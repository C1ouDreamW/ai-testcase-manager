from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import evaluation, generation, knowledge, project, requirement, system_config, testcase  # noqa: F401
    from app.services.settings_service import load_config_to_runtime

    DATA_DIR.mkdir(exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_schema()

    db = SessionLocal()
    try:
        load_config_to_runtime(db)
    finally:
        db.close()


def _migrate_schema():
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.connect() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(generation_tasks)").fetchall()
        col_names = {row[1] for row in cols}
        if "strategy_config" not in col_names:
            conn.exec_driver_sql("ALTER TABLE generation_tasks ADD COLUMN strategy_config TEXT DEFAULT ''")
            conn.commit()
        if "tokens_used" not in col_names:
            conn.exec_driver_sql("ALTER TABLE generation_tasks ADD COLUMN tokens_used INTEGER DEFAULT 0")
            conn.commit()
        if "is_eval" not in col_names:
            conn.exec_driver_sql("ALTER TABLE generation_tasks ADD COLUMN is_eval BOOLEAN DEFAULT 0")
            conn.commit()
        if "stage" not in col_names:
            conn.exec_driver_sql("ALTER TABLE generation_tasks ADD COLUMN stage VARCHAR(100) DEFAULT ''")
            conn.commit()
        if "knowledge_refs" not in col_names:
            conn.exec_driver_sql("ALTER TABLE generation_tasks ADD COLUMN knowledge_refs TEXT DEFAULT ''")
            conn.commit()

        eval_run_tables = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='eval_runs'"
        ).fetchall()
        if eval_run_tables:
            eval_run_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(eval_runs)").fetchall()}
            if "stage" not in eval_run_cols:
                conn.exec_driver_sql("ALTER TABLE eval_runs ADD COLUMN stage VARCHAR(100) DEFAULT ''")
                conn.commit()

        draft_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(generated_case_drafts)").fetchall()}
        if "is_smoke" not in draft_cols:
            conn.exec_driver_sql("ALTER TABLE generated_case_drafts ADD COLUMN is_smoke BOOLEAN DEFAULT 0")
            conn.commit()
        if "was_edited" not in draft_cols:
            conn.exec_driver_sql("ALTER TABLE generated_case_drafts ADD COLUMN was_edited BOOLEAN DEFAULT 0")
            # 存量数据：当前状态为 edited 的草稿补标
            conn.exec_driver_sql("UPDATE generated_case_drafts SET was_edited = 1 WHERE review_status = 'edited'")
            conn.commit()
        for col, ddl in [
            ("reject_reason", "ALTER TABLE generated_case_drafts ADD COLUMN reject_reason VARCHAR(200) DEFAULT ''"),
            ("judge_score", "ALTER TABLE generated_case_drafts ADD COLUMN judge_score FLOAT"),
            ("judge_issues", "ALTER TABLE generated_case_drafts ADD COLUMN judge_issues TEXT DEFAULT ''"),
        ]:
            if col not in draft_cols:
                conn.exec_driver_sql(ddl)
                conn.commit()

        config_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(system_config)").fetchall()}
        for col, ddl in [
            ("eval_llm_api_key", "ALTER TABLE system_config ADD COLUMN eval_llm_api_key VARCHAR(500) DEFAULT ''"),
            ("eval_llm_base_url", "ALTER TABLE system_config ADD COLUMN eval_llm_base_url VARCHAR(500) DEFAULT ''"),
            ("eval_llm_model", "ALTER TABLE system_config ADD COLUMN eval_llm_model VARCHAR(100) DEFAULT ''"),
            ("embedding_api_key", "ALTER TABLE system_config ADD COLUMN embedding_api_key VARCHAR(500) DEFAULT ''"),
            ("embedding_base_url", "ALTER TABLE system_config ADD COLUMN embedding_base_url VARCHAR(500) DEFAULT ''"),
            ("embedding_model", "ALTER TABLE system_config ADD COLUMN embedding_model VARCHAR(100) DEFAULT ''"),
        ]:
            if config_cols and col not in config_cols:
                conn.exec_driver_sql(ddl)
                conn.commit()

        report_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(quality_reports)").fetchall()}
        for col, ddl in [
            ("avg_judge_score", "ALTER TABLE quality_reports ADD COLUMN avg_judge_score FLOAT"),
            ("hallucination_count", "ALTER TABLE quality_reports ADD COLUMN hallucination_count INTEGER DEFAULT 0"),
            ("duplicate_count", "ALTER TABLE quality_reports ADD COLUMN duplicate_count INTEGER DEFAULT 0"),
        ]:
            if col not in report_cols:
                conn.exec_driver_sql(ddl)
                conn.commit()

        tc_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(testcases)").fetchall()}
        if "is_smoke" not in tc_cols:
            conn.exec_driver_sql("ALTER TABLE testcases ADD COLUMN is_smoke BOOLEAN DEFAULT 0")
            conn.commit()

        project_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(projects)").fetchall()}
        if "is_eval" not in project_cols:
            conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN is_eval BOOLEAN DEFAULT 0")
            conn.commit()

        doc_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(requirement_documents)").fetchall()}
        if "test_scope" not in doc_cols:
            conn.exec_driver_sql("ALTER TABLE requirement_documents ADD COLUMN test_scope TEXT DEFAULT ''")
            conn.commit()
        if "is_eval" not in doc_cols:
            conn.exec_driver_sql("ALTER TABLE requirement_documents ADD COLUMN is_eval BOOLEAN DEFAULT 0")
            conn.commit()
