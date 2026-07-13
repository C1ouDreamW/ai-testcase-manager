from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SystemSettingsOut, SystemSettingsUpdate
from app.services.settings_service import load_config_to_runtime, serialize_settings, update_config

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SystemSettingsOut)
def get_settings(db: Session = Depends(get_db)):
    """获取当前系统配置，对 API Key 进行脱敏处理。

    Args:
        db (Session): 数据库会话。

    Returns:
        SystemSettingsOut: 系统配置信息。
    """
    row = load_config_to_runtime(db)
    return serialize_settings(row)


@router.patch("", response_model=SystemSettingsOut)
def patch_settings(data: SystemSettingsUpdate, db: Session = Depends(get_db)):
    """更新系统配置的指定字段，仅更新传入的非空字段。

    Args:
        data (SystemSettingsUpdate): 配置更新请求体。
        db (Session): 数据库会话。

    Returns:
        SystemSettingsOut: 更新后的系统配置。
    """
    row = update_config(db, data.model_dump(exclude_unset=True))
    return serialize_settings(row)
