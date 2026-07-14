from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.generation import GenerationTask
from app.models.project import Project
from app.models.testcase import TestCase


def get_home_overview(db: Session) -> dict:
    """获取首页概览数据，包含项目列表、用例和生成任务的统计信息。

    排除评测专用项目（is_eval=True），按更新时间降序排列，
    同时计算最近活跃的项目 ID。

    Args:
        db (Session): 数据库会话。

    Returns:
        dict: 包含 total_projects、total_testcases、total_generations、projects 和
            latest_active_project_id 的概览字典。
    """
    projects = (
        db.query(Project)
        .filter(~Project.is_eval)
        .order_by(Project.updated_at.desc())
        .all()
    )

    testcase_counts = dict(
        db.query(TestCase.project_id, func.count(TestCase.id))
        .group_by(TestCase.project_id)
        .all()
    )
    generation_counts = dict(
        db.query(GenerationTask.project_id, func.count(GenerationTask.id))
        .filter(~GenerationTask.is_eval)
        .group_by(GenerationTask.project_id)
        .all()
    )

    latest_subq = (
        db.query(
            GenerationTask.project_id,
            func.max(GenerationTask.id).label("latest_id"),
        )
        .filter(~GenerationTask.is_eval)
        .group_by(GenerationTask.project_id)
        .subquery()
    )
    latest_tasks = {
        task.project_id: task
        for task in db.query(GenerationTask)
        .join(latest_subq, GenerationTask.id == latest_subq.c.latest_id)
        .all()
    }

    project_items = []
    latest_active_project_id = None
    latest_active_at: datetime | None = None

    for project in projects:
        last_task = latest_tasks.get(project.id)
        last_at = last_task.created_at if last_task else None
        if last_at and (latest_active_at is None or last_at > latest_active_at):
            latest_active_at = last_at
            latest_active_project_id = project.id

        project_items.append(
            {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
                "testcase_count": testcase_counts.get(project.id, 0),
                "generation_count": generation_counts.get(project.id, 0),
                "last_generation_at": last_at,
                "last_generation_status": last_task.status if last_task else None,
            }
        )

    if latest_active_project_id is None and projects:
        latest_active_project_id = projects[0].id

    return {
        "total_projects": len(projects),
        "total_testcases": sum(testcase_counts.values()),
        "total_generations": sum(generation_counts.values()),
        "projects": project_items,
        "latest_active_project_id": latest_active_project_id,
    }
