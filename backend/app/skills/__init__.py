"""AI Skill 插件体系 — 通过 SkillRegistry 发现与调度。"""

from app.config import settings
from app.skills.base import SkillContext
from app.skills.registry import get_registry

__all__ = [
    "SkillContext",
    "get_registry",
    "parse_requirements",
    "propose_test_scope",
    "generate_cases_for_feature",
    "generate_specialist_cases",
    "list_selectable_specialist_names",
]


def _build_context(**kwargs) -> SkillContext:
    """构建 SkillContext 对象，自动填入 mock 模式标志。

    Args:
        **kwargs: 传递给 SkillContext 的其他参数，如 project_id、task_id、strategy。

    Returns:
        SkillContext: 技能上下文对象。
    """
    return SkillContext(use_mock=settings.use_mock_llm, **kwargs)


async def parse_requirements(raw_content: str) -> list[dict]:
    """解析需求文档原始内容，提取功能点列表。

    Args:
        raw_content (str): 需求文档原始内容。

    Returns:
        list[dict]: 功能点列表，每个功能点为一个包含 module、feature 等字段的字典。
    """
    registry = get_registry()
    result = await registry.run(
        "requirement_parser",
        {"raw_content": raw_content},
        _build_context(),
    )
    return result.get("items", [])


async def propose_test_scope(raw_content: str) -> dict:
    """根据需求文档内容，提出测试范围与风险建议。

    Args:
        raw_content (str): 需求文档原始内容。

    Returns:
        dict: 测试范围建议，包含 scope 字段。
    """
    registry = get_registry()
    result = await registry.run(
        "test_proposal",
        {"raw_content": raw_content},
        _build_context(),
    )
    return result.get("scope", {})


async def generate_cases_for_feature(
    feature_item: dict, strategy: str = "detailed"
) -> list[dict]:
    """根据单个功能点生成测试用例。

    Args:
        feature_item (dict): 功能点字典，包含 module、feature、description 等字段。
        strategy (str, optional): 生成策略名称。默认为 "detailed"。

    Returns:
        list[dict]: 测试用例列表。
    """
    registry = get_registry()
    strategy = registry.normalize_strategy(strategy)
    result = await registry.run(
        "case_writer",
        {"feature_item": feature_item, "strategy": strategy},
        _build_context(strategy=strategy),
    )
    return result.get("cases", [])


async def generate_specialist_cases(feature_item: dict, skill_name: str) -> list[dict]:
    """使用指定的专项技能为功能点生成测试用例。

    Args:
        feature_item (dict): 功能点字典。
        skill_name (str): 专项技能名称，如 "security"、"api_test"。

    Returns:
        list[dict]: 测试用例列表。
    """
    registry = get_registry()
    resolved = registry.resolve_skill_name(skill_name)
    result = await registry.run(
        resolved,
        {"feature_item": feature_item},
        _build_context(),
    )
    return result.get("cases", [])


def list_selectable_specialist_names() -> list[str]:
    """列出所有可在前端界面上选择的专项技能名称。

    Returns:
        list[str]: 专项技能名称列表。
    """
    return [s.name for s in get_registry().list_selectable_specialists()]
