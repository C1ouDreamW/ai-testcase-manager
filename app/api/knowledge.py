from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.project import Project
from app.schemas import (
    KnowledgeChunkOut,
    KnowledgeDocumentCreate,
    KnowledgeDocumentOut,
    KnowledgeSearchHit,
    KnowledgeSearchRequest,
)
from app.services.document_parser import DocumentParseError, parse_upload, title_from_filename
from app.services.knowledge_service import delete_document_vectors, ingest_document, retrieve

router = APIRouter(prefix="/projects/{project_id}/knowledge", tags=["knowledge"])


def _get_doc(db: Session, project_id: int, doc_id: int) -> KnowledgeDocument:
    """根据项目 ID 和文档 ID 查询知识文档，不存在时抛出 404 异常。

    Args:
        db (Session): 数据库会话。
        project_id (int): 项目 ID。
        doc_id (int): 文档 ID。

    Returns:
        KnowledgeDocument: 知识文档 ORM 对象。

    Raises:
        HTTPException: 文档不存在时抛出 404。
    """
    doc = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.id == doc_id, KnowledgeDocument.project_id == project_id)
        .first()
    )
    if not doc:
        raise HTTPException(404, "知识文档不存在")
    return doc


@router.get("", response_model=list[KnowledgeDocumentOut])
def list_documents(project_id: int, db: Session = Depends(get_db)):
    """列出项目下所有知识库文档，按创建时间降序排列。

    Args:
        project_id (int): 项目 ID。
        db (Session): 数据库会话。

    Returns:
        list[KnowledgeDocumentOut]: 知识文档列表。
    """
    return (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.project_id == project_id)
        .order_by(KnowledgeDocument.created_at.desc())
        .all()
    )


@router.post("", response_model=KnowledgeDocumentOut, status_code=201)
async def create_document(project_id: int, data: KnowledgeDocumentCreate, db: Session = Depends(get_db)):
    """创建文本形式的知识库文档并自动入库（分块 + 向量化）。

    Args:
        project_id (int): 项目 ID。
        data (KnowledgeDocumentCreate): 知识文档创建请求体。
        db (Session): 数据库会话。

    Returns:
        KnowledgeDocumentOut: 新创建的知识文档。

    Raises:
        HTTPException: 项目不存在或入库失败时返回 400/404。
    """
    if not db.get(Project, project_id):
        raise HTTPException(404, "项目不存在")

    doc = KnowledgeDocument(
        project_id=project_id,
        title=data.title[:200],
        source_type=data.source_type,
        raw_content=data.content,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    try:
        await ingest_document(db, doc)
    except Exception as exc:
        raise HTTPException(400, f"知识入库失败：{exc}") from exc
    db.refresh(doc)
    return doc


@router.post("/upload", response_model=KnowledgeDocumentOut, status_code=201)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    source_type: str = Form("doc"),
    db: Session = Depends(get_db),
):
    """上传文件作为知识库文档并自动入库（分块 + 向量化）。

    Args:
        project_id (int): 项目 ID。
        file (UploadFile): 上传的文件。
        title (str | None, optional): 自定义标题。默认为 None。
        source_type (str, optional): 来源类型（doc/case/defect）。默认为 "doc"。
        db (Session): 数据库会话。

    Returns:
        KnowledgeDocumentOut: 新创建的知识文档。

    Raises:
        HTTPException: 项目不存在、文件解析失败或入库失败时返回 400/404。
    """
    if not db.get(Project, project_id):
        raise HTTPException(404, "项目不存在")

    filename = file.filename or ""
    data = await file.read()
    try:
        content, _ = parse_upload(filename, data)
    except DocumentParseError as exc:
        raise HTTPException(400, str(exc)) from exc

    doc = KnowledgeDocument(
        project_id=project_id,
        title=(title or title_from_filename(filename) or "未命名知识")[:200],
        source_type=source_type,
        raw_content=content,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    try:
        await ingest_document(db, doc)
    except Exception as exc:
        raise HTTPException(400, f"知识入库失败：{exc}") from exc
    db.refresh(doc)
    return doc


@router.get("/{doc_id}/chunks", response_model=list[KnowledgeChunkOut])
def list_chunks(project_id: int, doc_id: int, db: Session = Depends(get_db)):
    """列出知识文档的所有分片。

    Args:
        project_id (int): 项目 ID。
        doc_id (int): 文档 ID。
        db (Session): 数据库会话。

    Returns:
        list[KnowledgeChunkOut]: 分片列表。

    Raises:
        HTTPException: 文档不存在时返回 404。
    """
    _get_doc(db, project_id, doc_id)
    return (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.document_id == doc_id)
        .order_by(KnowledgeChunk.id)
        .all()
    )


@router.delete("/{doc_id}", status_code=204)
def delete_document(project_id: int, doc_id: int, db: Session = Depends(get_db)):
    """删除知识文档及其在 ChromaDB 中的向量记录。

    Args:
        project_id (int): 项目 ID。
        doc_id (int): 文档 ID。
        db (Session): 数据库会话。

    Raises:
        HTTPException: 文档不存在时返回 404。
    """
    doc = _get_doc(db, project_id, doc_id)
    delete_document_vectors(doc)
    db.delete(doc)
    db.commit()


@router.post("/search", response_model=list[KnowledgeSearchHit])
async def search_knowledge(project_id: int, data: KnowledgeSearchRequest, db: Session = Depends(get_db)):
    """在项目知识库中按查询文本检索相关分块。

    Args:
        project_id (int): 项目 ID。
        data (KnowledgeSearchRequest): 检索请求体，指定 query 和 top_k。
        db (Session): 数据库会话。

    Returns:
        list[KnowledgeSearchHit]: 检索结果列表。

    Raises:
        HTTPException: Embedding 模型未配置时返回 400。
    """
    try:
        return await retrieve(db, project_id, data.query, top_k=data.top_k)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
