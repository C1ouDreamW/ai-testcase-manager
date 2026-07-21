from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DesignAsset(Base):
    __tablename__ = "design_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_documents.id"), nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)  # image / figma
    title: Mapped[str] = mapped_column(String(200), default="")
    filename: Mapped[str] = mapped_column(String(255), default="")
    content_type: Mapped[str] = mapped_column(String(100), default="")
    storage_path: Mapped[str] = mapped_column(String(500), default="")
    figma_url: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    error_message: Mapped[str] = mapped_column(Text, default="")
    # 解析结果来源：mock 或 vision:{模型名}，用于区分示例数据与真实视觉模型输出
    parse_source: Mapped[str] = mapped_column(String(120), default="")
    # 视觉模型对图片内容的客观描述；非设计稿时用于友好提示
    image_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="design_assets")
    document: Mapped["RequirementDocument"] = relationship(back_populates="design_assets")
    insights: Mapped[list["DesignInsight"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        order_by="DesignInsight.sort_order",
    )


class DesignInsight(Base):
    __tablename__ = "design_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("design_assets.id"), nullable=False, index=True)
    page: Mapped[str] = mapped_column(String(200), default="")
    module: Mapped[str] = mapped_column(String(100), default="")
    feature: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    acceptance_criteria: Mapped[str] = mapped_column(Text, default="")
    constraints: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(10), default="P1")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    selected: Mapped[bool] = mapped_column(default=True)
    merged: Mapped[bool] = mapped_column(default=False)

    asset: Mapped["DesignAsset"] = relationship(back_populates="insights")
