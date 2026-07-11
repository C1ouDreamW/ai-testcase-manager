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
    """FastAPI 依赖注入：创建数据库会话并在请求结束后自动关闭。

    Yields:
        Session: SQLAlchemy 数据库会话对象。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库，创建 data 目录和所有模型对应的表结构。"""
    from app.models import evaluation, generation, knowledge, project, requirement, system_config, testcase  # noqa: F401

    DATA_DIR.mkdir(exist_ok=True)
    Base.metadata.create_all(bind=engine)
