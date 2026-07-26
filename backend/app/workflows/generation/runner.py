from app.database import SessionLocal
from app.models.generation import GenerationTask
from app.services.llm import start_token_tracking, total_tokens
from app.workflows.generation.checkpoint import checkpoint_context
from app.workflows.generation.control import (
    GenerationPaused,
    claim_run_lease,
)
from app.workflows.generation.graph import build_generation_graph


def _accumulate_tokens(task: GenerationTask, token_counter) -> None:
    task.tokens_used = (task.tokens_used or 0) + total_tokens(token_counter)


async def run_generation_workflow(
    task_id: int,
    *,
    resume: bool = False,
    lease: str | None = None,
) -> None:
    """执行或恢复生成工作流，业务状态仍写回现有 GenerationTask。"""
    token_counter = start_token_tracking()
    config = {"configurable": {"thread_id": f"generation:{task_id}"}}
    active_lease = lease

    if not active_lease:
        db = SessionLocal()
        try:
            task = db.get(GenerationTask, task_id)
            if not task:
                raise RuntimeError("生成任务不存在")
            try:
                active_lease = claim_run_lease(db, task, resume=resume)
            except RuntimeError:
                # 已有并发运行占用租约，静默退出避免双跑
                return
        finally:
            db.close()

    try:
        async with checkpoint_context() as checkpointer:
            await checkpointer.setup()
            graph = build_generation_graph(checkpointer)
            inputs = None if resume else {"task_id": task_id}
            await graph.ainvoke(inputs, config=config)
    except GenerationPaused:
        db = SessionLocal()
        try:
            task = db.get(GenerationTask, task_id)
            if task:
                if task.status not in ("completed", "failed", "paused"):
                    task.status = "paused"
                    task.stage = "已暂停"
                    task.pause_requested = False
                _accumulate_tokens(task, token_counter)
                if not active_lease or (task.run_lease or "") in ("", active_lease):
                    task.run_lease = ""
                db.commit()
        finally:
            db.close()
        return
    except Exception as exc:
        db = SessionLocal()
        try:
            task = db.get(GenerationTask, task_id)
            if task:
                # 若暂停流程已写入 paused，不要被异常路径覆盖
                if task.status != "paused":
                    task.status = "failed"
                    task.error_message = str(exc)
                    task.stage = ""
                    task.pause_requested = False
                _accumulate_tokens(task, token_counter)
                if not active_lease or (task.run_lease or "") in ("", active_lease):
                    task.run_lease = ""
                db.commit()
        finally:
            db.close()
        raise
    else:
        db = SessionLocal()
        try:
            task = db.get(GenerationTask, task_id)
            if task:
                _accumulate_tokens(task, token_counter)
                # 完成后若仍有未消费的暂停请求，忽略之（终态优先）
                if task.status == "completed":
                    task.pause_requested = False
                if not active_lease or (task.run_lease or "") in ("", active_lease):
                    task.run_lease = ""
                db.commit()
        finally:
            db.close()


async def resume_generation_workflow(task_id: int, lease: str | None = None) -> None:
    await run_generation_workflow(task_id, resume=True, lease=lease)
