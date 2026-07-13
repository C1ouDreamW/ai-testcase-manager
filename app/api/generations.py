from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal, get_db
from app.models.generation import GenerationTask
from app.models.project import Project
from app.models.requirement import RequirementDocument, RequirementItem
from app.schemas import (
    DraftEdit,
    GeneratedCaseDraftOut,
    GenerationTaskCreate,
    GenerationTaskOut,
    GenerationTaskSummaryOut,
    ReviewAction,
    TestCaseOut,
)
from app.services.generation_service import (
    adopt_drafts,
    build_strategy_config_payload,
    parse_strategy_config,
    reject_drafts,
    run_generation,
    run_judge_for_task,
)
from app.services.quality_checker import judge_summary
from app.services.testcase_export_service import export_testcases
from app.models.generation import GeneratedCaseDraft
from app.models.testcase import TestCase

router = APIRouter(prefix="/projects/{project_id}/generations", tags=["generations"])


async def _run_generation_task(task_id: int):
    """后台异步执行生成任务，使用独立数据库会话。

    Args:
        task_id (int): 生成任务 ID。
    """
    db = SessionLocal()
    try:
        task = db.query(GenerationTask).get(task_id)
        if task:
            await run_generation(db, task)
    finally:
        db.close()


@router.get("", response_model=list[GenerationTaskOut])
def list_tasks(project_id: int, db: Session = Depends(get_db)):
    """列出项目下所有生成任务，包含草稿和质检报告明细。

    Args:
        project_id (int): 项目 ID。
        db (Session): 数据库会话。

    Returns:
        list[GenerationTaskOut]: 生成任务列表。
    """
    return (
        db.query(GenerationTask)
        .options(joinedload(GenerationTask.drafts), joinedload(GenerationTask.quality_report))
        .filter(GenerationTask.project_id == project_id, GenerationTask.is_eval == False)
        .order_by(GenerationTask.created_at.desc())
        .all()
    )


@router.post("", response_model=GenerationTaskOut, status_code=201)
async def create_task(
    project_id: int,
    data: GenerationTaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """创建测试用例生成任务，提交到后台异步执行。

    Args:
        project_id (int): 项目 ID。
        data (GenerationTaskCreate): 生成任务创建请求体。
        background_tasks (BackgroundTasks): FastAPI 后台任务管理器。
        db (Session): 数据库会话。

    Returns:
        GenerationTaskOut: 新创建的生成任务。

    Raises:
        HTTPException: 项目不存在、需求文档不存在或功能点未确认时返回 400/404。
    """
    if not db.query(Project).get(project_id):
        raise HTTPException(404, "项目不存在")

    doc = (
        db.query(RequirementDocument)
        .filter(RequirementDocument.id == data.document_id, RequirementDocument.project_id == project_id)
        .first()
    )
    if not doc:
        raise HTTPException(404, "需求文档不存在")
    if doc.status != "confirmed":
        raise HTTPException(400, "请先确认功能点后再生成")

    task = GenerationTask(
        project_id=project_id,
        document_id=data.document_id,
        strategy=data.strategy,
        strategy_config=build_strategy_config_payload(data),
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    background_tasks.add_task(_run_generation_task, task.id)
    return task


@router.get("/summary", response_model=list[GenerationTaskSummaryOut])
def list_task_summaries(project_id: int, db: Session = Depends(get_db)):
    """生成任务列表（轻量视图），仅返回统计信息，不返回草稿明细。

    Args:
        project_id (int): 项目 ID。
        db (Session): 数据库会话。

    Returns:
        list[GenerationTaskSummaryOut]: 生成任务摘要列表。
    """
    tasks = (
        db.query(GenerationTask)
        .options(joinedload(GenerationTask.drafts), joinedload(GenerationTask.quality_report))
        .filter(GenerationTask.project_id == project_id, GenerationTask.is_eval == False)
        .order_by(GenerationTask.created_at.desc())
        .all()
    )

    doc_ids = {t.document_id for t in tasks}
    doc_titles = {}
    if doc_ids:
        for doc_id, title in (
            db.query(RequirementDocument.id, RequirementDocument.title)
            .filter(RequirementDocument.id.in_(doc_ids))
            .all()
        ):
            doc_titles[doc_id] = title

    result = []
    for t in tasks:
        config = parse_strategy_config(t)
        drafts = t.drafts or []
        result.append(
            GenerationTaskSummaryOut(
                id=t.id,
                document_id=t.document_id,
                document_title=doc_titles.get(t.document_id, ""),
                strategy=config["strategy"],
                specialist_skills=config["specialist_skills"],
                status=t.status,
                progress=t.progress,
                error_message=t.error_message,
                tokens_used=t.tokens_used or 0,
                created_at=t.created_at,
                draft_count=len(drafts),
                smoke_count=sum(1 for d in drafts if d.is_smoke),
                coverage_rate=t.quality_report.coverage_rate if t.quality_report else None,
                review_stats=t.review_stats,
            )
        )
    return result


@router.get("/{task_id}", response_model=GenerationTaskOut)
def get_task(project_id: int, task_id: int, db: Session = Depends(get_db)):
    """获取单个生成任务的完整明细，包含草稿和质检报告。

    Args:
        project_id (int): 项目 ID。
        task_id (int): 任务 ID。
        db (Session): 数据库会话。

    Returns:
        GenerationTaskOut: 生成任务详情。

    Raises:
        HTTPException: 任务不存在时返回 404。
    """
    task = (
        db.query(GenerationTask)
        .options(joinedload(GenerationTask.drafts), joinedload(GenerationTask.quality_report))
        .filter(GenerationTask.id == task_id, GenerationTask.project_id == project_id)
        .first()
    )
    if not task:
        raise HTTPException(404, "生成任务不存在")
    return task


@router.get("/{task_id}/export")
def export_drafts(
    project_id: int,
    task_id: int,
    format: str = "xlsx",
    smoke_only: bool = False,
    db: Session = Depends(get_db),
):
    """导出生成任务的测试用例草稿为 .xlsx 或 .md 文件。

    Args:
        project_id (int): 项目 ID。
        task_id (int): 任务 ID。
        format (str, optional): 导出格式，支持 "xlsx" 和 "md"。默认为 "xlsx"。
        smoke_only (bool, optional): 仅导出冒烟用例。默认为 False。
        db (Session): 数据库会话。

    Returns:
        StreamingResponse: 文件流响应。

    Raises:
        HTTPException: 任务不存在或没有可导出用例时返回 400/404。
    """
    task = (
        db.query(GenerationTask)
        .options(joinedload(GenerationTask.drafts))
        .filter(GenerationTask.id == task_id, GenerationTask.project_id == project_id)
        .first()
    )
    if not task:
        raise HTTPException(404, "生成任务不存在")

    drafts = list(task.drafts or [])
    if smoke_only:
        drafts = [d for d in drafts if d.is_smoke]
    if not drafts:
        raise HTTPException(400, "没有可导出的用例")

    item_ids = {d.requirement_item_id for d in drafts if d.requirement_item_id}
    items_map = {}
    if item_ids:
        for item in db.query(RequirementItem).filter(RequirementItem.id.in_(item_ids)).all():
            items_map[item.id] = item

    doc = db.get(RequirementDocument, task.document_id)
    doc_title = (doc.title if doc else "") or f"任务{task_id}"

    cases = []
    for d in drafts:
        item = items_map.get(d.requirement_item_id)
        cases.append({
            "id": d.id,
            "module": item.module if item else "",
            "feature": item.feature if item else "",
            "title": d.title,
            "priority": d.priority,
            "case_type": d.case_type,
            "is_smoke": d.is_smoke,
            "precondition": d.precondition,
            "steps": d.steps,
            "expected_result": d.expected_result,
            "review_status": d.review_status,
            "source": "ai_generated",
        })

    fmt = "md" if format == "md" else "xlsx"
    export_title = f"{doc_title}-生成任务{task_id}"
    content, media_type, ext = export_testcases(export_title, cases, fmt=fmt, include_review=True)
    suffix = "冒烟" if smoke_only else "用例"
    filename = f"{doc_title}-任务{task_id}-{suffix}.{ext}"
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(BytesIO(content), media_type=media_type, headers=headers)


@router.post("/{task_id}/review", response_model=list[TestCaseOut])
def review_drafts(project_id: int, task_id: int, data: ReviewAction, db: Session = Depends(get_db)):
    """批量采纳或驳回测试用例草稿。

    Args:
        project_id (int): 项目 ID。
        task_id (int): 任务 ID。
        data (ReviewAction): 评审操作请求体，指定 draft_ids 和 action（adopt/reject）。
        db (Session): 数据库会话。

    Returns:
        list[TestCaseOut]: 采纳操作返回新建的 TestCase 列表，驳回返回空列表。

    Raises:
        HTTPException: 无效操作时返回 400。
    """
    if data.action == "adopt":
        return adopt_drafts(db, task_id, data.draft_ids)
    if data.action == "reject":
        reject_drafts(db, task_id, data.draft_ids, data.reject_reason)
        return []
    raise HTTPException(400, "无效操作")


@router.post("/{task_id}/judge", response_model=GenerationTaskOut)
async def rejudge_task(project_id: int, task_id: int, db: Session = Depends(get_db)):
    """手动（重新）运行 AI Judge 评分，并刷新质检报告中的评分汇总。

    Args:
        project_id (int): 项目 ID。
        task_id (int): 任务 ID。
        db (Session): 数据库会话。

    Returns:
        GenerationTaskOut: 更新后的生成任务。

    Raises:
        HTTPException: 任务不存在或没有可评分的用例时返回 400/404。
    """
    task = (
        db.query(GenerationTask)
        .options(joinedload(GenerationTask.drafts), joinedload(GenerationTask.quality_report))
        .filter(GenerationTask.id == task_id, GenerationTask.project_id == project_id)
        .first()
    )
    if not task:
        raise HTTPException(404, "生成任务不存在")
    if not task.drafts:
        raise HTTPException(400, "该任务没有可评分的用例")

    await run_judge_for_task(db, task)

    if task.quality_report:
        avg_score, hallucination = judge_summary(list(task.drafts))
        task.quality_report.avg_judge_score = avg_score
        task.quality_report.hallucination_count = hallucination
        db.commit()

    db.refresh(task)
    return task


@router.patch("/{task_id}/drafts/{draft_id}", response_model=GeneratedCaseDraftOut)
def edit_draft(
    project_id: int,
    task_id: int,
    draft_id: int,
    data: DraftEdit,
    db: Session = Depends(get_db),
):
    """编辑单条候选用例草稿，标记为已编辑状态。

    Args:
        project_id (int): 项目 ID。
        task_id (int): 任务 ID。
        draft_id (int): 草稿 ID。
        data (DraftEdit): 草稿编辑请求体。
        db (Session): 数据库会话。

    Returns:
        GeneratedCaseDraftOut: 更新后的草稿。

    Raises:
        HTTPException: 草稿不存在时返回 404。
    """
    draft = (
        db.query(GeneratedCaseDraft)
        .filter(GeneratedCaseDraft.id == draft_id, GeneratedCaseDraft.task_id == task_id)
        .first()
    )
    if not draft:
        raise HTTPException(404, "候选用例不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(draft, field, value)
    draft.review_status = "edited"
    draft.was_edited = True
    db.commit()
    db.refresh(draft)
    return draft
