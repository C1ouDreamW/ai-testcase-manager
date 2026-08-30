import shutil
from pathlib import Path

from app.config import BASE_DIR, settings


def design_root() -> Path:
    configured = settings.design_asset_dir.strip()
    return (
        Path(configured).expanduser().resolve()
        if configured
        else (BASE_DIR / "data" / "design-assets").resolve()
    )


def remove_project_designs(project_id: int) -> None:
    root = design_root()
    project_dir = (root / str(project_id)).resolve()
    if root in project_dir.parents:
        shutil.rmtree(project_dir, ignore_errors=True)
