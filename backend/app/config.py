from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"
    debug: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 生成模型
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-v4-flash"
    llm_mock_mode: bool = True

    # 评测专用 LLM（AI Judge / 召回率判定），留空则复用上面的生成模型配置
    eval_llm_api_key: str = ""
    eval_llm_base_url: str = ""
    eval_llm_model: str = ""

    # Embedding 模型
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        """将逗号分隔的 CORS 来源字符串解析为列表。

        Returns:
            list[str]: 去除空白后的 CORS 来源列表。
        """
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def use_mock_llm(self) -> bool:
        """判断是否使用模拟 LLM 模式。

        当 mock 模式开启或未配置 API Key 时返回 True。

        Returns:
            bool: 是否使用模拟 LLM。
        """
        return self.llm_mock_mode or not self.llm_api_key


settings = Settings()
