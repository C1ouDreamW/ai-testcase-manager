import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator


class RequirementFeature(BaseModel):
    model_config = ConfigDict(extra="ignore")

    module: str = ""
    feature: str = ""
    description: str = ""
    acceptance_criteria: str = ""
    constraints: str = ""
    priority: str = "P1"


class RequirementFeatureBatch(RootModel[list[RequirementFeature]]):
    pass


class DesignFeature(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page: str = ""
    module: str = ""
    feature: str = ""
    description: str = ""
    acceptance_criteria: str = ""
    constraints: str = ""
    priority: str = "P1"


class DesignFeatureBatch(RootModel[list[DesignFeature]]):
    pass


class DesignParseResult(BaseModel):
    """视觉解析结果：先判定是否产品设计稿，再给出功能点。"""

    model_config = ConfigDict(extra="ignore")

    is_design: bool = True
    image_summary: str = ""  # 对图片内容的一句话客观描述
    features: list[DesignFeature] = Field(default_factory=list)


class GeneratedTestCase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    priority: str = "P2"
    case_type: str = "functional"
    is_smoke: bool = False
    precondition: str = ""
    steps: list[str] = Field(default_factory=list)
    expected_result: str = ""

    @field_validator("steps", mode="before")
    @classmethod
    def normalize_steps(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return [line.strip() for line in text.splitlines() if line.strip()]
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
            return [str(parsed)]
        return []


class GeneratedCaseBatch(RootModel[list[GeneratedTestCase]]):
    pass


class TestProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    in_scope: list[str] = Field(default_factory=list)
    out_scope: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class CaseJudgement(BaseModel):
    model_config = ConfigDict(extra="ignore")

    index: int
    relevance: int = 3
    executability: int = 3
    verifiability: int = 3
    hallucination: bool = False
    hallucination_reason: str = ""
    comment: str = ""


class CaseJudgementBatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    judgements: list[CaseJudgement] = Field(default_factory=list)


class CoverageDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    covered_indexes: list[int] = Field(default_factory=list)
