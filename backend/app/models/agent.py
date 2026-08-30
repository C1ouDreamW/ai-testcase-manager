from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentMessage(Base):
    """测试助手对话记录，按项目隔离。tool_calls 存 JSON 数组 [{name}]。"""

    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[str] = mapped_column(Text, default="")
    # 设计稿上下文：附件快照 JSON、目标需求、待确认 insight IDs
    attachments: Mapped[str] = mapped_column(Text, default="")  # JSON array
    document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pending_insight_ids: Mapped[str] = mapped_column(
        Text, default=""
    )  # JSON array of ints
    # 引用回复：指向同项目下被回复的消息 ID
    reply_to_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
