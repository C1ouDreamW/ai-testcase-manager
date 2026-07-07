from pathlib import Path


def load_prompt(skill_dir: Path, relative_path: str) -> str:
    """
    从skill目录中加载prompt模板文件
    """
    path = skill_dir / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    return path.read_text(encoding="utf-8").strip()
