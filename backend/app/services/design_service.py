"""设计稿解析与合并：供 designs API 与 Agent 工具共用。"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.design import DesignAsset, DesignInsight
from app.models.requirement import RequirementDocument, RequirementItem
from app.services.design_storage import design_root
from app.services.settings_service import get_project_runtime_config
from app.skills.base import SkillContext
from app.skills.registry import get_registry


def feature_key(module: str, feature: str) -> tuple[str, str]:
    return (
        " ".join((module or "").lower().split()),
        " ".join((feature or "").lower().split()),
    )


def get_document(db: Session, project_id: int, document_id: int) -> RequirementDocument:
    document = (
        db.query(RequirementDocument)
        .filter(
            RequirementDocument.id == document_id,
            RequirementDocument.project_id == project_id,
        )
        .first()
    )
    if not document:
        raise HTTPException(404, "需求文档不存在")
    return document


def get_asset(db: Session, project_id: int, asset_id: int) -> DesignAsset:
    asset = (
        db.query(DesignAsset)
        .options(joinedload(DesignAsset.insights))
        .filter(DesignAsset.id == asset_id, DesignAsset.project_id == project_id)
        .first()
    )
    if not asset:
        raise HTTPException(404, "设计稿不存在")
    return asset


def safe_asset_path(asset: DesignAsset) -> Path:
    root = design_root()
    path = (root / asset.storage_path).resolve()
    if root not in path.parents:
        raise HTTPException(404, "设计稿文件不存在")
    return path


def list_assets(db: Session, project_id: int, document_id: int) -> list[DesignAsset]:
    get_document(db, project_id, document_id)
    return (
        db.query(DesignAsset)
        .options(joinedload(DesignAsset.insights))
        .filter(
            DesignAsset.project_id == project_id,
            DesignAsset.document_id == document_id,
        )
        .order_by(DesignAsset.created_at, DesignAsset.id)
        .all()
    )


def insight_to_dict(insight: DesignInsight) -> dict:
    return {
        "id": insight.id,
        "asset_id": insight.asset_id,
        "page": insight.page,
        "module": insight.module,
        "feature": insight.feature,
        "description": insight.description,
        "acceptance_criteria": insight.acceptance_criteria,
        "constraints": insight.constraints,
        "priority": insight.priority,
        "selected": insight.selected,
        "merged": insight.merged,
        "sort_order": insight.sort_order,
    }


def source_note(parse_source: str) -> str:
    """把 parse_source 翻译成给用户看的来源说明。"""
    if not parse_source:
        return "来源未知（该解析结果早于来源标记功能，建议重新解析确认）"
    if parse_source == "mock":
        return "Mock 示例数据，未调用视觉模型；请先在「设置」页配置视觉模型再重新解析"
    if parse_source.startswith("vision:"):
        return (
            f"由视觉模型 {parse_source.split(':', 1)[1] or '（未记录模型名）'} 真实解析"
        )
    return parse_source


def asset_to_summary(asset: DesignAsset) -> dict:
    insights = list(asset.insights or [])
    return {
        "id": asset.id,
        "document_id": asset.document_id,
        "asset_type": asset.asset_type,
        "title": asset.title,
        "filename": asset.filename,
        "figma_url": asset.figma_url,
        "status": asset.status,
        "error_message": asset.error_message,
        "parse_source": asset.parse_source or "",
        "is_mock_result": asset.parse_source == "mock",
        "source_note": source_note(asset.parse_source or ""),
        "is_design": asset.status != "not_design",
        "image_summary": asset.image_summary or "",
        "insight_count": len(insights),
        "unmerged_count": sum(1 for i in insights if not i.merged),
        "insights": [insight_to_dict(i) for i in insights],
    }


async def parse_asset(db: Session, project_id: int, asset_id: int) -> DesignAsset:
    """解析图片设计稿，写入 DesignInsight；Figma 链接不可直接解析。

    视觉解析与生成模型 Mock 解耦：已配置视觉模型时一律真实调用；
    仅未配置视觉且开启 LLM Mock 时才返回示例数据，并写入 parse_source 供上层展示。
    """
    asset = get_asset(db, project_id, asset_id)
    if asset.asset_type != "image":
        raise HTTPException(400, "Figma 链接首版不支持自动解析，请上传对应页面截图")
    path = safe_asset_path(asset)
    if not path.is_file():
        raise HTTPException(404, "设计稿文件不存在")

    config = get_project_runtime_config(db, project_id)
    use_mock = not config.vision_configured and config.use_mock_llm
    if not config.vision_configured and not config.use_mock_llm:
        raise HTTPException(400, "尚未配置视觉模型，请先到「设置」页完成配置")

    asset.status = "parsing"
    asset.error_message = ""
    asset.parse_source = ""
    asset.image_summary = ""
    db.commit()
    try:
        result = await get_registry().run(
            "design_parser",
            {"image_data": path.read_bytes(), "content_type": asset.content_type},
            SkillContext(
                model_config=config,
                project_id=project_id,
                use_mock=use_mock,
            ),
        )
        insights_data = result.get("insights") or []
        parse_source = str(result.get("source") or ("mock" if use_mock else ""))[:120]
        is_design = bool(result.get("is_design", True))
        image_summary = str(result.get("image_summary") or "")[:1000]
        db.query(DesignInsight).filter(DesignInsight.asset_id == asset.id).delete()
        # 非设计稿：不写功能点，标记 not_design，由上层友好提示
        if not is_design:
            asset.status = "not_design"
            asset.parse_source = parse_source
            asset.image_summary = image_summary
            db.commit()
            return get_asset(db, project_id, asset_id)
        for index, item in enumerate(insights_data):
            db.add(
                DesignInsight(
                    asset_id=asset.id,
                    page=str(item.get("page", ""))[:200],
                    module=str(item.get("module", ""))[:100],
                    feature=str(item.get("feature", ""))[:200]
                    or f"设计功能点 {index + 1}",
                    description=str(item.get("description", "")),
                    acceptance_criteria=str(item.get("acceptance_criteria", "")),
                    constraints=str(item.get("constraints", "")),
                    priority=item.get("priority")
                    if item.get("priority") in {"P0", "P1", "P2"}
                    else "P1",
                    sort_order=index,
                    selected=True,
                )
            )
        asset.status = "parsed"
        asset.parse_source = parse_source
        asset.image_summary = image_summary
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        failed_asset = db.get(DesignAsset, asset_id)
        if failed_asset:
            failed_asset.status = "failed"
            failed_asset.error_message = str(exc)[:1000]
            failed_asset.parse_source = ""
            db.commit()
        raise HTTPException(502, f"设计稿解析失败：{str(exc)[:300]}") from exc
    return get_asset(db, project_id, asset_id)


def merge_insights(
    db: Session,
    project_id: int,
    document_id: int,
    insight_ids: list[int] | None = None,
    *,
    selected_only: bool = True,
) -> dict:
    """将未合并的设计功能点写入需求文档，并回退确认状态。"""
    document = get_document(db, project_id, document_id)
    query = (
        db.query(DesignInsight)
        .join(DesignAsset)
        .filter(
            DesignAsset.project_id == project_id,
            DesignAsset.document_id == document_id,
            DesignInsight.merged == False,  # noqa: E712
        )
    )
    if insight_ids:
        query = query.filter(DesignInsight.id.in_(insight_ids))
    elif selected_only:
        query = query.filter(DesignInsight.selected == True)  # noqa: E712
    insights = query.order_by(DesignAsset.id, DesignInsight.sort_order).all()

    existing_items = (
        db.query(RequirementItem)
        .filter(RequirementItem.document_id == document_id)
        .order_by(RequirementItem.sort_order)
        .all()
    )
    existing_keys = {feature_key(item.module, item.feature) for item in existing_items}
    next_order = max((item.sort_order for item in existing_items), default=-1) + 1
    added = 0

    for insight in insights:
        key = feature_key(insight.module, insight.feature)
        if key not in existing_keys:
            db.add(
                RequirementItem(
                    document_id=document_id,
                    module=insight.module,
                    feature=insight.feature,
                    description=insight.description,
                    acceptance_criteria=insight.acceptance_criteria,
                    constraints=insight.constraints,
                    priority=insight.priority,
                    sort_order=next_order,
                    confirmed=False,
                    source_type="design",
                    source_ref_id=insight.asset_id,
                )
            )
            next_order += 1
            existing_keys.add(key)
            added += 1
        insight.merged = True

    if insights:
        document.status = "structured"
        db.query(RequirementItem).filter(
            RequirementItem.document_id == document_id
        ).update({"confirmed": False}, synchronize_session=False)
    db.commit()
    refreshed = (
        db.query(RequirementDocument)
        .options(joinedload(RequirementDocument.items))
        .filter(RequirementDocument.id == document_id)
        .first()
    )
    return {
        "document": refreshed,
        "merged_count": len(insights),
        "added_count": added,
        "document_status": refreshed.status if refreshed else document.status,
        "item_count": len(refreshed.items) if refreshed else 0,
    }
