"""测试助手 Agent 运行器：LangGraph ReAct 循环，产出前端可流式消费的事件。

事件类型（dict 的 type 字段）：
- tool_start: {name, input}   开始调用某个工具
- tool_end:   {name, output?} 工具调用结束
- token:      {content}       模型回答的增量文本
- done:       {content, tool_calls, pending_insight_ids}  本轮结束

模型/网络错误抛出 LLMCallError，由 API 层转成 error 事件。
Mock 模式（未配置生成模型 Key 或显式开启）走固定剧本，不调用真实接口。
有截图附件时：无论是否 Mock，都强制走设计稿解析，禁止模型凭空编造功能点。
"""

import json
from typing import Any, AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from sqlalchemy.orm import Session

from app.agent.tools import build_agent_tools
from app.ai.model_factory import create_chat_model, normalize_chat_error
from app.models.testcase import TestCase
from app.services import design_service, knowledge_service
from app.services.settings_service import RuntimeModelConfig

# recursion_limit 按 LangGraph 超步计：agent + tools 一轮占 2 步，
# 13 约等于最多 6 轮工具调用 + 最终回答，防止模型陷入循环取数。
MAX_GRAPH_STEPS = 13
HISTORY_LIMIT = 12  # 注入模型的历史消息条数上限

SYSTEM_PROMPT = """你是「测试助手」，嵌入在 AI 测试用例平台中的项目问答助手。
当前项目：{project_name}。

你可以调用工具查询该项目的真实数据：知识库、测试用例、需求覆盖率、测试任务进度、缺陷记录。
同时支持设计稿受控写入：查询设计稿、解析截图、查看解析结果；仅在用户明确确认后才能合并功能点。

回答规则：
1. 涉及项目数据的问题必须先调用工具取数，再基于返回结果回答，禁止编造数字或规则。
2. 工具没有查到相关结果时，直接告诉用户"没有查到"，并给出下一步建议（如补充知识库、调整关键词）。
3. 除设计稿合并外，你是只读助手，不能修改其他数据。用户要求增删改用例/任务时，说明无此权限并指引到对应页面。
4. 设计稿协议（必须遵守）：
   - 禁止在未调用 parse_design_asset / get_design_insights 时编造任何功能点、页面或验收标准；
   - 必须如实转述工具返回的 is_mock_result / source_note / parse_source；若为 Mock，明确告诉用户「未调用视觉模型，是示例数据」；
   - Figma 链接只作关联展示，不能直接视觉解析，请提示用户补充页面截图；
   - 禁止在未确认时调用 merge_design_insights；调用合并时 confirmed 必须为 true 且传入 insight_ids；
   - 合并后提醒用户：需求已回退为 structured，需重新确认功能点后才能生成用例。
5. 用简体中文回答，简明扼要，数字与结论要能对应到工具返回的数据。
6. 当引导用户去某个页面操作时，使用 Markdown 链接语法 [页面名](路径) 给出可点击的站内跳转链接，路径必须取自下方「本项目页面链接」，不要编造其它路径。

本项目页面链接（projectId={project_id}）：
- 需求与用例生成（导入/确认功能点/生成用例）：[生成流程](/projects/{project_id}/generate)
- 项目用例库：[用例库](/projects/{project_id}/testcases)
- 测试任务：[测试任务](/projects/{project_id}/tasks)
- 项目知识库：[知识库](/projects/{project_id}/knowledge)
- 生成历史：[生成历史](/projects/{project_id}/generations)
- 项目主页：[项目详情](/projects/{project_id})
- 模型设置：[设置](/settings)
{context_block}"""


def _message_text(content) -> str:
    """兼容 str 与分块 list 两种 content 形态。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    return str(content or "")


def _history_messages(history: list[tuple[str, str]]) -> list:
    messages = []
    for role, content in history[-HISTORY_LIMIT:]:
        if not content:
            continue
        messages.append(HumanMessage(content) if role == "user" else AIMessage(content))
    return messages


def _extract_pending_ids(tool_name: str, output) -> list[int]:
    if tool_name not in {"parse_design_asset", "get_design_insights"}:
        return []
    text = _message_text(output)
    try:
        data = json.loads(text) if isinstance(text, str) else output
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, dict):
        return []
    ids = data.get("pending_insight_ids") or []
    result = []
    for item in ids:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _http_detail(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, str) and detail:
        return detail
    return str(exc)


async def _stream_parse_images(
    db: Session,
    project_id: int,
    image_assets: list[dict],
) -> AsyncIterator[dict[str, Any]]:
    """强制解析本轮截图附件，产出 tool 事件；最后产出 type=_parse_summary。"""
    summaries: list[dict] = []
    pending_ids: list[int] = []
    errors: list[str] = []
    tool_calls: list[dict] = []

    for item in image_assets:
        asset_id = int(item["asset_id"])
        tool_calls.append({"name": "parse_design_asset"})
        yield {
            "type": "tool_start",
            "name": "parse_design_asset",
            "input": {"asset_id": asset_id},
        }
        try:
            asset = await design_service.parse_asset(db, project_id, asset_id)
            summary = design_service.asset_to_summary(asset)
            ids = [i["id"] for i in summary["insights"] if not i["merged"]]
            pending_ids.extend(ids)
            summaries.append(summary)
            output = json.dumps(
                {**summary, "pending_insight_ids": ids},
                ensure_ascii=False,
            )
        except Exception as exc:
            err = _http_detail(exc)
            errors.append(f"asset_id={asset_id}：{err}")
            summaries.append({
                "id": asset_id,
                "error": err,
                "insights": [],
                "is_mock_result": False,
                "source_note": "",
            })
            output = json.dumps({"error": err, "asset_id": asset_id}, ensure_ascii=False)
        yield {"type": "tool_end", "name": "parse_design_asset", "output": output[:4000]}

    yield {
        "type": "_parse_summary",
        "summaries": summaries,
        "pending_insight_ids": pending_ids,
        "errors": errors,
        "tool_calls": tool_calls,
    }


def _format_parse_answer(summaries: list[dict], errors: list[str]) -> list[str]:
    lines: list[str] = []
    if errors and not any(s.get("insights") for s in summaries):
        lines.append("设计稿解析失败，未能调用成功的视觉解析：")
        lines.extend(f"- {err}" for err in errors)
        lines.append("请到「设置 → 视觉模型」确认模型已开通且接口可达，稍后重试或重新上传/解析。")
        return lines

    for summary in summaries:
        if summary.get("error"):
            lines.append(f"设计稿 #{summary.get('id')} 解析失败：{summary['error']}")
            continue
        title = summary.get("title") or summary.get("filename") or f"#{summary.get('id')}"
        if summary.get("is_design") is False:
            desc = summary.get("image_summary") or "图片内容与产品界面无关"
            lines.append(f"【{title}】这张图不像产品设计稿：{desc}")
            lines.append("已跳过，不会生成功能点。如需解析，请上传真实的页面截图或原型图。")
            continue
        if summary.get("is_mock_result"):
            lines.append(f"【{title}】解析完成，但是 Mock 示例数据（未调用视觉模型）。")
            if summary.get("source_note"):
                lines.append(summary["source_note"] + "。")
            lines.append("识别到的功能点如下（仅供演示）：")
        else:
            note = summary.get("source_note") or "真实视觉解析"
            lines.append(f"【{title}】已解析（{note}），功能点：")
        insights = summary.get("insights") or []
        if not insights:
            lines.append("- （未识别到功能点）")
        for insight in insights:
            lines.append(
                f"- [{insight.get('priority')}] {insight.get('module')} / {insight.get('feature')}："
                f"{insight.get('description') or '无描述'}"
            )
    if errors:
        lines.append("部分解析失败：")
        lines.extend(f"- {err}" for err in errors)
    # 仅当确有待确认功能点时才提示合并
    has_insights = any(s.get("insights") for s in summaries)
    if has_insights:
        lines.append("请确认后点击「确认合并」，或回复「确认合并」。在你确认前我不会写入需求。")
    return lines


async def _run_design_parse_turn(
    db: Session,
    project_id: int,
    image_assets: list[dict],
) -> AsyncIterator[dict]:
    """有截图时的确定性回合：真实调用解析服务并展示结果，不经过生成模型编造。"""
    summary_event = None
    async for event in _stream_parse_images(db, project_id, image_assets):
        if event["type"] == "_parse_summary":
            summary_event = event
            continue
        yield event

    assert summary_event is not None
    lines = _format_parse_answer(summary_event["summaries"], summary_event["errors"])
    for piece in lines:
        yield {"type": "token", "content": piece + "\n"}
    yield {
        "type": "done",
        "content": "\n".join(lines) + "\n",
        "tool_calls": summary_event["tool_calls"],
        "pending_insight_ids": summary_event["pending_insight_ids"],
    }


async def run_agent(
    db: Session,
    project_id: int,
    project_name: str,
    question: str,
    history: list[tuple[str, str]],
    model_config: RuntimeModelConfig,
    *,
    document_id: int | None = None,
    attachments: list[dict] | None = None,
    context_note: str = "",
) -> AsyncIterator[dict]:
    """执行一轮问答，异步产出事件流。history 为 [(role, content)] 旧→新。"""
    attachments = attachments or []
    image_assets = [a for a in attachments if a.get("asset_type") == "image"]
    # 有截图则强制走解析链路，避免生成模型跳过工具并编造功能点
    if image_assets:
        async for event in _run_design_parse_turn(db, project_id, image_assets):
            yield event
        return

    if model_config.use_mock_llm:
        async for event in _run_mock(db, project_id, question):
            yield event
        return

    tools = build_agent_tools(db, project_id, model_config)
    model = create_chat_model(model_config, "generation")
    llm = model.bind_tools(tools)

    async def call_model(state: MessagesState):
        response = await llm.ainvoke(state["messages"])
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    graph = builder.compile()

    context_block = f"\n本轮上下文：{context_note}" if context_note else ""
    user_content = question
    if context_note:
        user_content = f"{question}\n\n[{context_note}]"

    messages = [
        SystemMessage(SYSTEM_PROMPT.format(
            project_name=project_name,
            project_id=project_id,
            context_block=context_block,
        )),
        *_history_messages(history),
        HumanMessage(user_content),
    ]

    answer_parts: list[str] = []
    tool_calls: list[dict] = []
    pending_insight_ids: list[int] = []
    try:
        async for event in graph.astream_events(
            {"messages": messages},
            config={"recursion_limit": MAX_GRAPH_STEPS},
            version="v2",
        ):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                text = _message_text(event["data"]["chunk"].content)
                if text:
                    answer_parts.append(text)
                    yield {"type": "token", "content": text}
            elif kind == "on_tool_start":
                yield {
                    "type": "tool_start",
                    "name": event["name"],
                    "input": event["data"].get("input") or {},
                }
            elif kind == "on_tool_end":
                output = event["data"].get("output")
                tool_calls.append({"name": event["name"]})
                ids = _extract_pending_ids(event["name"], output)
                if ids:
                    pending_insight_ids = ids
                payload = {"type": "tool_end", "name": event["name"]}
                if output is not None:
                    payload["output"] = _message_text(output)[:4000]
                yield payload
    except GraphRecursionError:
        note = "本次查询涉及的步骤过多，我先停在这里。请把问题拆小一点再问我，比如按模块或按任务分别询问。"
        answer_parts.append(note)
        yield {"type": "token", "content": note}
    except Exception as exc:
        raise normalize_chat_error(exc, "generation") from exc

    yield {
        "type": "done",
        "content": "".join(answer_parts),
        "tool_calls": tool_calls,
        "pending_insight_ids": pending_insight_ids,
    }


async def _run_mock(
    db: Session,
    project_id: int,
    question: str,
) -> AsyncIterator[dict]:
    """Mock 剧本：无设计附件时走知识库检索演示。"""
    yield {"type": "tool_start", "name": "search_knowledge", "input": {"query": question}}
    try:
        hits = await knowledge_service.retrieve(db, project_id, question, top_k=3)
    except Exception:
        hits = []
    yield {"type": "tool_end", "name": "search_knowledge"}

    case_count = db.query(TestCase).filter(TestCase.project_id == project_id).count()
    lines = [
        f"（Mock 模式）我检索了项目知识库，命中 {len(hits)} 条相关内容；当前项目共有 {case_count} 条测试用例。",
    ]
    if hits:
        top = hits[0]
        source = f"《{top['title']}》" + (f" · {top['heading']}" if top["heading"] else "")
        lines.append(f"最相关的知识来自 {source}：{top['content'][:120]}")
    lines.append("配置真实生成模型后，我可以基于这些数据直接回答你的问题。也可上传设计稿截图，让我解析功能点。")

    for piece in lines:
        yield {"type": "token", "content": piece + "\n"}
    yield {
        "type": "done",
        "content": "\n".join(lines) + "\n",
        "tool_calls": [{"name": "search_knowledge"}],
        "pending_insight_ids": [],
    }
