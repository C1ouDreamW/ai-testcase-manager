from pathlib import Path


def load_prompt(skill_dir: Path, relative_path: str) -> str:
    """从技能目录中加载 prompt 模板文件。

    Args:
        skill_dir (Path): 技能根目录。
        relative_path (str): prompt 文件的相对路径。

    Returns:
        str: prompt 模板内容。

    Raises:
        FileNotFoundError: prompt 文件不存在时抛出。
    """
    path = skill_dir / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    return path.read_text(encoding="utf-8").strip()
