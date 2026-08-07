from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import require_project_access
from app.database import get_db
from app.models.design import DesignAsset, DesignInsight
from app.schemas import (
    DesignAssetOut,
    DesignInsightOut,
    DesignInsightUpdate,
    DesignMergeRequest,
    FigmaLinkCreate,
    RequirementDocumentOut,
)
from app.services import design_service
from app.services.design_storage import design_root


MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_IMAGES_PER_DOCUMENT = 8
router = APIRouter(
    prefix="/projects/{project_id}/designs",
    tags=["designs"],
    dependencies=[Depends(require_project_access)],
)


def _detect_image(data: bytes) -> tuple[str, str] | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp", "image/webp"
    return None


def _validate_figma_url(value: str) -> str:
    try:
        parsed = urlparse(value.strip())
    except ValueError as exc:
        raise HTTPException(400, "Figma 链接格式无效") from exc
    host = (parsed.hostname or "").lower()
    path_head = parsed.path.strip("/").split("/", 1)[0].lower()
    if parsed.scheme != "https" or host not in {"figma.com", "www.figma.com"}:
        raise HTTPException(400, "仅支持 https://www.figma.com 的链接")
    if path_head not in {"design", "file", "proto", "board"}:
        raise HTTPException(400, "请填写有效的 Figma 设计稿链接")
    return value.strip()


@router.get("", response_model=list[DesignAssetOut])
def list_designs(project_id: int, document_id: int, db: Session = Depends(get_db)):
    return design_service.list_assets(db, project_id, document_id)


@router.post("/upload", response_model=DesignAssetOut, status_code=201)
async def upload_design(
    project_id: int,
    document_id: int = Form(...),
    file: UploadFile = File(...),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
):
    design_service.get_document(db, project_id, document_id)
    image_count = db.query(DesignAsset).filter(
        DesignAsset.document_id == document_id,
        DesignAsset.asset_type == "image",
    ).count()
    if image_count >= MAX_IMAGES_PER_DOCUMENT:
        raise HTTPException(400, f"每份需求最多上传 {MAX_IMAGES_PER_DOCUMENT} 张设计稿")

    data = await file.read(MAX_IMAGE_SIZE + 1)
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(400, "单张设计稿不能超过 10MB")
    detected = _detect_image(data)
    if not detected:
        raise HTTPException(400, "仅支持真实的 PNG、JPG、WebP 图片")
    extension, content_type = detected
    declared_extension = Path(file.filename or "").suffix.lower()
    if declared_extension == ".jpeg":
        declared_extension = ".jpg"
    if declared_extension != extension:
        raise HTTPException(400, "文件扩展名与实际图片格式不一致")
    if (file.content_type or "").lower() != content_type:
        raise HTTPException(400, "文件 MIME 类型与实际图片格式不一致")

    relative_path = Path(str(project_id)) / str(document_id) / f"{uuid4().hex}{extension}"
    absolute_path = (design_root() / relative_path).resolve()
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(data)

    filename = (file.filename or f"design{extension}")[:255]
    asset = DesignAsset(
        project_id=project_id,
        document_id=document_id,
        asset_type="image",
        title=(title or Path(filename).stem or "未命名设计稿")[:200],
        filename=filename,
        content_type=content_type,
        storage_path=relative_path.as_posix(),
        status="uploaded",
    )
    try:
        db.add(asset)
        db.commit()
        db.refresh(asset)
    except Exception:
        db.rollback()
        absolute_path.unlink(missing_ok=True)
        raise
    return asset


@router.post("/figma", response_model=DesignAssetOut, status_code=201)
def add_figma_link(project_id: int, data: FigmaLinkCreate, db: Session = Depends(get_db)):
    design_service.get_document(db, project_id, data.document_id)
    url = _validate_figma_url(data.url)
    asset = DesignAsset(
        project_id=project_id,
        document_id=data.document_id,
        asset_type="figma",
        title=(data.title.strip() or "Figma 设计稿")[:200],
        figma_url=url,
        status="linked",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/{asset_id}/content")
def get_design_content(project_id: int, asset_id: int, db: Session = Depends(get_db)):
    asset = design_service.get_asset(db, project_id, asset_id)
    if asset.asset_type != "image" or not asset.storage_path:
        raise HTTPException(404, "设计稿文件不存在")
    path = design_service.safe_asset_path(asset)
    if not path.is_file():
        raise HTTPException(404, "设计稿文件不存在")
    return FileResponse(path, media_type=asset.content_type, filename=asset.filename)


@router.post("/{asset_id}/parse", response_model=DesignAssetOut)
async def parse_design(project_id: int, asset_id: int, db: Session = Depends(get_db)):
    return await design_service.parse_asset(db, project_id, asset_id)


@router.post("/merge", response_model=RequirementDocumentOut)
def merge_design_insights(
    project_id: int,
    document_id: int,
    data: DesignMergeRequest,
    db: Session = Depends(get_db),
):
    result = design_service.merge_insights(
        db, project_id, document_id, data.insight_ids or None,
    )
    return result["document"]


@router.patch("/insights/{insight_id}", response_model=DesignInsightOut)
def update_insight(
    project_id: int,
    insight_id: int,
    data: DesignInsightUpdate,
    db: Session = Depends(get_db),
):
    insight = (
        db.query(DesignInsight)
        .join(DesignAsset)
        .filter(DesignInsight.id == insight_id, DesignAsset.project_id == project_id)
        .first()
    )
    if not insight:
        raise HTTPException(404, "设计功能点不存在")
    if insight.merged:
        raise HTTPException(400, "已合并的设计功能点不能修改")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(insight, field, value)
    db.commit()
    db.refresh(insight)
    return insight


@router.delete("/{asset_id}", status_code=204)
def delete_design(project_id: int, asset_id: int, db: Session = Depends(get_db)):
    asset = design_service.get_asset(db, project_id, asset_id)
    if any(insight.merged for insight in asset.insights):
        raise HTTPException(400, "设计功能点已合并，不能删除其来源设计稿")
    path = design_service.safe_asset_path(asset) if asset.storage_path else None
    db.delete(asset)
    db.commit()
    if path:
        path.unlink(missing_ok=True)
