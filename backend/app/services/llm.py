import contextvars
import json
from typing import Any

import httpx

from app.config import settings

# 按异步上下文累计 token 用量：run_generation 开始时创建计数器，
# 期间所有 LLM 调用（生成 + 专项 + Judge）都会累加到同一个计数器。
_token_counter: contextvars.ContextVar[dict | None] = contextvars.ContextVar("token_counter", default=None)


def start_token_tracking() -> dict:
    """启动 Token 用量跟踪，为当前异步上下文创建计数器。

    Returns:
        dict: 包含 prompt_tokens 和 completion_tokens 初始值的计数器字典。
    """
    counter = {"prompt_tokens": 0, "completion_tokens": 0}
    _token_counter.set(counter)
    return counter


def total_tokens(counter: dict) -> int:
    """计算提示词和完成词的总 Token 数。

    Args:
        counter (dict): Token 计数器字典，包含 prompt_tokens 和 completion_tokens。

    Returns:
        int: 总 Token 数量。
    """
    return counter.get("prompt_tokens", 0) + counter.get("completion_tokens", 0)


def _record_usage(usage: dict | None) -> None:
    """将一次 LLM 调用的用量记录到当前上下文的 Token 计数器中。

    Args:
        usage (dict | None): LLM 响应中的 usage 字段。
    """
    counter = _token_counter.get()
    if counter is None or not isinstance(usage, dict):
        return
    counter["prompt_tokens"] += usage.get("prompt_tokens", 0) or 0
    counter["completion_tokens"] += usage.get("completion_tokens", 0) or 0


def _resolve_llm(use_eval_model: bool) -> tuple[str, str, str]:
    """根据用途解析 LLM 连接参数，评测模型配置留空的项回退到生成模型配置。

    Args:
        use_eval_model (bool): 是否使用评测专用模型。

    Returns:
        tuple[str, str, str]: (base_url, api_key, model) 三元组。
    """
    if use_eval_model:
        return (
            settings.eval_llm_base_url or settings.llm_base_url,
            settings.eval_llm_api_key or settings.llm_api_key,
            settings.eval_llm_model or settings.llm_model,
        )
    return settings.llm_base_url, settings.llm_api_key, settings.llm_model


class LLMCallError(RuntimeError):
    """LLM 调用失败，message 为面向用户的中文提示。"""


def _friendly_error(exc: Exception, kind: str) -> LLMCallError:
    """将 HTTP 异常转换为面向用户的中文友好错误提示。

    Args:
        exc (Exception): 原始异常对象。
        kind (str): 模型类型描述，如"生成模型"、"评测模型"。

    Returns:
        LLMCallError: 包含中文提示的 LLM 调用错误。
    """
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return LLMCallError(f"{kind}的 API Key 无效或已过期，请到「设置」页更新后重试")
        if code == 429:
            return LLMCallError(f"{kind}调用触发限流（429），请稍后重试")
        if code == 404:
            return LLMCallError(f"{kind}的接口地址或模型名有误（404），请检查「设置」页配置")
        return LLMCallError(f"{kind}调用失败（HTTP {code}），请检查「设置」页配置")
    return LLMCallError(f"无法连接{kind}服务，请检查接口地址与网络：{exc}")


async def chat_completion(system_prompt: str, user_prompt: str, *, use_eval_model: bool = False) -> str:
    """异步发送 Chat Completions 请求到 LLM 服务。

    mock 模式下直接返回空字符串。

    Args:
        system_prompt (str): 系统提示词。
        user_prompt (str): 用户提示词。
        use_eval_model (bool, optional): 是否使用评测专用模型。默认为 False。

    Returns:
        str: LLM 返回的文本内容。

    Raises:
        LLMCallError: LLM 调用失败时抛出，包含中文友好提示。
    """
    if settings.use_mock_llm:
        return ""

    kind = "评测模型" if use_eval_model else "生成模型"
    base_url, api_key, model = _resolve_llm(use_eval_model)
    try:
        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        raise _friendly_error(exc, kind) from exc
    _record_usage(data.get("usage"))
    return data["choices"][0]["message"]["content"]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """调用 OpenAI 兼容的 Embeddings 接口批量向量化文本。

    Args:
        texts (list[str]): 待向量化的文本列表。

    Returns:
        list[list[float]]: 按输入顺序排列的向量列表。

    Raises:
        RuntimeError: 未配置 Embedding 模型时抛出。
        LLMCallError: Embedding 调用失败时抛出。
    """
    if not (settings.embedding_base_url and settings.embedding_api_key and settings.embedding_model):
        raise RuntimeError("未配置 Embedding 模型，请先在设置中填写 Embedding API 地址、模型和 Key")

    try:
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            response = await client.post(
                f"{settings.embedding_base_url.rstrip('/')}/embeddings",
                headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
                json={"model": settings.embedding_model, "input": texts},
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        raise _friendly_error(exc, "Embedding 模型") from exc
    # 按 index 排序，保证返回顺序与输入一致
    items = sorted(data["data"], key=lambda d: d["index"])
    return [item["embedding"] for item in items]


def parse_json_response(text: str) -> Any:
    """解析 LLM 返回的 JSON 文本，自动处理 markdown 代码块包裹。

    Args:
        text (str): LLM 返回的原始文本。

    Returns:
        Any: 解析后的 JSON 对象。
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)
