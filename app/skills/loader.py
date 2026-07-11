import importlib.util
from pathlib import Path
from typing import Any

import yaml

from app.skills.base import SkillContext, SkillMeta, SkillRunFn, SkillUIConfig

SKILLS_ROOT = Path(__file__).resolve().parent


def _parse_ui(raw: dict | None) -> SkillUIConfig:
    """从 raw 字典解析 UI 配置，返回 SkillUIConfig 对象。

    Args:
        raw (dict | None): YAML 中 ui 字段的原始字典。

    Returns:
        SkillUIConfig: UI 配置对象。
    """
    raw = raw or {}
    return SkillUIConfig(
        selectable=bool(raw.get("selectable", False)),
        group=raw.get("group"),
        icon=raw.get("icon"),
    )


def _load_manifest(skill_dir: Path) -> SkillMeta:
    """从技能目录加载 skill.yaml 并解析为 SkillMeta 对象。

    Args:
        skill_dir (Path): 技能目录路径。

    Returns:
        SkillMeta: 技能元数据对象。

    Raises:
        FileNotFoundError: 缺少 skill.yaml 文件时抛出。
        ValueError: skill.yaml 格式无效时抛出。
    """
    manifest_path = skill_dir / "skill.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"缺少 skill.yaml: {skill_dir}")

    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("name"):
        raise ValueError(f"无效的 skill.yaml: {manifest_path}")

    return SkillMeta(
        name=data["name"],
        version=str(data.get("version", "1.0.0")),
        title=data.get("title", data["name"]),
        description=data.get("description", ""),
        category=data.get("category", "utility"),
        stage=data.get("stage", "generation"),
        tags=list(data.get("tags") or []),
        ui=_parse_ui(data.get("ui")),
        inputs=dict(data.get("inputs") or {}),
        outputs=dict(data.get("outputs") or {}),
        directory=skill_dir,
        strategies=dict(data.get("strategies") or {}),
    )


def _load_handler(skill_dir: Path, skill_name: str) -> SkillRunFn:
    """动态加载技能目录中的 handler.py 模块，提取 run 函数。

    Args:
        skill_dir (Path): 技能目录路径。
        skill_name (str): 技能名称，用于生成唯一模块名。

    Returns:
        SkillRunFn: 可调用的异步 run 函数。

    Raises:
        FileNotFoundError: 缺少 handler.py 文件时抛出。
        ImportError: handler 加载失败时抛出。
        AttributeError: handler.py 未导出 run 函数时抛出。
    """
    handler_path = skill_dir / "handler.py"
    if not handler_path.exists():
        raise FileNotFoundError(f"缺少 handler.py: {skill_dir}")

    module_name = f"skill_handler_{skill_name}"
    spec = importlib.util.spec_from_file_location(module_name, handler_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 handler: {handler_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    run_fn = getattr(module, "run", None)
    if run_fn is None or not callable(run_fn):
        raise AttributeError(f"{handler_path} 必须导出 async def run(inputs, context)")
    return run_fn


def discover_skills(root: Path | None = None) -> tuple[dict[str, SkillMeta], dict[str, SkillRunFn]]:
    """发现并加载指定根目录下所有的技能插件。

    遍历子目录，跳过以下划线开头、shared 目录以及不含 skill.yaml 的目录。
    对每个有效技能目录加载清单和处理器。

    Args:
        root (Path | None, optional): 技能根目录。默认为 skills 目录自身。

    Returns:
        tuple[dict[str, SkillMeta], dict[str, SkillRunFn]]: (名称→元数据, 名称→处理函数) 的元组。

    Raises:
        RuntimeError: 未发现任何技能时抛出。
        ValueError: 技能名称重复时抛出。
    """
    root = root or SKILLS_ROOT
    metas: dict[str, SkillMeta] = {}
    handlers: dict[str, SkillRunFn] = {}

    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("_") or child.name == "shared":
            continue
        if not (child / "skill.yaml").exists():
            continue

        meta = _load_manifest(child)
        if meta.name in metas:
            raise ValueError(f"Skill 名称重复: {meta.name}")

        handler = _load_handler(child, meta.name)
        metas[meta.name] = meta
        handlers[meta.name] = handler

    if not metas:
        raise RuntimeError("未发现任何 Skill，请检查 skills 目录")

    return metas, handlers


def normalize_inputs(meta: SkillMeta, inputs: dict[str, Any]) -> dict[str, Any]:
    """根据技能元数据的输入规范，校验并补全调用参数。

    检查必填参数是否存在，为缺失的可选参数填入默认值。

    Args:
        meta (SkillMeta): 技能元数据。
        inputs (dict[str, Any]): 调用时传入的参数字典。

    Returns:
        dict[str, Any]: 标准化后的参数字典。

    Raises:
        ValueError: 缺少必填参数时抛出。
    """
    normalized = dict(inputs)
    for key, spec in meta.inputs.items():
        if spec.get("required") and key not in normalized:
            raise ValueError(f"Skill `{meta.name}` 缺少必填参数: {key}")
        if key not in normalized and "default" in spec:
            normalized[key] = spec["default"]
    return normalized
