from typing import TypedDict


class GenerationState(TypedDict, total=False):
    """用例生成 Graph 的可持久化状态；只保存 ID 和普通数据。"""

    task_id: int
    project_id: int
    document_id: int
    feature_ids: list[int]
    feature_index: int
    current_feature_id: int | None
    current_feature: dict | None

    strategy: str
    specialist_skills: list[str]
    use_knowledge: bool
    scope: dict | None

    retrieval_query: str
    knowledge: list[dict]
    knowledge_refs: dict[str, list[dict]]
    current_cases: list[dict]

    retry_count: int
    generation_error: str
    duplicate_count: int

