from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.schemas import HomeOverviewOut, ProjectCreate, ProjectOut, ProjectUpdate
from app.services.knowledge_service import delete_document_vectors
from app.services.project_service import get_home_overview

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/overview", response_model=HomeOverviewOut)
def get_overview(db: Session = Depends(get_db)):
    """获取首页概览数据，包含项目列表和用例、生成任务的统计信息。

    Args:
        db (Session): 数据库会话（由 FastAPI 依赖注入）。

    Returns:
        HomeOverviewOut: 首页概览响应。
    """
    return get_home_overview(db)


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    """列出所有业务项目，排除评测专用项目，按更新时间降序排列。

    Args:
        db (Session): 数据库会话。

    Returns:
        list[ProjectOut]: 项目列表。
    """
    return db.query(Project).filter(Project.is_eval == False).order_by(Project.updated_at.desc()).all()


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    """创建新项目。

    Args:
        data (ProjectCreate): 项目创建请求体。
        db (Session): 数据库会话。

    Returns:
        ProjectOut: 新创建的项目。
    """
    project = Project(name=data.name, description=data.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """根据 ID 获取单个项目详情。

    Args:
        project_id (int): 项目 ID。
        db (Session): 数据库会话。

    Returns:
        ProjectOut: 项目详情。

    Raises:
        HTTPException: 项目不存在时返回 404。
    """
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db)):
    """更新项目名称或描述，仅更新传入的非空字段。

    Args:
        project_id (int): 项目 ID。
        data (ProjectUpdate): 项目更新请求体。
        db (Session): 数据库会话。

    Returns:
        ProjectOut: 更新后的项目。

    Raises:
        HTTPException: 项目不存在时返回 404。
    """
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """删除项目及其关联数据，删除前先清理 ChromaDB 中的知识库向量。

    清理向量可防止 SQLite 复用主键时残留向量污染新项目的检索。

    Args:
        project_id (int): 项目 ID。
        db (Session): 数据库会话。

    Raises:
        HTTPException: 项目不存在时返回 404。
    """
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    # 先清理知识库向量，SQLite 复用主键时残留向量会污染新项目的检索
    for doc in project.knowledge_documents:
        delete_document_vectors(doc)
    db.delete(project)
    db.commit()
