"""测试助手的工具集：只读查询 + 设计稿受控写入。

全部工具在构建时绑定 project_id，LLM 无法跨项目取数；列表类输出做条数与
文本截断，避免把整个用例库塞进上下文。
"""

import json

from fastapi import HTTPException
from langchain_core.tools import StructuredTool
from sqlalchemy.orm import Session, selectinload

from app.models.execution import TestBatch, TestBatchCase, TestTask
from app.models.requirement import RequirementDocument, RequirementItem
from app.models.testcase import TestCase
from app.services import design_service, knowledge_service
from app.services.settings_service import RuntimeModelConfig

MAX_LIST_ITEMS = 20  # 列表类工具单次最多返回条数
SNIPPET_CHARS = 400  # 知识分块注入上下文的最大字符数


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _clip(text: str, limit: int = SNIPPET_CHARS) -> str:
    text = text or ""
    return text if len(text) <= limit else f"{text[:limit]}……（已截断）"


def build_agent_tools(
    db: Session,
    project_id: int,
    model_config: RuntimeModelConfig,
) -> list[StructuredTool]:
    """构建绑定到指定项目的工具集。"""

    async def search_knowledge(query: str) -> str:
        try:
            hits = await knowledge_service.retrieve(
                db, project_id, query, top_k=5, model_config=model_config
            )
        except Exception as exc:
            return _dump({"error": f"知识库检索失败：{exc}"})
        if not hits:
            return _dump({"hits": [], "message": "知识库中没有检索到相关内容"})
        return _dump({
            "hits": [
                {
                    "title": h["title"],
                    "heading": h["heading"],
                    "content": _clip(h["content"]),
                    "score": h["score"],
                    "match": h["match"],
                }
                for h in hits
            ]
        })

    def list_testcases(
        keyword: str = "",
        priority: str = "",
        case_type: str = "",
        module: str = "",
        limit: int = MAX_LIST_ITEMS,
    ) -> str:
        q = (
            db.query(TestCase, RequirementItem.module, RequirementItem.feature)
            .outerjoin(RequirementItem, TestCase.requirement_item_id == RequirementItem.id)
            .filter(TestCase.project_id == project_id)
        )
        if keyword.strip():
            q = q.filter(TestCase.title.ilike(f"%{keyword.strip()}%"))
        if priority.strip():
            q = q.filter(TestCase.priority == priority.strip().upper())
        if case_type.strip():
            q = q.filter(TestCase.case_type == case_type.strip())
        if module.strip():
            q = q.filter(RequirementItem.module.ilike(f"%{module.strip()}%"))
        total = q.count()
        limit = max(1, min(limit, MAX_LIST_ITEMS))
        rows = q.order_by(TestCase.priority, TestCase.id).limit(limit).all()
        return _dump({
            "total": total,
            "returned": len(rows),
            "note": "" if total <= limit else f"共 {total} 条，仅返回前 {limit} 条，可用筛选条件缩小范围",
            "cases": [
                {
                    "id": tc.id,
                    "title": tc.title,
                    "priority": tc.priority,
                    "case_type": tc.case_type,
                    "is_smoke": tc.is_smoke,
                    "module": m or "",
                    "feature": f or "",
                }
                for tc, m, f in rows
            ],
        })

    def get_testcase_detail(case_id: int) -> str:
        row = (
            db.query(TestCase, RequirementItem.module, RequirementItem.feature)
            .outerjoin(RequirementItem, TestCase.requirement_item_id == RequirementItem.id)
            .filter(TestCase.project_id == project_id, TestCase.id == case_id)
            .first()
        )
        if not row:
            return _dump({"error": f"该项目中不存在 ID 为 {case_id} 的用例"})
        tc, module, feature = row
        return _dump({
            "id": tc.id,
            "title": tc.title,
            "priority": tc.priority,
            "case_type": tc.case_type,
            "is_smoke": tc.is_smoke,
            "module": module or "",
            "feature": feature or "",
            "precondition": tc.precondition,
            "steps": tc.steps,
            "expected_result": tc.expected_result,
            "status": tc.status,
            "source": tc.source,
        })

    def get_coverage_summary() -> str:
        items = (
            db.query(RequirementItem)
            .join(RequirementDocument, RequirementItem.document_id == RequirementDocument.id)
            .filter(RequirementDocument.project_id == project_id, RequirementItem.confirmed == True)  # noqa: E712
            .all()
        )
        if not items:
            return _dump({"message": "该项目还没有已确认的功能点，无法统计覆盖率"})
        covered_ids = {
            item_id
            for (item_id,) in db.query(TestCase.requirement_item_id)
            .filter(TestCase.project_id == project_id, TestCase.requirement_item_id.isnot(None))
            .distinct()
        }
        uncovered = [i for i in items if i.id not in covered_ids]
        return _dump({
            "confirmed_features": len(items),
            "covered_features": len(items) - len(uncovered),
            "coverage_rate": round((len(items) - len(uncovered)) / len(items) * 100, 1),
            "uncovered": [
                {"module": i.module, "feature": i.feature}
                for i in uncovered[:MAX_LIST_ITEMS]
            ],
        })

    def get_test_task_stats(task_name: str = "") -> str:
        q = (
            db.query(TestTask)
            .options(selectinload(TestTask.batches).selectinload(TestBatch.batch_cases))
            .filter(TestTask.project_id == project_id)
        )
        if task_name.strip():
            q = q.filter(TestTask.name.ilike(f"%{task_name.strip()}%"))
        tasks = q.order_by(TestTask.created_at.desc()).limit(10).all()
        if not tasks:
            return _dump({"message": "没有找到匹配的测试任务"})
        return _dump({
            "tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "status": t.status,
                    "stats": t.stats,
                    "batches": [
                        {"id": b.id, "name": b.name, "status": b.status, "stats": b.stats}
                        for b in t.batches
                    ],
                }
                for t in tasks
            ]
        })

    def list_defects(include_blocked: bool = True) -> str:
        results = ["failed", "blocked"] if include_blocked else ["failed"]
        rows = (
            db.query(TestBatchCase, TestBatch, TestTask, TestCase)
            .join(TestBatch, TestBatchCase.batch_id == TestBatch.id)
            .join(TestTask, TestBatch.task_id == TestTask.id)
            .join(TestCase, TestBatchCase.case_id == TestCase.id)
            .filter(TestTask.project_id == project_id, TestBatchCase.result.in_(results))
            .order_by(TestBatchCase.executed_at.desc())
            .limit(MAX_LIST_ITEMS)
            .all()
        )
        if not rows:
            return _dump({"defects": [], "message": "当前没有失败或阻塞的执行记录"})
        return _dump({
            "defects": [
                {
                    "case_id": tc.id,
                    "title": tc.title,
                    "priority": tc.priority,
                    "result": bc.result,
                    "note": _clip(bc.note, 200),
                    "defect_ref": bc.defect_ref,
                    "task": task.name,
                    "batch": batch.name,
                    "executed_at": bc.executed_at,
                }
                for bc, batch, task, tc in rows
            ]
        })

    def list_requirement_documents(limit: int = 10) -> str:
        docs = (
            db.query(RequirementDocument)
            .filter(RequirementDocument.project_id == project_id)
            .order_by(RequirementDocument.created_at.desc())
            .limit(max(1, min(limit, MAX_LIST_ITEMS)))
            .all()
        )
        return _dump({
            "documents": [
                {
                    "id": d.id,
                    "title": d.title,
                    "status": d.status,
                    "item_count": len(d.items or []),
                    "created_at": d.created_at,
                }
                for d in docs
            ]
        })

    def list_design_assets(document_id: int) -> str:
        try:
            assets = design_service.list_assets(db, project_id, document_id)
        except HTTPException as exc:
            return _dump({"error": exc.detail})
        return _dump({
            "document_id": document_id,
            "assets": [design_service.asset_to_summary(a) for a in assets],
            "note": "Figma 链接仅作关联展示；请对截图资产调用 parse_design_asset 做视觉解析。解析后勿自动合并，需用户确认。",
        })

    async def parse_design_asset(asset_id: int) -> str:
        try:
            asset = await design_service.parse_asset(db, project_id, asset_id)
        except HTTPException as exc:
            return _dump({"error": exc.detail})
        summary = design_service.asset_to_summary(asset)
        pending_ids = [i["id"] for i in summary["insights"] if not i["merged"]]
        if summary.get("is_design") is False:
            message = (
                "这张图片不是产品设计稿（视觉模型判定）。"
                f"图片内容：{summary.get('image_summary') or '与产品界面无关'}。"
                "请如实告知用户该图已跳过、未生成任何功能点，并建议上传真实页面截图或原型图；"
                "禁止编造功能点，也不要调用 merge_design_insights。"
            )
        elif summary.get("is_mock_result"):
            message = (
                "解析完成，但结果是 Mock 示例数据（未调用视觉模型）。"
                f"{summary.get('source_note', '')}。"
                "请把功能点与来源说明一并展示给用户，提醒先配置视觉模型并重新解析；"
                "不要调用 merge_design_insights，除非用户已明确确认。"
            )
        else:
            message = (
                f"解析完成（{summary.get('source_note', '真实视觉解析')}）。"
                "请把功能点列表展示给用户，并明确等待确认后再合并。"
                "不要调用 merge_design_insights，除非用户已明确确认。"
            )
        return _dump({
            **summary,
            "pending_insight_ids": pending_ids,
            "message": message,
        })

    def get_design_insights(document_id: int, asset_id: int = 0) -> str:
        try:
            if asset_id:
                asset = design_service.get_asset(db, project_id, asset_id)
                if asset.document_id != document_id:
                    return _dump({"error": "设计稿不属于该需求文档"})
                assets = [asset]
            else:
                assets = design_service.list_assets(db, project_id, document_id)
        except HTTPException as exc:
            return _dump({"error": exc.detail})
        insights = []
        asset_sources = []
        for asset in assets:
            asset_sources.append({
                "asset_id": asset.id,
                "parse_source": asset.parse_source or "",
                "is_mock_result": asset.parse_source == "mock",
                "source_note": design_service.source_note(asset.parse_source or ""),
            })
            for insight in asset.insights or []:
                insights.append(design_service.insight_to_dict(insight))
        pending = [i for i in insights if not i["merged"]]
        any_mock = any(s["is_mock_result"] for s in asset_sources)
        return _dump({
            "document_id": document_id,
            "total": len(insights),
            "pending_count": len(pending),
            "pending_insight_ids": [i["id"] for i in pending],
            "asset_sources": asset_sources,
            "insights": insights[:MAX_LIST_ITEMS],
            "note": (
                "其中含 Mock 示例数据，请先配置视觉模型并重新解析后再合并。"
                if any_mock else
                "合并前必须得到用户确认；前端确认卡片或用户明确说「确认合并」后才可调用 merge_design_insights。"
            ),
        })

    def merge_design_insights(
        document_id: int,
        insight_ids: list[int],
        confirmed: bool = False,
    ) -> str:
        if not confirmed:
            return _dump({
                "error": "拒绝合并：confirmed 必须为 true。请先展示功能点并等待用户确认。",
            })
        if not insight_ids:
            return _dump({"error": "请提供要合并的 insight_ids"})
        try:
            result = design_service.merge_insights(
                db, project_id, document_id, insight_ids, selected_only=False,
            )
        except HTTPException as exc:
            return _dump({"error": exc.detail})
        return _dump({
            "message": "已合并设计功能点到需求文档，需求状态已回退为 structured，需用户重新确认功能点后才能生成用例。",
            "document_id": document_id,
            "merged_count": result["merged_count"],
            "added_count": result["added_count"],
            "document_status": result["document_status"],
            "item_count": result["item_count"],
        })

    return [
        StructuredTool.from_function(
            coroutine=search_knowledge,
            name="search_knowledge",
            description=(
                "检索本项目知识库（业务规则、历史文档、缺陷经验等）。"
                "当用户询问业务规则、名词解释、历史背景等需要文档依据的问题时使用。"
                "参数 query 为检索关键词或问题原文。"
            ),
        ),
        StructuredTool.from_function(
            func=list_testcases,
            name="list_testcases",
            description=(
                "按条件查询本项目的测试用例列表（返回摘要，不含步骤详情）。"
                "可选参数：keyword（标题关键词）、priority（P0/P1/P2）、"
                "case_type（functional/boundary/exception）、module（所属模块名）、limit（最多 20）。"
                "当用户想了解有哪些用例、某类用例数量时使用。"
            ),
        ),
        StructuredTool.from_function(
            func=get_testcase_detail,
            name="get_testcase_detail",
            description=(
                "按用例 ID 查询单条用例的完整内容（前置条件、步骤、预期结果）。"
                "用户询问某条具体用例的细节时使用，case_id 可先通过 list_testcases 获得。"
            ),
        ),
        StructuredTool.from_function(
            func=get_coverage_summary,
            name="get_coverage_summary",
            description=(
                "统计本项目需求功能点的用例覆盖情况：已确认功能点数、已覆盖数、"
                "覆盖率与未覆盖功能点清单。用户询问覆盖率、哪些需求没有用例时使用。"
            ),
        ),
        StructuredTool.from_function(
            func=get_test_task_stats,
            name="get_test_task_stats",
            description=(
                "查询本项目测试任务的执行进度与通过率（任务与批次两级统计：总数/通过/失败/阻塞/未执行）。"
                "可选参数 task_name 按任务名模糊过滤。用户询问测试进度、通过率时使用。"
            ),
        ),
        StructuredTool.from_function(
            func=list_defects,
            name="list_defects",
            description=(
                "列出本项目测试执行中失败（可含阻塞）的用例记录，含备注与缺陷单号。"
                "可选参数 include_blocked 是否包含阻塞记录（默认包含）。用户询问缺陷、失败用例时使用。"
            ),
        ),
        StructuredTool.from_function(
            func=list_requirement_documents,
            name="list_requirement_documents",
            description=(
                "列出本项目的需求文档（含状态与功能点数）。"
                "处理设计稿前先确认目标 document_id；用户未指定时取最近一份。"
            ),
        ),
        StructuredTool.from_function(
            func=list_design_assets,
            name="list_design_assets",
            description=(
                "查询指定需求文档下的设计稿资产（截图与 Figma 链接）及已有解析结果摘要。"
                "参数 document_id 必填。"
            ),
        ),
        StructuredTool.from_function(
            coroutine=parse_design_asset,
            name="parse_design_asset",
            description=(
                "对指定截图设计稿做视觉解析，产出待确认功能点（写入 DesignInsight）。"
                "参数 asset_id 必填；仅支持 image 类型。解析后必须向用户展示结果并等待确认，禁止自动合并。"
            ),
        ),
        StructuredTool.from_function(
            func=get_design_insights,
            name="get_design_insights",
            description=(
                "查看指定需求文档（或某张设计稿）的解析功能点列表，含 pending_insight_ids。"
                "参数 document_id 必填；可选 asset_id 过滤单张设计稿。"
            ),
        ),
        StructuredTool.from_function(
            func=merge_design_insights,
            name="merge_design_insights",
            description=(
                "将已解析的设计功能点合并到目标需求文档。仅当用户明确确认后调用："
                "confirmed 必须为 true，并传入 insight_ids。"
                "合并后需求会回退为 structured，需重新确认功能点。"
            ),
        ),
    ]
