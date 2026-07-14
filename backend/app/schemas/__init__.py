from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectStatsOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    testcase_count: int = 0
    generation_count: int = 0
    last_generation_at: datetime | None = None
    last_generation_status: str | None = None


class HomeOverviewOut(BaseModel):
    total_projects: int
    total_testcases: int
    total_generations: int
    projects: list[ProjectStatsOut]
    latest_active_project_id: int | None = None


class StrategyOut(BaseModel):
    key: str
    title: str
    description: str = ""
    min_cases_per_feature: int = 2
    max_cases_per_feature: int = 4
    recommended: bool = False


class SkillOut(BaseModel):
    name: str
    version: str
    title: str
    description: str
    category: str
    stage: str
    tags: list[str] = []
    selectable: bool = False
    group: str | None = None
    icon: str | None = None


class SkillCatalogOut(BaseModel):
    core: list[SkillOut] = []
    specialist: list[SkillOut] = []
    strategies: list[StrategyOut] = []


class RequirementDocumentCreate(BaseModel):
    title: str
    content: str


class RequirementItemOut(BaseModel):
    id: int
    module: str
    feature: str
    description: str
    acceptance_criteria: str
    constraints: str
    priority: str
    sort_order: int
    confirmed: bool

    model_config = {"from_attributes": True}


class RequirementItemUpdate(BaseModel):
    module: str | None = None
    feature: str | None = None
    description: str | None = None
    acceptance_criteria: str | None = None
    constraints: str | None = None
    priority: str | None = None
    confirmed: bool | None = None


class RequirementItemCreate(BaseModel):
    module: str = ""
    feature: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    acceptance_criteria: str = ""
    constraints: str = ""
    priority: str = "P1"


class RequirementDocumentOut(BaseModel):
    id: int
    project_id: int
    title: str
    source_type: str
    status: str
    test_scope: str = ""
    created_at: datetime
    items: list[RequirementItemOut] = []

    model_config = {"from_attributes": True}


class TestScopeUpdate(BaseModel):
    test_scope: str = ""


class GenerationTaskCreate(BaseModel):
    document_id: int
    strategy: str = "full"  # full | quick
    specialist_skills: list[str] = Field(
        default_factory=list,
        description="可选专项 Skill：security（安全/权限）、api_test（接口测试）",
    )
    use_knowledge: bool = False  # 生成前检索项目知识库并注入 prompt（RAG）


class KnowledgeDocumentCreate(BaseModel):
    title: str
    content: str
    source_type: str = "doc"  # doc | case | defect


class KnowledgeDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    source_type: str
    status: str
    error_message: str = ""
    chunk_count: int = 0
    created_at: datetime


class KnowledgeChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    heading: str = ""


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class KnowledgeSearchHit(BaseModel):
    content: str
    title: str = ""
    heading: str = ""
    source_type: str = "doc"
    score: float = 0.0


class GeneratedCaseDraftOut(BaseModel):
    id: int
    requirement_item_id: int | None
    title: str
    priority: str
    case_type: str
    is_smoke: bool = False
    precondition: str
    steps: str
    expected_result: str
    quality_status: str
    quality_issues: str
    review_status: str
    reject_reason: str = ""
    was_edited: bool = False
    skill_name: str
    judge_score: float | None = None
    judge_issues: str = ""

    model_config = {"from_attributes": True}


class QualityReportOut(BaseModel):
    id: int
    total_cases: int
    pass_count: int
    warning_count: int
    fail_count: int
    coverage_rate: float
    uncovered_features: str
    suggestions: str
    avg_judge_score: float | None = None
    hallucination_count: int = 0
    duplicate_count: int = 0

    model_config = {"from_attributes": True}


class ReviewStatsOut(BaseModel):
    total: int = 0
    adopted: int = 0
    rejected: int = 0
    edited_adopted: int = 0
    pending: int = 0
    reviewed: bool = False
    adoption_rate: float = 0.0
    edit_rate: float = 0.0
    rejection_rate: float = 0.0


class GenerationTaskOut(BaseModel):
    id: int
    project_id: int
    document_id: int
    strategy: str
    strategy_config: str = ""
    status: str
    progress: int
    stage: str = ""
    error_message: str
    tokens_used: int = 0
    knowledge_refs: str = ""  # JSON: {item_id: [{title, heading, score}]}，RAG 溯源
    created_at: datetime
    updated_at: datetime
    drafts: list[GeneratedCaseDraftOut] = []
    quality_report: QualityReportOut | None = None
    review_stats: ReviewStatsOut | None = None

    model_config = {"from_attributes": True}


class GenerationTaskSummaryOut(BaseModel):
    """生成记录列表项：不含草稿明细的轻量视图。"""

    id: int
    document_id: int
    document_title: str = ""
    strategy: str
    specialist_skills: list[str] = []
    status: str
    progress: int
    error_message: str = ""
    tokens_used: int = 0
    created_at: datetime
    draft_count: int = 0
    smoke_count: int = 0
    coverage_rate: float | None = None
    review_stats: ReviewStatsOut | None = None


class ConfirmRequest(BaseModel):
    item_ids: list[int] | None = None


class ReviewAction(BaseModel):
    draft_ids: list[int]
    action: str  # adopt, reject
    reject_reason: str = ""  # 驳回原因（badcase 归因用）


class DraftEdit(BaseModel):
    title: str | None = None
    priority: str | None = None
    case_type: str | None = None
    precondition: str | None = None
    steps: str | None = None
    expected_result: str | None = None


class TestCaseUpdate(BaseModel):
    title: str | None = None
    priority: str | None = None
    case_type: str | None = None
    precondition: str | None = None
    steps: str | None = None
    expected_result: str | None = None
    module: str | None = None
    feature: str | None = None


class CatalogRename(BaseModel):
    type: Literal["module", "feature"]
    old_module: str = Field(..., min_length=1)
    old_feature: str | None = None
    new_name: str = Field(..., min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_feature_rename(self):
        """校验功能点重命名请求：重命名功能点时必须提供 old_feature。

        Returns:
            CatalogRename: 校验通过后的自身实例。

        Raises:
            ValueError: 重命名功能点但未提供 old_feature 时抛出。
        """
        if self.type == "feature" and not self.old_feature:
            raise ValueError("重命名功能点需提供 old_feature")
        return self


class CatalogRenameOut(BaseModel):
    updated_items: int


class TestCaseOut(BaseModel):
    id: int
    project_id: int
    project_name: str = ""
    title: str
    priority: str
    case_type: str
    is_smoke: bool = False
    precondition: str
    steps: str
    expected_result: str
    status: str
    source: str
    created_at: datetime
    module: str = ""
    feature: str = ""

    model_config = {"from_attributes": True}


class SystemSettingsOut(BaseModel):
    llm_api_key_set: bool
    llm_api_key_masked: str
    llm_base_url: str
    llm_model: str
    llm_mock_mode: bool
    use_mock_llm: bool
    eval_llm_api_key_set: bool = False
    eval_llm_api_key_masked: str = ""
    eval_llm_base_url: str = ""
    eval_llm_model: str = ""
    embedding_api_key_set: bool = False
    embedding_api_key_masked: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""


class SystemSettingsUpdate(BaseModel):
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_mock_mode: bool | None = None
    eval_llm_api_key: str | None = None
    eval_llm_base_url: str | None = None
    eval_llm_model: str | None = None
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str | None = None


# ---------- 评测 ----------

class EvalCheckpoint(BaseModel):
    text: str
    keywords: list[str] = []


class EvalSampleCreate(BaseModel):
    title: str
    content: str
    checkpoints: list[EvalCheckpoint] = []


class EvalSampleUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    checkpoints: list[EvalCheckpoint] | None = None


class EvalSampleOut(BaseModel):
    id: int
    project_id: int
    title: str
    content: str
    checkpoints: list[EvalCheckpoint] = []
    created_at: datetime


class EvalRunCreate(BaseModel):
    label: str
    sample_ids: list[int]
    strategy: str = "full"


class EvalResultOut(BaseModel):
    id: int
    sample_id: int
    sample_title: str = ""
    task_id: int | None = None
    status: str
    metrics: dict = {}


class EvalRunOut(BaseModel):
    id: int
    project_id: int
    label: str
    config: dict = {}
    status: str
    progress: int
    stage: str = ""
    error_message: str = ""
    metrics: dict = {}
    created_at: datetime
    results: list[EvalResultOut] = []
