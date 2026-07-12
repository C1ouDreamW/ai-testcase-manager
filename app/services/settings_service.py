from sqlalchemy.orm import Session

from app.config import settings
from app.models.system_config import CONFIG_ID, SystemConfig


def apply_runtime_settings(row: SystemConfig) -> None:
    """将数据库中存储的运行时配置同步到全局 Settings 对象。

    Args:
        row (SystemConfig): 系统配置的 ORM 对象。
    """
    settings.llm_api_key = row.llm_api_key
    settings.llm_base_url = row.llm_base_url
    settings.llm_model = row.llm_model
    settings.llm_mock_mode = row.llm_mock_mode
    settings.eval_llm_api_key = row.eval_llm_api_key
    settings.eval_llm_base_url = row.eval_llm_base_url
    settings.eval_llm_model = row.eval_llm_model
    settings.embedding_api_key = row.embedding_api_key
    settings.embedding_base_url = row.embedding_base_url
    settings.embedding_model = row.embedding_model


def get_or_create_config(db: Session) -> SystemConfig:
    """获取系统配置记录，不存在时用当前 Settings 值创建默认记录。

    Args:
        db (Session): 数据库会话。

    Returns:
        SystemConfig: 系统配置 ORM 对象。
    """
    row = db.get(SystemConfig, CONFIG_ID)
    if row:
        return row

    row = SystemConfig(
        id=CONFIG_ID,
        llm_api_key=settings.llm_api_key,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        llm_mock_mode=settings.llm_mock_mode,
        eval_llm_api_key=settings.eval_llm_api_key,
        eval_llm_base_url=settings.eval_llm_base_url,
        eval_llm_model=settings.eval_llm_model,
        embedding_api_key=settings.embedding_api_key,
        embedding_base_url=settings.embedding_base_url,
        embedding_model=settings.embedding_model,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def load_config_to_runtime(db: Session) -> SystemConfig:
    """从数据库加载配置并同步到运行时 Settings 对象。

    Args:
        db (Session): 数据库会话。

    Returns:
        SystemConfig: 系统配置 ORM 对象。
    """
    row = get_or_create_config(db)
    apply_runtime_settings(row)
    return row


def mask_api_key(key: str) -> tuple[bool, str]:
    """对 API Key 进行脱敏处理，仅展示后 4 位，其余用星号替代。

    Args:
        key (str): 原始 API Key。

    Returns:
        tuple[bool, str]: (是否已配置, 脱敏后的 Key 字符串)。
    """
    if not key:
        return False, ""
    if len(key) <= 4:
        return True, "****"
    return True, f"{'*' * 8}{key[-4:]}"


def serialize_settings(row: SystemConfig) -> dict:
    """将系统配置序列化为前端可用的字典，对 API Key 进行脱敏处理。

    Args:
        row (SystemConfig): 系统配置 ORM 对象。

    Returns:
        dict: 包含脱敏 Key、模型配置和 mock 状态等字段的字典。
    """
    key_set, key_masked = mask_api_key(row.llm_api_key)
    eval_key_set, eval_key_masked = mask_api_key(row.eval_llm_api_key)
    emb_key_set, emb_key_masked = mask_api_key(row.embedding_api_key)
    apply_runtime_settings(row)
    return {
        "llm_api_key_set": key_set,
        "llm_api_key_masked": key_masked,
        "llm_base_url": row.llm_base_url,
        "llm_model": row.llm_model,
        "llm_mock_mode": row.llm_mock_mode,
        "use_mock_llm": settings.use_mock_llm,
        "eval_llm_api_key_set": eval_key_set,
        "eval_llm_api_key_masked": eval_key_masked,
        "eval_llm_base_url": row.eval_llm_base_url,
        "eval_llm_model": row.eval_llm_model,
        "embedding_api_key_set": emb_key_set,
        "embedding_api_key_masked": emb_key_masked,
        "embedding_base_url": row.embedding_base_url,
        "embedding_model": row.embedding_model,
    }


def update_config(db: Session, data: dict) -> SystemConfig:
    """更新系统配置的指定字段并同步到运行时。

    仅更新传入的非 None 字段，更新后自动同步到全局 Settings。

    Args:
        db (Session): 数据库会话。
        data (dict): 待更新的配置字段字典。

    Returns:
        SystemConfig: 更新后的系统配置 ORM 对象。
    """
    row = get_or_create_config(db)

    if "llm_api_key" in data and data["llm_api_key"] is not None:
        row.llm_api_key = data["llm_api_key"]
    if data.get("llm_base_url") is not None:
        row.llm_base_url = data["llm_base_url"]
    if data.get("llm_model") is not None:
        row.llm_model = data["llm_model"]
    if data.get("llm_mock_mode") is not None:
        row.llm_mock_mode = data["llm_mock_mode"]
    if "eval_llm_api_key" in data and data["eval_llm_api_key"] is not None:
        row.eval_llm_api_key = data["eval_llm_api_key"]
    if data.get("eval_llm_base_url") is not None:
        row.eval_llm_base_url = data["eval_llm_base_url"]
    if data.get("eval_llm_model") is not None:
        row.eval_llm_model = data["eval_llm_model"]
    if "embedding_api_key" in data and data["embedding_api_key"] is not None:
        row.embedding_api_key = data["embedding_api_key"]
    if data.get("embedding_base_url") is not None:
        row.embedding_base_url = data["embedding_base_url"]
    if data.get("embedding_model") is not None:
        row.embedding_model = data["embedding_model"]

    db.commit()
    db.refresh(row)
    apply_runtime_settings(row)
    return row
