"""全局评测 API：评测衡量的是生成能力（Prompt / 模型 / RAG 策略），与具体业务项目无关。

所有样本与运行挂在一个自动创建的隐藏评测项目下（Project.is_eval=True），
生成链路无需改动，业务列表通过 is_eval 过滤不受影响。
"""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal, get_db
from app.models.evaluation import EvalResult, EvalRun, EvalSample
from app.models.generation import GenerationTask
from app.models.project import Project
from app.schemas import (
    EvalRunCreate,
    EvalRunOut,
    EvalResultOut,
    EvalSampleCreate,
    EvalSampleOut,
    EvalSampleUpdate,
    GenerationTaskOut,
)
from app.services.evaluation_service import run_evaluation

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

EVAL_PROJECT_NAME = "__evaluation__"


def _eval_project(db: Session) -> Project:
    """获取或创建评测专用隐藏项目（is_eval=True）。

    Args:
        db (Session): 数据库会话。

    Returns:
        Project: 评测专用项目对象。
    """
    project = db.query(Project).filter(Project.is_eval == True).first()
    if not project:
        project = Project(name=EVAL_PROJECT_NAME, description="评测专用隐藏项目", is_eval=True)
        db.add(project)
        db.commit()
        db.refresh(project)
    return project


def _sample_to_out(sample: EvalSample) -> EvalSampleOut:
    """将 EvalSample ORM 对象序列化为输出 Schema，解析检查点 JSON。

    Args:
        sample (EvalSample): 评测样本 ORM 对象。

    Returns:
        EvalSampleOut: 序列化后的样本输出。
    """
    try:
        checkpoints = json.loads(sample.checkpoints or "[]")
    except json.JSONDecodeError:
        checkpoints = []
    return EvalSampleOut(
        id=sample.id,
        project_id=sample.project_id,
        title=sample.title,
        content=sample.content,
        checkpoints=checkpoints,
        created_at=sample.created_at,
    )


def _parse_json(raw: str, fallback):
    """安全解析 JSON 字符串，解析失败或类型不匹配时返回回退值。

    Args:
        raw (str): JSON 字符串。
        fallback: 解析失败时的回退值。

    Returns:
        与 fallback 类型相同的解析结果或回退值。
    """
    try:
        data = json.loads(raw or "")
        return data if isinstance(data, type(fallback)) else fallback
    except json.JSONDecodeError:
        return fallback


def _run_to_out(run: EvalRun, sample_titles: dict[int, str]) -> EvalRunOut:
    """将 EvalRun ORM 对象序列化为输出 Schema，补入样本标题和配置/指标 JSON。

    Args:
        run (EvalRun): 评测运行 ORM 对象。
        sample_titles (dict[int, str]): 样本 ID 到标题的映射。

    Returns:
        EvalRunOut: 序列化后的评测运行输出。
    """
    return EvalRunOut(
        id=run.id,
        project_id=run.project_id,
        label=run.label,
        config=_parse_json(run.config, {}),
        status=run.status,
        progress=run.progress,
        stage=run.stage or "",
        error_message=run.error_message,
        metrics=_parse_json(run.metrics, {}),
        created_at=run.created_at,
        results=[
            EvalResultOut(
                id=r.id,
                sample_id=r.sample_id,
                sample_title=sample_titles.get(r.sample_id, ""),
                task_id=r.task_id,
                status=r.status,
                metrics=_parse_json(r.metrics, {}),
            )
            for r in run.results
        ],
    )


def _sample_titles(db: Session) -> dict[int, str]:
    """获取所有评测样本的 ID 到标题映射。

    Args:
        db (Session): 数据库会话。

    Returns:
        dict[int, str]: ID 到标题的映射字典。
    """
    return dict(db.query(EvalSample.id, EvalSample.title).all())


# ---------- 样本管理 ----------

@router.get("/samples", response_model=list[EvalSampleOut])
def list_samples(db: Session = Depends(get_db)):
    """列出所有评测样本。

    Args:
        db (Session): 数据库会话。

    Returns:
        list[EvalSampleOut]: 评测样本列表。
    """
    samples = db.query(EvalSample).order_by(EvalSample.created_at.desc()).all()
    return [_sample_to_out(s) for s in samples]


@router.post("/samples", response_model=EvalSampleOut, status_code=201)
def create_sample(data: EvalSampleCreate, db: Session = Depends(get_db)):
    """创建评测样本，保存需求内容和标准测试点。

    Args:
        data (EvalSampleCreate): 样本创建请求体。
        db (Session): 数据库会话。

    Returns:
        EvalSampleOut: 新创建的评测样本。

    Raises:
        HTTPException: 标题或需求内容为空时返回 400。
    """
    if not data.title.strip() or not data.content.strip():
        raise HTTPException(400, "标题和需求内容不能为空")

    sample = EvalSample(
        project_id=_eval_project(db).id,
        title=data.title.strip(),
        content=data.content,
        checkpoints=json.dumps([cp.model_dump() for cp in data.checkpoints], ensure_ascii=False),
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return _sample_to_out(sample)


@router.put("/samples/{sample_id}", response_model=EvalSampleOut)
def update_sample(sample_id: int, data: EvalSampleUpdate, db: Session = Depends(get_db)):
    """更新评测样本的标题、内容或标准测试点。

    Args:
        sample_id (int): 样本 ID。
        data (EvalSampleUpdate): 样本更新请求体。
        db (Session): 数据库会话。

    Returns:
        EvalSampleOut: 更新后的样本。

    Raises:
        HTTPException: 样本不存在时返回 404。
    """
    sample = db.query(EvalSample).get(sample_id)
    if not sample:
        raise HTTPException(404, "评测样本不存在")

    if data.title is not None:
        sample.title = data.title.strip()
    if data.content is not None:
        sample.content = data.content
    if data.checkpoints is not None:
        sample.checkpoints = json.dumps([cp.model_dump() for cp in data.checkpoints], ensure_ascii=False)
    db.commit()
    db.refresh(sample)
    return _sample_to_out(sample)


@router.delete("/samples/{sample_id}", status_code=204)
def delete_sample(sample_id: int, db: Session = Depends(get_db)):
    """删除评测样本，已被评测运行引用的样本不允许删除。

    Args:
        sample_id (int): 样本 ID。
        db (Session): 数据库会话。

    Raises:
        HTTPException: 样本不存在或已被引用时返回 400/404。
    """
    sample = db.query(EvalSample).get(sample_id)
    if not sample:
        raise HTTPException(404, "评测样本不存在")
    used = db.query(EvalResult).filter(EvalResult.sample_id == sample_id).count()
    if used:
        raise HTTPException(400, "该样本已被评测运行引用，不能删除")
    db.delete(sample)
    db.commit()


# ---------- 评测运行 ----------

async def _run_eval_background(run_id: int):
    """后台异步执行评测运行，使用独立数据库会话。

    Args:
        run_id (int): 评测运行 ID。
    """
    db = SessionLocal()
    try:
        await run_evaluation(db, run_id)
    finally:
        db.close()


@router.get("/runs", response_model=list[EvalRunOut])
def list_runs(db: Session = Depends(get_db)):
    """列出所有评测运行记录，包含各样本的结果。

    Args:
        db (Session): 数据库会话。

    Returns:
        list[EvalRunOut]: 评测运行列表。
    """
    runs = (
        db.query(EvalRun)
        .options(joinedload(EvalRun.results))
        .order_by(EvalRun.created_at.desc())
        .all()
    )
    titles = _sample_titles(db)
    return [_run_to_out(r, titles) for r in runs]


@router.post("/runs", response_model=EvalRunOut, status_code=201)
def create_run(
    data: EvalRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """创建评测运行，对选定样本走完整生成链路，提交到后台异步执行。

    Args:
        data (EvalRunCreate): 评测运行创建请求体。
        background_tasks (BackgroundTasks): FastAPI 后台任务管理器。
        db (Session): 数据库会话。

    Returns:
        EvalRunOut: 新创建的评测运行。

    Raises:
        HTTPException: 标签为空、无样本或已有评测正在运行时返回 400。
    """
    if not data.label.strip():
        raise HTTPException(400, "请填写运行标签（如 baseline）")
    samples = db.query(EvalSample).filter(EvalSample.id.in_(data.sample_ids)).all()
    if not samples:
        raise HTTPException(400, "请至少选择一个评测样本")

    running = db.query(EvalRun).filter(EvalRun.status.in_(["pending", "running"])).count()
    if running:
        raise HTTPException(400, "已有评测正在运行，请等待完成")

    run = EvalRun(
        project_id=_eval_project(db).id,
        label=data.label.strip(),
        config=json.dumps({"strategy": data.strategy}, ensure_ascii=False),
        status="pending",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    for sample in samples:
        db.add(EvalResult(run_id=run.id, sample_id=sample.id))
    db.commit()

    background_tasks.add_task(_run_eval_background, run.id)
    db.refresh(run)
    return _run_to_out(run, _sample_titles(db))


@router.get("/runs/{run_id}", response_model=EvalRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    """获取单个评测运行的详细结果。

    Args:
        run_id (int): 评测运行 ID。
        db (Session): 数据库会话。

    Returns:
        EvalRunOut: 评测运行详情。

    Raises:
        HTTPException: 评测运行不存在时返回 404。
    """
    run = (
        db.query(EvalRun)
        .options(joinedload(EvalRun.results))
        .filter(EvalRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(404, "评测运行不存在")
    return _run_to_out(run, _sample_titles(db))


@router.get("/tasks/{task_id}", response_model=GenerationTaskOut)
def get_eval_task(task_id: int, db: Session = Depends(get_db)):
    """获取评测样本对应生成任务的完整明细（用例、评分和质检报告）。

    Args:
        task_id (int): 生成任务 ID。
        db (Session): 数据库会话。

    Returns:
        GenerationTaskOut: 生成任务详情。

    Raises:
        HTTPException: 任务不存在时返回 404。
    """
    task = (
        db.query(GenerationTask)
        .options(joinedload(GenerationTask.drafts), joinedload(GenerationTask.quality_report))
        .filter(GenerationTask.id == task_id, GenerationTask.is_eval == True)
        .first()
    )
    if not task:
        raise HTTPException(404, "评测任务不存在")
    return task


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: int, db: Session = Depends(get_db)):
    """删除评测运行，正在运行中的不能删除。

    Args:
        run_id (int): 评测运行 ID。
        db (Session): 数据库会话。

    Raises:
        HTTPException: 评测运行不存在或正在运行时返回 400/404。
    """
    run = db.query(EvalRun).get(run_id)
    if not run:
        raise HTTPException(404, "评测运行不存在")
    if run.status == "running":
        raise HTTPException(400, "评测正在运行，不能删除")
    db.delete(run)
    db.commit()
