from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForRetrieverRun, CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field

from app.services.knowledge_service import DEFAULT_TOP_K, SIMILARITY_THRESHOLD, retrieve


class AITCHybridRetriever(BaseRetriever):
    """把 AITC 现有向量 + BM25 + RRF + Rerank 检索包装成 LangChain Retriever。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db: Any = Field(exclude=True)
    project_id: int
    runtime_config: Any = Field(default=None, exclude=True)
    top_k: int = DEFAULT_TOP_K
    threshold: float = SIMILARITY_THRESHOLD

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        raise RuntimeError("AITCHybridRetriever 仅支持异步调用，请使用 ainvoke()")

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: AsyncCallbackManagerForRetrieverRun,
    ) -> list[Document]:
        hits = await retrieve(
            self.db,
            self.project_id,
            query,
            top_k=self.top_k,
            threshold=self.threshold,
            model_config=self.runtime_config,
        )
        return [
            Document(
                page_content=hit.get("content", ""),
                metadata={key: value for key, value in hit.items() if key != "content"},
            )
            for hit in hits
        ]


def documents_to_knowledge(documents: list[Document]) -> list[dict]:
    """转回现有 Skill Prompt 使用的知识字典协议。"""
    return [{"content": doc.page_content, **doc.metadata} for doc in documents]

