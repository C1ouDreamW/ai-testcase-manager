from typing import Any

from app.skills.base import SkillContext, SkillMeta, SkillRunFn
from app.skills.loader import discover_skills, normalize_inputs

STRATEGY_DEFAULTS = {
    "full": {
        "title": "完整用例",
        "description": "覆盖功能、边界与异常，并自动标记其中的冒烟用例",
        "min_cases_per_feature": 5,
        "max_cases_per_feature": 12,
        "recommended": True,
    },
    "quick": {
        "title": "快速冒烟",
        "description": "只生成核心主路径冒烟用例，每个功能点 2～4 条",
        "min_cases_per_feature": 2,
        "max_cases_per_feature": 4,
        "recommended": False,
    },
}

LEGACY_SKILL_ALIASES = {
    "api": "api_test",
}

LEGACY_STRATEGY_MAP = {
    "detailed": "full",
    "standard": "full",
    "smoke": "quick",
    "functional_only": "quick",
}


class SkillRegistry:
    """技能注册表，管理所有技能插件的发现、查询和调度。"""

    def __init__(self) -> None:
        """初始化技能注册表，自动发现并加载所有技能。"""
        self._metas, self._handlers = discover_skills()

    def reload(self) -> None:
        """重新扫描并加载技能目录，用于热更新。"""
        self._metas, self._handlers = discover_skills()

    def list_skills(
        self,
        *,
        category: str | None = None,
        stage: str | None = None,
        selectable_only: bool = False,
    ) -> list[SkillMeta]:
        """列出满足筛选条件的技能。

        Args:
            category (str | None, optional): 按分类筛选。默认为 None。
            stage (str | None, optional): 按阶段筛选。默认为 None。
            selectable_only (bool, optional): 仅返回界面可选的技能。默认为 False。

        Returns:
            list[SkillMeta]: 按名称排序的技能元数据列表。
        """
        items = list(self._metas.values())
        if category:
            items = [s for s in items if s.category == category]
        if stage:
            items = [s for s in items if s.stage == stage]
        if selectable_only:
            items = [s for s in items if s.ui.selectable]
        return sorted(items, key=lambda s: s.name)

    def get_skill(self, name: str) -> SkillMeta:
        """通过名称获取技能元数据。

        Args:
            name (str): 技能名称（支持别名）。

        Returns:
            SkillMeta: 技能元数据对象。

        Raises:
            KeyError: 技能不存在时抛出。
        """
        resolved = self.resolve_skill_name(name)
        if resolved not in self._metas:
            raise KeyError(f"Skill 不存在: {name}")
        return self._metas[resolved]

    def resolve_skill_name(self, name: str) -> str:
        """将旧版别名解析为当前技能名称。

        Args:
            name (str): 技能名称或别名。

        Returns:
            str: 解析后的标准技能名称。
        """
        return LEGACY_SKILL_ALIASES.get(name, name)

    def list_selectable_specialists(self) -> list[SkillMeta]:
        """列出所有可在界面上勾选的专项技能。

        Returns:
            list[SkillMeta]: 专项技能元数据列表。
        """
        return self.list_skills(category="specialist", selectable_only=True)

    def list_strategies(self) -> list[dict[str, Any]]:
        """列出所有可用的生成策略及其配置。

        优先从 case_writer 技能的 skill.yaml 中读取，缺失项由 STRATEGY_DEFAULTS 补全。

        Returns:
            list[dict[str, Any]]: 策略配置列表，每项包含 key、title、description、min/max 用例数等。
        """
        case_writer = self._metas.get("case_writer")
        strategies = []
        source = case_writer.strategies if case_writer else STRATEGY_DEFAULTS
        for key, spec in source.items():
            defaults = STRATEGY_DEFAULTS.get(key, {})
            merged = {**defaults, **spec, "key": key}
            strategies.append(merged)
        if not strategies:
            for key, spec in STRATEGY_DEFAULTS.items():
                strategies.append({**spec, "key": key})
        return strategies

    def normalize_strategy(self, strategy: str) -> str:
        """将策略名称标准化为合法值，旧版名称自动映射。

        Args:
            strategy (str): 策略名称。

        Returns:
            str: 标准化后的策略名称，无效名称回退为 "full"。
        """
        valid = set(STRATEGY_DEFAULTS)
        case_writer = self._metas.get("case_writer")
        if case_writer:
            valid |= set(case_writer.strategies)
        if strategy in valid:
            return strategy
        return LEGACY_STRATEGY_MAP.get(strategy, "full")

    def validate_specialist_skills(self, names: list[str]) -> list[str]:
        """校验并过滤专项技能名称列表，仅保留已注册的有效技能。

        Args:
            names (list[str]): 待校验的技能名称列表。

        Returns:
            list[str]: 通过校验的有效技能名称列表。
        """
        allowed = {s.name for s in self.list_selectable_specialists()}
        result = []
        for name in names:
            resolved = self.resolve_skill_name(name)
            if resolved in allowed:
                result.append(resolved)
        return result

    async def run(
        self, name: str, inputs: dict[str, Any], context: SkillContext
    ) -> dict[str, Any]:
        """根据名称调度技能，校验参数后执行 handler 的 run 函数。

        Args:
            name (str): 技能名称。
            inputs (dict[str, Any]): 传入技能的参数。
            context (SkillContext): 技能执行上下文。

        Returns:
            dict[str, Any]: 技能执行结果。

        Raises:
            KeyError: 技能不存在时抛出。
        """
        resolved = self.resolve_skill_name(name)
        if resolved not in self._handlers:
            raise KeyError(f"Skill 不存在: {name}")
        meta = self._metas[resolved]
        handler: SkillRunFn = self._handlers[resolved]
        normalized = normalize_inputs(meta, inputs)
        return await handler(normalized, context)


_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    """获取技能注册表单例实例，首次调用时自动初始化。

    Returns:
        SkillRegistry: 技能注册表单例。
    """
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
