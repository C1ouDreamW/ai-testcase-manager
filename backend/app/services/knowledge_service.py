"""知识库服务：分块、向量化入库、检索、删除。

向量存 ChromaDB（嵌入模式，本地文件），文本与元数据存 SQLite，两边用 chroma_id 对齐。
collection 按「项目 + embedding 模型」隔离，避免更换模型后新旧向量维度混杂。
"""

import hashlib
import os
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import BASE_DIR, settings
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.llm import embed_texts

# 支持环境变量覆盖，便于自动化测试隔离向量数据
CHROMA_DIR = Path(os.environ.get("AITC_CHROMA_DIR", "") or BASE_DIR / "data" / "chroma")

# 分块参数：每块目标 200~500 字，过长段落按句子切
MAX_CHUNK_CHARS = 500
MIN_CHUNK_CHARS = 20

# 检索参数
DEFAULT_TOP_K = 5
SIMILARITY_THRESHOLD = 0.35  # 余弦相似度低于该值的分块视为不相关，不注入

_client = None


def _get_client():
    """获取 ChromaDB 持久化客户端单例，首次调用时自动创建存储目录。

    Returns:
        chromadb.PersistentClient: ChromaDB 客户端实例。
    """
    global _client
    if _client is None:
        import chromadb

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def _embedding_configured() -> bool:
    """检查 Embedding 模型的 API 配置是否完整。

    Returns:
        bool: 配置完整返回 True。
    """
    return bool(settings.embedding_base_url and settings.embedding_api_key and settings.embedding_model)


def _use_pseudo_embedding() -> bool:
    """判断是否使用伪向量模式。

    mock 模式且未配置 embedding 时启用，使链路在离线开发时也可跑通。

    Returns:
        bool: 是否使用伪向量。
    """
    return settings.use_mock_llm and not _embedding_configured()


def _pseudo_embed(texts: list[str]) -> list[list[float]]:
    """基于字符 trigram 哈希生成确定性伪向量（64 维），仅供 mock 模式调试。

    Args:
        texts (list[str]): 待向量化的文本列表。

    Returns:
        list[list[float]]: 归一化的伪向量列表。
    """
    dim = 64
    result = []
    for text in texts:
        vec = [0.0] * dim
        for i in range(len(text) - 2):
            bucket = int(hashlib.md5(text[i:i + 3].encode()).hexdigest(), 16) % dim
            vec[bucket] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        result.append([v / norm for v in vec])
    return result


async def _embed(texts: list[str]) -> list[list[float]]:
    """批量向量化文本，mock 模式回退到伪向量，真实模式分批调用 API。

    Args:
        texts (list[str]): 待向量化的文本列表。

    Returns:
        list[list[float]]: 向量列表。
    """
    if _use_pseudo_embedding():
        return _pseudo_embed(texts)
    # 分批调用，避免单次请求过大（多数供应商限制 batch <= 64）
    vectors: list[list[float]] = []
    batch_size = 16
    for i in range(0, len(texts), batch_size):
        vectors.extend(await embed_texts(texts[i:i + batch_size]))
    return vectors


def _model_key() -> str:
    """生成当前 embedding 模型的唯一标识符，用于隔离不同模型的向量集合。

    Returns:
        str: 模型标识字符串（仅字母数字和下划线，最长 40 字符）。
    """
    model = settings.embedding_model if not _use_pseudo_embedding() else "mock"
    return re.sub(r"[^a-zA-Z0-9]", "_", model)[:40] or "default"


def _collection(project_id: int):
    """获取或创建项目对应的 ChromaDB 集合，按项目加模型隔离。

    Args:
        project_id (int): 项目 ID。

    Returns:
        chromadb.Collection: ChromaDB 集合对象。
    """
    name = f"p{project_id}_{_model_key()}"
    return _get_client().get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


# ---------- 分块 ----------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？；!?;\n])")


def _split_long_text(text: str) -> list[str]:
    """将超长文本按句子边界切割为不超过 MAX_CHUNK_CHARS 的片段。

    Args:
        text (str): 待切割的文本。

    Returns:
        list[str]: 文本片段列表。
    """
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    pieces, current = [], ""
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        if current and len(current) + len(sentence) > MAX_CHUNK_CHARS:
            pieces.append(current)
            current = sentence
        else:
            current += sentence
    if current.strip():
        pieces.append(current)
    return pieces


def chunk_markdown(text: str) -> list[dict]:
    """按 Markdown 标题层级分块，每块带标题路径。

    非 Markdown 的纯文本会整体按段落加句子切块（heading 为空）。

    Args:
        text (str): Markdown 文本。

    Returns:
        list[dict]: 分块列表，每项包含 content 和 heading 字段。
    """
    heading_stack: list[tuple[int, str]] = []  # [(level, title)]
    blocks: list[dict] = []
    buffer: list[str] = []

    def heading_path() -> str:
        return " > ".join(t for _, t in heading_stack)

    def flush():
        content = "\n".join(buffer).strip()
        buffer.clear()
        if len(content) < MIN_CHUNK_CHARS:
            return
        path = heading_path()
        for piece in _split_long_text(content):
            piece = piece.strip()
            if len(piece) >= MIN_CHUNK_CHARS:
                blocks.append({"content": piece, "heading": path})

    for line in text.split("\n"):
        match = _HEADING_RE.match(line.strip())
        if match:
            flush()
            level = len(match.group(1))
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, match.group(2).strip()))
        else:
            buffer.append(line)
    flush()
    return blocks


# ---------- 入库 / 删除 ----------

async def ingest_document(db: Session, doc: KnowledgeDocument) -> None:
    """分块、向量化并写入 ChromaDB 与 SQLite，失败时置为 failed 并记录原因。

    Args:
        db (Session): 数据库会话。
        doc (KnowledgeDocument): 知识库文档对象。

    Raises:
        Exception: 入库失败时重新抛出，文档状态已被标记为 failed。
    """
    try:
        chunks = chunk_markdown(doc.raw_content)
        if not chunks:
            raise ValueError("文档内容过短或无法分块")

        # 向量化时把标题路径拼进文本，提升检索区分度
        texts = [
            f"{c['heading']}\n{c['content']}" if c["heading"] else c["content"]
            for c in chunks
        ]
        vectors = await _embed(texts)

        collection = _collection(doc.project_id)
        ids = [f"doc{doc.id}_c{i}" for i in range(len(chunks))]
        collection.add(
            ids=ids,
            embeddings=vectors,
            documents=[c["content"] for c in chunks],
            metadatas=[
                {
                    "document_id": doc.id,
                    "title": doc.title,
                    "source_type": doc.source_type,
                    "heading": c["heading"],
                }
                for c in chunks
            ],
        )

        for i, c in enumerate(chunks):
            db.add(KnowledgeChunk(
                document_id=doc.id,
                content=c["content"],
                heading=c["heading"],
                chroma_id=ids[i],
            ))
        doc.status = "ready"
        doc.chunk_count = len(chunks)
        doc.error_message = ""
        db.commit()
    except Exception as exc:
        db.rollback()
        doc.status = "failed"
        doc.error_message = str(exc)[:500]
        db.commit()
        raise


def delete_document_vectors(doc: KnowledgeDocument) -> None:
    """从 ChromaDB 中删除文档对应的所有向量记录。

    清理失败不抛出异常，因为 collection 可能因更换模型而不存在。

    Args:
        doc (KnowledgeDocument): 知识库文档对象。
    """
    try:
        collection = _collection(doc.project_id)
        collection.delete(where={"document_id": doc.id})
    except Exception:
        pass  # 向量清理失败不阻塞文档删除（collection 可能因换模型而不存在）


# ---------- 检索 ----------

async def retrieve(
    db: Session,
    project_id: int,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """按查询文本检索项目知识库，返回相关分块及相似度。

    知识库为空或未命中时返回空列表，调用方按"无知识"继续，不应视为错误。

    Args:
        db (Session): 数据库会话。
        project_id (int): 项目 ID。
        query (str): 查询文本。
        top_k (int, optional): 返回的最大结果数。默认为 DEFAULT_TOP_K。
        threshold (float, optional): 相似度阈值，低于此值的分块不返回。默认为 SIMILARITY_THRESHOLD。

    Returns:
        list[dict]: 结果列表，每项包含 content、title、heading、source_type、score。
    """
    ready_count = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.project_id == project_id, KnowledgeDocument.status == "ready")
        .count()
    )
    if not ready_count:
        return []

    query_vector = (await _embed([query]))[0]
    collection = _collection(project_id)
    if collection.count() == 0:
        return []

    result = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for content, meta, distance in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        score = 1.0 - distance  # cosine distance → similarity
        if score < threshold:
            continue
        hits.append({
            "content": content,
            "title": (meta or {}).get("title", ""),
            "heading": (meta or {}).get("heading", ""),
            "source_type": (meta or {}).get("source_type", "doc"),
            "score": round(score, 3),
        })
    return hits


def has_ready_knowledge(db: Session, project_id: int) -> bool:
    """检查项目中是否有状态为 ready 的知识库文档。

    Args:
        db (Session): 数据库会话。
        project_id (int): 项目 ID。

    Returns:
        bool: 存在可用知识返回 True。
    """
    return (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.project_id == project_id, KnowledgeDocument.status == "ready")
        .count()
        > 0
    )
