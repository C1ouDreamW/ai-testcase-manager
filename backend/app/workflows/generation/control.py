"""生成工作流运行控制：安全暂停信号与运行租约。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.database import SessionLocal
from app.models.generation import GenerationTask


class GenerationPaused(Exception):
    """用户请求暂停后，在节点边界抛出，供 Runner 写入 paused 状态。"""


def new_run_lease() -> str:
    return uuid4().hex


def ensure_not_paused(task_id: int) -> None:
    """在节点入口检查暂停标记。

    若检测到 pause_requested（或无租约的 pausing），则标记 paused 并抛出 GenerationPaused。
    已完成 / 已失败的任务忽略暂停请求，避免覆盖终态。
    """
    db = SessionLocal()
    try:
        task = db.get(GenerationTask, task_id)
        if not task:
            raise RuntimeError("生成任务不存在")
        if task.status in ("completed", "failed"):
            return

        should_pause = bool(task.pause_requested) or (
            task.status == "pausing" and not (task.run_lease or "").strip()
        )
        if not should_pause:
            return

        task.status = "paused"
        task.stage = "已暂停"
        task.pause_requested = False
        task.run_lease = ""
        db.commit()
        raise GenerationPaused("生成任务已暂停")
    finally:
        db.close()


def claim_run_lease(db, task: GenerationTask, *, resume: bool = False) -> str:
    """通过条件更新抢占单一运行租约，阻止并发双跑。"""
    lease = new_run_lease()
    allowed = ("failed", "paused") if resume else ("pending",)
    current_lease = task.run_lease or ""
    updated = (
        db.query(GenerationTask)
        .filter(
            GenerationTask.id == task.id,
            GenerationTask.status.in_(allowed),
            GenerationTask.run_lease == current_lease,
        )
        .update(
            {
                "status": "generating",
                "run_lease": lease,
                "run_started_at": datetime.now(UTC).replace(tzinfo=None),
                "pause_requested": False,
                "error_message": "",
                "stage": "等待恢复" if resume else "准备中",
            },
            synchronize_session=False,
        )
    )
    db.commit()
    if not updated:
        raise RuntimeError("生成任务正在运行或状态已变更，无法启动")
    db.refresh(task)
    return lease


def clear_run_lease(task_id: int, lease: str | None = None) -> None:
    db = SessionLocal()
    try:
        task = db.get(GenerationTask, task_id)
        if not task:
            return
        if lease and task.run_lease and task.run_lease != lease:
            return
        task.run_lease = ""
        db.commit()
    finally:
        db.close()


def wrap_node(fn, *, skip_pause_check: bool = False):
    """包装 LangGraph 节点：在入口检查暂停标记。"""

    async def _wrapped(state):
        task_id = state.get("task_id")
        if task_id is not None and not skip_pause_check:
            ensure_not_paused(task_id)
        return await fn(state)

    _wrapped.__name__ = getattr(fn, "__name__", "wrapped_node")
    return _wrapped
