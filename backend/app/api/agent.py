"""测试助手 Agent 接口：SSE 对话 + 历史查询 / 清空。

对话接口返回 text/event-stream，每行 data: 为一个 JSON 事件
（tool_start / tool_end / token / done / error），前端逐事件渲染。
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agent.runner import run_agent
from app.api.deps import require_project_access
from app.database import SessionLocal, get_db
from app.models.agent import AgentMessage
from app.models.design import DesignAsset
from app.models.project import Project
from app.models.requirement import RequirementDocument
from app.schemas import (
    AgentAttachmentOut,
    AgentChatRequest,
    AgentMessageOut,
    AgentReplyPreview,
    AgentToolCallOut,
)
from app.services.llm import LLMCallError
from app.services.settings_service import get_project_runtime_config

router = APIRouter(
    prefix="/projects/{project_id}/agent",
    tags=["agent"],
    dependencies=[Depends(require_project_access)],
)

HISTORY_LOAD_LIMIT = 50  # 历史接口与上下文注入读取的最大条数


def _parse_json_list(raw: str, fallback=None):
    fallback = fallback if fallback is not None else []
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return fallback
    return data if isinstance(data, list) else fallback


def _reply_preview(row: AgentMessage | None) -> AgentReplyPreview | None:
    if not row:
        return None
    content = (row.content or "").strip()
    if len(content) > 120:
        content = content[:120] + "…"
    return AgentReplyPreview(id=row.id, role=row.role, content=content)


def _serialize_message(
    row: AgentMessage,
    *,
    reply_map: dict[int, AgentMessage] | None = None,
) -> AgentMessageOut:
    tool_calls = _parse_json_list(row.tool_calls)
    attachments_raw = _parse_json_list(row.attachments)
    pending = _parse_json_list(row.pending_insight_ids)
    attachments = []
    for item in attachments_raw:
        if not isinstance(item, dict):
            continue
        attachments.append(
            AgentAttachmentOut(
                asset_id=int(item.get("asset_id") or 0),
                asset_type=str(item.get("asset_type") or "image"),
                title=str(item.get("title") or ""),
                filename=str(item.get("filename") or ""),
                figma_url=str(item.get("figma_url") or ""),
            )
        )
    reply_to = None
    if row.reply_to_id:
        target = (reply_map or {}).get(row.reply_to_id)
        reply_to = _reply_preview(target)
    return AgentMessageOut(
        id=row.id,
        role=row.role,
        content=row.content,
        tool_calls=[
            AgentToolCallOut(name=t["name"] if isinstance(t, dict) else str(t))
            for t in tool_calls
            if (isinstance(t, dict) and t.get("name")) or isinstance(t, str)
        ],
        attachments=attachments,
        document_id=row.document_id,
        pending_insight_ids=[
            int(x) for x in pending if str(x).isdigit() or isinstance(x, int)
        ],
        reply_to_id=row.reply_to_id,
        reply_to=reply_to,
        created_at=row.created_at,
    )


def _resolve_reply_to(
    db: Session,
    project_id: int,
    reply_to_id: int | None,
) -> AgentMessage | None:
    if not reply_to_id:
        return None
    target = (
        db.query(AgentMessage)
        .filter(AgentMessage.id == reply_to_id, AgentMessage.project_id == project_id)
        .first()
    )
    if not target:
        raise HTTPException(404, "被回复的消息不存在")
    return target


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _resolve_attachments(
    db: Session,
    project_id: int,
    data: AgentChatRequest,
) -> tuple[int | None, list[dict], str]:
    """校验附件归属，返回 (document_id, attachments_snapshot, context_note)。"""
    document_id = data.document_id
    asset_ids = list(data.asset_ids or [])
    for att in data.attachments or []:
        if att.asset_id not in asset_ids:
            asset_ids.append(att.asset_id)

    if document_id is not None:
        doc = (
            db.query(RequirementDocument)
            .filter(
                RequirementDocument.id == document_id,
                RequirementDocument.project_id == project_id,
            )
            .first()
        )
        if not doc:
            raise HTTPException(404, "目标需求文档不存在")
    elif not asset_ids:
        return None, [], ""

    attachments = []
    if asset_ids:
        assets = (
            db.query(DesignAsset)
            .filter(DesignAsset.project_id == project_id, DesignAsset.id.in_(asset_ids))
            .all()
        )
        by_id = {a.id: a for a in assets}
        if len(by_id) != len(set(asset_ids)):
            raise HTTPException(400, "存在不属于当前项目的设计稿附件")
        doc_ids = {a.document_id for a in assets}
        if document_id is None:
            if len(doc_ids) != 1:
                raise HTTPException(400, "请先选择目标需求文档")
            document_id = next(iter(doc_ids))
        elif any(a.document_id != document_id for a in assets):
            raise HTTPException(400, "设计稿必须属于所选需求文档")
        for aid in asset_ids:
            asset = by_id[aid]
            attachments.append(
                {
                    "asset_id": asset.id,
                    "asset_type": asset.asset_type,
                    "title": asset.title or "",
                    "filename": asset.filename or "",
                    "figma_url": asset.figma_url or "",
                }
            )

    note_parts = []
    if document_id is not None:
        note_parts.append(f"目标需求文档 ID={document_id}")
    if attachments:
        kinds = ", ".join(
            f"{a['asset_type']}#{a['asset_id']}（{a['title'] or a['filename'] or '未命名'}）"
            for a in attachments
        )
        note_parts.append(f"本轮附件：{kinds}")
        note_parts.append(
            "请优先解析 image 类型资产；Figma 仅作链接参考。"
            "解析后列出功能点，等待用户确认后再合并。"
        )
    return document_id, attachments, "；".join(note_parts)


@router.get("/messages", response_model=list[AgentMessageOut])
def list_messages(project_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(AgentMessage)
        .filter(AgentMessage.project_id == project_id)
        .order_by(AgentMessage.id.desc())
        .limit(HISTORY_LOAD_LIMIT)
        .all()
    )
    rows = list(reversed(rows))
    reply_map = {row.id: row for row in rows}
    # 被引用消息可能落在分页窗口外，补查一次
    missing_ids = {
        row.reply_to_id
        for row in rows
        if row.reply_to_id and row.reply_to_id not in reply_map
    }
    if missing_ids:
        extras = (
            db.query(AgentMessage)
            .filter(
                AgentMessage.project_id == project_id, AgentMessage.id.in_(missing_ids)
            )
            .all()
        )
        for row in extras:
            reply_map[row.id] = row
    return [_serialize_message(row, reply_map=reply_map) for row in rows]


@router.delete("/messages", status_code=204)
def clear_messages(project_id: int, db: Session = Depends(get_db)):
    db.query(AgentMessage).filter(AgentMessage.project_id == project_id).delete()
    db.commit()


@router.post("/chat")
async def chat(
    project_id: int,
    data: AgentChatRequest,
    project: Project = Depends(require_project_access),
    db: Session = Depends(get_db),
):
    model_config = get_project_runtime_config(db, project_id)
    document_id, attachments, context_note = _resolve_attachments(db, project_id, data)
    reply_target = _resolve_reply_to(db, project_id, data.reply_to_id)
    question = (data.question or "").strip()
    if reply_target:
        preview = _reply_preview(reply_target)
        role_label = "用户" if reply_target.role == "user" else "助手"
        quote = f"【回复 {role_label}】{preview.content if preview else ''}"
        context_note = f"{context_note}；{quote}" if context_note else quote
        # 把引用内容注入问题，便于模型对齐被回复的那一条
        question_for_model = f"{quote}\n\n{question}" if question else quote
    else:
        question_for_model = question

    history_rows = (
        db.query(AgentMessage)
        .filter(AgentMessage.project_id == project_id)
        .order_by(AgentMessage.id.desc())
        .limit(HISTORY_LOAD_LIMIT)
        .all()
    )
    history = []
    for row in reversed(history_rows):
        content = row.content or ""
        if row.role == "user" and row.attachments:
            try:
                atts = json.loads(row.attachments)
            except json.JSONDecodeError:
                atts = []
            if atts:
                content = f"{content}\n[附件上下文] document_id={row.document_id}, assets={atts}"
        history.append((row.role, content))

    user_msg = AgentMessage(
        project_id=project_id,
        role="user",
        content=question,
        attachments=json.dumps(attachments, ensure_ascii=False),
        document_id=document_id,
        reply_to_id=reply_target.id if reply_target else None,
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)
    user_msg_id = user_msg.id
    project_name = project.name

    async def event_stream():
        session = SessionLocal()
        try:
            answer, tool_calls, pending_ids = "", [], []
            yield _sse({"type": "user_message", "id": user_msg_id})
            try:
                async for event in run_agent(
                    session,
                    project_id,
                    project_name,
                    question_for_model,
                    history,
                    model_config,
                    document_id=document_id,
                    attachments=attachments,
                    context_note=context_note,
                ):
                    if event["type"] == "done":
                        answer = event["content"]
                        tool_calls = event["tool_calls"]
                        pending_ids = event.get("pending_insight_ids") or []
                        continue  # 持久化后再发 done，附带消息 ID
                    yield _sse(event)
            except LLMCallError as exc:
                yield _sse({"type": "error", "message": str(exc)})
                return
            assistant = AgentMessage(
                project_id=project_id,
                role="assistant",
                content=answer,
                tool_calls=json.dumps(tool_calls, ensure_ascii=False),
                document_id=document_id,
                pending_insight_ids=json.dumps(pending_ids, ensure_ascii=False),
            )
            session.add(assistant)
            session.commit()
            session.refresh(assistant)
            yield _sse(
                {
                    "type": "done",
                    "content": answer,
                    "tool_calls": tool_calls,
                    "pending_insight_ids": pending_ids,
                    "id": assistant.id,
                    "user_message_id": user_msg_id,
                }
            )
        finally:
            session.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
