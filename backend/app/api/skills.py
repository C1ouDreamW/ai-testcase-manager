from fastapi import APIRouter, HTTPException

from app.schemas import SkillCatalogOut, SkillOut, StrategyOut
from app.skills.registry import get_registry

router = APIRouter(prefix="/skills", tags=["skills"])


def _skill_to_out(meta) -> SkillOut:
    """将 SkillMeta 对象序列化为供前端使用的 SkillOut Schema。

    Args:
        meta (SkillMeta): 技能元数据对象。

    Returns:
        SkillOut: 序列化后的技能输出。
    """
    return SkillOut(
        name=meta.name,
        version=meta.version,
        title=meta.title,
        description=meta.description,
        category=meta.category,
        stage=meta.stage,
        tags=meta.tags,
        selectable=meta.ui.selectable,
        group=meta.ui.group,
        icon=meta.ui.icon,
    )


@router.get("", response_model=SkillCatalogOut)
def list_skills():
    """列出所有可用技能和生成策略的目录。

    Returns:
        SkillCatalogOut: 包含核心技能、专项技能和策略的目录。
    """
    registry = get_registry()
    all_skills = registry.list_skills()
    core = [_skill_to_out(s) for s in all_skills if s.category == "core"]
    specialist = [_skill_to_out(s) for s in registry.list_selectable_specialists()]
    strategies = [
        StrategyOut(
            key=s["key"],
            title=s.get("title", s["key"]),
            description=s.get("description", ""),
            min_cases_per_feature=s.get("min_cases_per_feature", 2),
            max_cases_per_feature=s.get("max_cases_per_feature", 4),
            recommended=bool(s.get("recommended", False)),
        )
        for s in registry.list_strategies()
    ]
    return SkillCatalogOut(core=core, specialist=specialist, strategies=strategies)


@router.get("/{skill_name}", response_model=SkillOut)
def get_skill(skill_name: str):
    """根据名称获取单个技能的详细信息。

    Args:
        skill_name (str): 技能名称。

    Returns:
        SkillOut: 技能详细信息。

    Raises:
        HTTPException: 技能不存在时返回 404。
    """
    registry = get_registry()
    try:
        meta = registry.get_skill(skill_name)
    except KeyError as exc:
        raise HTTPException(404, "Skill 不存在") from exc
    return _skill_to_out(meta)
