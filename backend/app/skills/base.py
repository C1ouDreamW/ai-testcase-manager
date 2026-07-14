from dataclasses import dataclass,field
from pathlib import Path
from typing import Any,Awaitable,Callable,Literal


SkillCategory = Literal["core","specialist","utility"] # 核心、专家、辅助
SkillStage = Literal["requirement", "generation", "quality"] # 需求阶段、生成阶段、质检阶段

@dataclass
class SkillUIConfig:
    selectable: bool = False
    group: str | None = None
    icon: str | None = None

@dataclass
class SkillMeta:
    name: str
    version: str
    title: str
    description: str
    category: SkillCategory
    stage: SkillStage
    tags: list[str] = field(default_factory=list)
    ui: SkillUIConfig = field(default_factory=SkillUIConfig)
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    directory: Path | None = None
    strategies: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillContext:
    project_id: int | None = None
    task_id: int | None = None
    strategy: str = "detailed"
    use_mock: bool = False


SkillRunFn = Callable[[dict[str, Any], SkillContext], Awaitable[dict[str, Any]]]