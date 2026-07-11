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
    """
    构建 SkillContext 对象。
    :param kwargs: 其他参数
    :return: SkillContext 对象
    """
    return SkillContext(use_mock=settings.use_mock_llm, **kwargs)


async def parse_requirements(raw_content: str) -> list[dict]:
    """
    解析需求文档，提取功能点。
    :param raw_content: 需求文档原始内容
    :return: 功能点列表，每个功能点为一个字典
    """
    registry = get_registry()
    result = await registry.run(
        "requirement_parser",
        {"raw_content": raw_content},
        _build_context(),
    )
    return result.get("items", [])


async def propose_test_scope(raw_content: str) -> dict:
    """
    根据需求文档，提出测试范围建议。
    :param raw_content: 需求文档原始内容
    :return: 测试范围建议，包含 scope 字段
    """
    registry = get_registry()
    result = await registry.run(
        "test_proposal",
        {"raw_content": raw_content},
        _build_context(),
    )
    return result.get("scope", {})


async def generate_cases_for_feature(feature_item: dict, strategy: str = "detailed") -> list[dict]:
    """
    根据功能点，生成测试用例。
    :param feature_item: 功能点字典
    :param strategy: 生成策略
    :return: 测试用例列表
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
    """
    根据功能点，使用指定的专家技能生成测试用例。
    :param feature_item: 功能点字典
    :param skill_name: 专家技能名称
    :return: 测试用例列表
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
    """
    列出所有可选的专家技能名称。
    :return: 专家技能名称列表
    """
    return [s.name for s in get_registry().list_selectable_specialists()]
