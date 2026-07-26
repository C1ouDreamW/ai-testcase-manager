import json

from langchain_core.exceptions import OutputParserException

from app.ai.retrievers import AITCHybridRetriever, documents_to_knowledge
from app.database import SessionLocal
from app.models.generation import GeneratedCaseDraft, GenerationTask, QualityReport
from app.models.requirement import RequirementDocument, RequirementItem
from app.services.quality_checker import (
    build_quality_report,
    check_case,
    detect_duplicates,
    is_meaningful_case,
    normalize_steps,
)
from app.services.settings_service import get_project_runtime_config
from app.skills.base import SkillContext
from app.skills.registry import get_registry
from app.workflows.generation.state import GenerationState


def _task_or_raise(db, task_id: int) -> GenerationTask:
    task = db.get(GenerationTask, task_id)
    if not task:
        raise RuntimeError("生成任务不存在")
    return task


def _feature_data(item: RequirementItem) -> dict:
    return {
        "module": item.module,
        "feature": item.feature,
        "description": item.description,
        "acceptance_criteria": item.acceptance_criteria,
        "constraints": item.constraints,
        "priority": item.priority,
    }


def _parse_scope(raw: str) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    normalized = {
        "in_scope": [str(s).strip() for s in (data.get("in_scope") or []) if str(s).strip()],
        "out_scope": [str(s).strip() for s in (data.get("out_scope") or []) if str(s).strip()],
        "risks": [str(s).strip() for s in (data.get("risks") or []) if str(s).strip()],
    }
    return normalized if any(normalized.values()) else None


def _strategy_config(task: GenerationTask) -> dict:
    registry = get_registry()
    try:
        data = json.loads(task.strategy_config or "{}")
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    preset = data.get("strategy") or data.get("preset") or task.strategy
    return {
        "strategy": registry.normalize_strategy(preset),
        "specialist_skills": registry.validate_specialist_skills(data.get("specialist_skills") or []),
        "use_knowledge": bool(data.get("use_knowledge", False)),
    }


def _skill_context(task: GenerationTask, strategy: str, model_config) -> SkillContext:
    return SkillContext(
        model_config=model_config,
        project_id=task.project_id,
        task_id=task.id,
        strategy=strategy,
        use_mock=model_config.use_mock_llm,
    )


def _structured_output_failure(state: GenerationState, exc: OutputParserException) -> dict:
    """首次格式错误交给 Graph 重试；第二次直接失败并停在生成节点前。"""
    if state.get("retry_count", 0) >= 1:
        raise RuntimeError(f"模型连续两次未返回有效结构化结果：{exc}") from exc
    return {"current_cases": [], "generation_error": str(exc)}


async def load_task(state: GenerationState) -> dict:
    task_id = state["task_id"]
    db = SessionLocal()
    try:
        task = _task_or_raise(db, task_id)
        items = (
            db.query(RequirementItem)
            .filter(
                RequirementItem.document_id == task.document_id,
                RequirementItem.confirmed == True,
            )
            .order_by(RequirementItem.sort_order)
            .all()
        )
        if not items:
            raise RuntimeError("没有已确认的功能点")

        document = db.get(RequirementDocument, task.document_id)
        config = _strategy_config(task)

        task.status = "generating"
        task.progress = 0
        task.stage = "准备中"
        task.error_message = ""
        db.query(GeneratedCaseDraft).filter(GeneratedCaseDraft.task_id == task.id).delete()
        existing_report = db.query(QualityReport).filter(QualityReport.task_id == task.id).first()
        if existing_report:
            db.delete(existing_report)
        db.commit()

        return {
            "project_id": task.project_id,
            "document_id": task.document_id,
            "feature_ids": [item.id for item in items],
            "feature_index": 0,
            "current_feature_id": None,
            "current_feature": None,
            "strategy": config["strategy"],
            "specialist_skills": config["specialist_skills"],
            "use_knowledge": config["use_knowledge"],
            "scope": _parse_scope(document.test_scope) if document else None,
            "retrieval_query": "",
            "knowledge": [],
            "knowledge_refs": {},
            "current_cases": [],
            "retry_count": 0,
            "generation_error": "",
            "duplicate_count": 0,
        }
    finally:
        db.close()


async def prepare_feature(state: GenerationState) -> dict:
    item_id = state["feature_ids"][state["feature_index"]]
    db = SessionLocal()
    try:
        item = db.get(RequirementItem, item_id)
        if not item:
            raise RuntimeError(f"功能点不存在: {item_id}")
        task = _task_or_raise(db, state["task_id"])
        total = len(state["feature_ids"])
        task.stage = f"生成用例 {state['feature_index'] + 1}/{total}：{item.feature}"
        db.commit()
        return {
            "current_feature_id": item.id,
            "current_feature": _feature_data(item),
            "retrieval_query": " ".join(filter(None, [item.module, item.feature, item.description])),
            "knowledge": [],
            "current_cases": [],
            "retry_count": 0,
            "generation_error": "",
        }
    finally:
        db.close()


async def retrieve_knowledge(state: GenerationState) -> dict:
    if not state.get("use_knowledge"):
        return {"knowledge": []}

    db = SessionLocal()
    try:
        task = _task_or_raise(db, state["task_id"])
        task.stage = f"检索知识：{(state.get('current_feature') or {}).get('feature', '')}"
        db.commit()
        model_config = get_project_runtime_config(db, state["project_id"])
        retriever = AITCHybridRetriever(
            db=db,
            project_id=state["project_id"],
            runtime_config=model_config,
        )
        try:
            documents = await retriever.ainvoke(state.get("retrieval_query", ""))
        except Exception:
            return {"knowledge": []}

        knowledge = documents_to_knowledge(documents)
        refs = dict(state.get("knowledge_refs") or {})
        if knowledge:
            refs[str(state["current_feature_id"])] = [
                {
                    "title": item.get("title", ""),
                    "heading": item.get("heading", ""),
                    "score": item.get("score", 0.0),
                    "match": item.get("match", "vector"),
                }
                for item in knowledge
            ]
        return {"knowledge": knowledge, "knowledge_refs": refs}
    finally:
        db.close()


async def generate_core_cases(state: GenerationState) -> dict:
    db = SessionLocal()
    try:
        task = _task_or_raise(db, state["task_id"])
        model_config = get_project_runtime_config(db, task.project_id)
        context = _skill_context(task, state["strategy"], model_config)
        task.stage = f"生成基础用例：{(state.get('current_feature') or {}).get('feature', '')}"
        db.commit()
        try:
            result = await get_registry().run(
                "case_writer",
                {
                    "feature_item": state["current_feature"],
                    "strategy": state["strategy"],
                    "scope": state.get("scope"),
                    "knowledge": state.get("knowledge") or [],
                },
                context,
            )
        except OutputParserException as exc:
            return _structured_output_failure(state, exc)
        return {"current_cases": list(result.get("cases") or []), "generation_error": ""}
    finally:
        db.close()


async def generate_specialist_cases(state: GenerationState) -> dict:
    specialist_skills = state.get("specialist_skills") or []
    if not specialist_skills:
        return {"generation_error": ""}

    db = SessionLocal()
    try:
        task = _task_or_raise(db, state["task_id"])
        model_config = get_project_runtime_config(db, task.project_id)
        context = _skill_context(task, state["strategy"], model_config)
        cases = list(state.get("current_cases") or [])
        for skill_name in specialist_skills:
            task.stage = f"生成专项用例（{skill_name}）：{(state.get('current_feature') or {}).get('feature', '')}"
            db.commit()
            try:
                result = await get_registry().run(
                    skill_name,
                    {
                        "feature_item": state["current_feature"],
                        "scope": state.get("scope"),
                        "knowledge": state.get("knowledge") or [],
                    },
                    context,
                )
            except OutputParserException as exc:
                return _structured_output_failure(state, exc)
            cases.extend(result.get("cases") or [])
        return {"current_cases": cases, "generation_error": ""}
    finally:
        db.close()


async def validate_cases(state: GenerationState) -> dict:
    normalized_cases = []
    for case in state.get("current_cases") or []:
        if not isinstance(case, dict):
            continue
        steps_text, steps_list = normalize_steps(case)
        if not is_meaningful_case(case, steps_list):
            continue
        quality_status, quality_issues = check_case({**case, "steps": steps_list})
        normalized_cases.append(
            {
                "title": (case.get("title") or "").strip(),
                "priority": case.get("priority", "P2"),
                "case_type": case.get("case_type", "functional"),
                "is_smoke": bool(case.get("is_smoke", False)),
                "precondition": (case.get("precondition") or "").strip(),
                "steps": steps_text,
                "expected_result": (case.get("expected_result") or "").strip(),
                "quality_status": quality_status,
                "quality_issues": json.dumps(quality_issues, ensure_ascii=False),
                "skill_name": case.get("skill_name", ""),
            }
        )
    return {"current_cases": normalized_cases}


async def retry_feature(state: GenerationState) -> dict:
    retry_count = state.get("retry_count", 0) + 1
    db = SessionLocal()
    try:
        task = _task_or_raise(db, state["task_id"])
        task.stage = f"结构校验失败，重新生成（{retry_count}/1）"
        db.commit()
    finally:
        db.close()
    return {"retry_count": retry_count, "current_cases": [], "generation_error": ""}


async def persist_feature_cases(state: GenerationState) -> dict:
    db = SessionLocal()
    try:
        task = _task_or_raise(db, state["task_id"])
        item_id = state["current_feature_id"]
        for index, case in enumerate(state.get("current_cases") or []):
            skill_name = case.get("skill_name", "")
            generation_key = f"{task.id}:{item_id}:{skill_name}:{index}"
            draft = (
                db.query(GeneratedCaseDraft)
                .filter(GeneratedCaseDraft.generation_key == generation_key)
                .first()
            )
            if draft is None:
                draft = GeneratedCaseDraft(
                    task_id=task.id,
                    requirement_item_id=item_id,
                    generation_key=generation_key,
                )
                db.add(draft)
            draft.title = case["title"]
            draft.priority = case["priority"]
            draft.case_type = case["case_type"]
            draft.is_smoke = case["is_smoke"]
            draft.precondition = case["precondition"]
            draft.steps = case["steps"]
            draft.expected_result = case["expected_result"]
            draft.quality_status = case["quality_status"]
            draft.quality_issues = case["quality_issues"]
            draft.skill_name = skill_name

        next_index = state["feature_index"] + 1
        task.progress = int(next_index / len(state["feature_ids"]) * 80)
        db.commit()
        return {"feature_index": next_index, "current_cases": []}
    finally:
        db.close()


async def detect_task_duplicates(state: GenerationState) -> dict:
    db = SessionLocal()
    try:
        task = _task_or_raise(db, state["task_id"])
        task.stage = "重复检测"
        task.progress = 85
        drafts = db.query(GeneratedCaseDraft).filter(GeneratedCaseDraft.task_id == task.id).all()
        duplicate_count = detect_duplicates(drafts)
        db.commit()
        return {"duplicate_count": duplicate_count}
    finally:
        db.close()


async def run_task_judge(state: GenerationState) -> dict:
    # 延迟导入，避免 generation_service 的兼容门面与 Graph 模块循环依赖。
    from app.services.generation_service import run_judge_for_task

    db = SessionLocal()
    try:
        task = _task_or_raise(db, state["task_id"])
        model_config = get_project_runtime_config(db, task.project_id)
        await run_judge_for_task(db, task, model_config)
        return {}
    finally:
        db.close()


async def build_task_report(state: GenerationState) -> dict:
    db = SessionLocal()
    try:
        task = _task_or_raise(db, state["task_id"])
        task.stage = "生成质检报告"
        task.progress = 95
        items = (
            db.query(RequirementItem)
            .filter(RequirementItem.id.in_(state["feature_ids"]))
            .order_by(RequirementItem.sort_order)
            .all()
        )
        drafts = db.query(GeneratedCaseDraft).filter(GeneratedCaseDraft.task_id == task.id).all()
        item_case_map: dict[int, list[GeneratedCaseDraft]] = {}
        for draft in drafts:
            item_case_map.setdefault(draft.requirement_item_id, []).append(draft)
        report_data = build_quality_report(
            drafts,
            items,
            item_case_map,
            state.get("duplicate_count", 0),
        )
        existing = db.query(QualityReport).filter(QualityReport.task_id == task.id).first()
        if existing:
            db.delete(existing)
        db.add(QualityReport(task_id=task.id, **report_data))
        refs = state.get("knowledge_refs") or {}
        task.knowledge_refs = json.dumps(refs, ensure_ascii=False) if refs else ""
        db.commit()
        return {}
    finally:
        db.close()


async def finalize_task(state: GenerationState) -> dict:
    db = SessionLocal()
    try:
        task = _task_or_raise(db, state["task_id"])
        task.status = "completed"
        task.progress = 100
        task.stage = ""
        task.error_message = ""
        db.commit()
        return {}
    finally:
        db.close()


def route_after_generation(state: GenerationState) -> str:
    if not state.get("generation_error"):
        return "continue"
    return "retry"


def route_after_validation(state: GenerationState) -> str:
    if state.get("current_cases") or state.get("retry_count", 0) >= 1:
        return "persist"
    return "retry"


def route_next_feature(state: GenerationState) -> str:
    if state["feature_index"] < len(state["feature_ids"]):
        return "next"
    return "quality"
