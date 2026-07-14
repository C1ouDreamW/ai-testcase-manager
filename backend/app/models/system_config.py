from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

CONFIG_ID = 1


class SystemConfig(Base):
    """运行时配置"""

    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=CONFIG_ID)
    # 用例生成模型
    llm_api_key: Mapped[str] = mapped_column(String(500), default="")
    llm_base_url: Mapped[str] = mapped_column(
        String(500), default="https://api.deepseek.com/v1"
    )
    llm_model: Mapped[str] = mapped_column(String(100), default="deepseek-v4-flash")
    llm_mock_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    # 评测专用 LLM
    eval_llm_api_key: Mapped[str] = mapped_column(String(500), default="")
    eval_llm_base_url: Mapped[str] = mapped_column(String(500), default="")
    eval_llm_model: Mapped[str] = mapped_column(String(100), default="")
    # Embedding 模型
    embedding_api_key: Mapped[str] = mapped_column(String(500), default="")
    embedding_base_url: Mapped[str] = mapped_column(String(500), default="")
    embedding_model: Mapped[str] = mapped_column(String(100), default="")
