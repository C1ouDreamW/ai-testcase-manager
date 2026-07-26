import base64
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from app.ai.model_factory import ModelPurpose, create_chat_model, normalize_chat_error
from app.ai.schemas import (
    CaseJudgementBatch,
    CoverageDecision,
    DesignParseResult,
    GeneratedCaseBatch,
    RequirementFeatureBatch,
    TestProposal,
)
from app.services.llm import LLMCallError, record_token_usage
from app.services.settings_service import RuntimeModelConfig


SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return str(content or "")


async def invoke_structured(
    system_prompt: str,
    user_prompt: str,
    schema: type[SchemaT],
    config: RuntimeModelConfig,
    *,
    purpose: ModelPurpose = "generation",
) -> SchemaT:
    """使用 LangChain Prompt + ChatModel + Pydantic Parser 获得结构化结果。

    这里采用供应商兼容性更高的 PydanticOutputParser，而不是强制所有
    OpenAI-compatible 服务都支持 tool calling/json_schema。
    """
    parser = PydanticOutputParser(pydantic_object=schema)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "{system_prompt}"),
            (
                "human",
                "{user_prompt}\n\n请严格遵循以下结构化输出规范，只输出 JSON：\n{format_instructions}",
            ),
        ]
    )
    model = create_chat_model(config, purpose)
    messages = prompt.format_messages(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        format_instructions=parser.get_format_instructions(),
    )
    try:
        response = await model.ainvoke(messages)
        record_token_usage(getattr(response, "usage_metadata", None))
        return parser.parse(_message_text(response.content))
    except Exception as exc:
        # Pydantic/JSON 错误保留原异常，交给 LangGraph 判断是否重试；
        # 网络、鉴权等模型异常继续转成项目原有的中文提示。
        if exc.__class__.__module__.startswith(("pydantic", "json")) or "OutputParser" in exc.__class__.__name__:
            raise
        if isinstance(exc, LLMCallError):
            raise
        raise normalize_chat_error(exc, purpose) from exc
    finally:
        # create_chat_model 为每次调用创建独立 AsyncClient；调用完成后及时释放连接。
        http_client = getattr(model, "http_async_client", None)
        if http_client is not None:
            await http_client.aclose()


async def parse_requirement_items(
    system_prompt: str,
    raw_content: str,
    config: RuntimeModelConfig,
) -> list[dict]:
    result = await invoke_structured(
        system_prompt,
        f"请分析以下需求文档并提取功能点：\n\n{raw_content}",
        RequirementFeatureBatch,
        config,
    )
    return [item.model_dump() for item in result.root]


async def parse_design_image(
    system_prompt: str,
    image_data: bytes,
    content_type: str,
    config: RuntimeModelConfig,
) -> dict:
    """调用独立视觉模型解析设计稿。

    返回 {is_design, image_summary, features}；非设计稿时 features 为空，
    由上层给出友好提示而不是硬凑需求功能点。
    """
    parser = PydanticOutputParser(pydantic_object=DesignParseResult)
    encoded = base64.b64encode(image_data).decode("ascii")
    # 硅基流动的 Qwen3 混合思考模型：关闭 thinking，避免结构化 JSON 前的长推理拖慢/超时。
    # 其它服务商（OpenAI/Gemini 等）不下发该字段，避免报未知参数。
    extra_body = None
    if "siliconflow" in (config.vision_base_url or "").lower():
        extra_body = {"enable_thinking": False}
    model = create_chat_model(
        config,
        "vision",
        temperature=0.1,
        extra_body=extra_body,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=[
            {
                "type": "text",
                "text": (
                    "请分析这张产品设计稿，提取可测试的页面功能、交互、状态与校验规则。"
                    "不要臆测图片中无法确认的后端规则。\n\n"
                    "请严格遵循以下结构化输出规范，只输出 JSON：\n"
                    f"{parser.get_format_instructions()}"
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:{content_type};base64,{encoded}"},
            },
        ]),
    ]
    try:
        response = await model.ainvoke(messages)
        record_token_usage(getattr(response, "usage_metadata", None))
        result = parser.parse(_message_text(response.content))
        features = [f.model_dump() for f in result.features if f.feature.strip()]
        return {
            "is_design": bool(result.is_design),
            "image_summary": result.image_summary.strip(),
            "features": features,
        }
    except Exception as exc:
        if exc.__class__.__module__.startswith(("pydantic", "json")) or "OutputParser" in exc.__class__.__name__:
            raise
        if isinstance(exc, LLMCallError):
            raise
        raise normalize_chat_error(exc, "vision") from exc
    finally:
        http_client = getattr(model, "http_async_client", None)
        if http_client is not None:
            await http_client.aclose()


async def generate_cases(
    system_prompt: str,
    user_prompt: str,
    skill_name: str,
    config: RuntimeModelConfig,
) -> list[dict]:
    result = await invoke_structured(
        system_prompt,
        user_prompt,
        GeneratedCaseBatch,
        config,
    )
    cases = [item.model_dump() for item in result.root]
    for case in cases:
        case["skill_name"] = skill_name
    return cases


async def generate_test_proposal(
    system_prompt: str,
    raw_content: str,
    config: RuntimeModelConfig,
) -> dict:
    result = await invoke_structured(
        system_prompt,
        f"请基于以下需求文档，输出测试范围与风险提案：\n\n{raw_content}",
        TestProposal,
        config,
    )
    return result.model_dump()


async def judge_cases(
    system_prompt: str,
    user_prompt: str,
    config: RuntimeModelConfig,
) -> list[dict]:
    result = await invoke_structured(
        system_prompt,
        user_prompt,
        CaseJudgementBatch,
        config,
        purpose="evaluation",
    )
    return [item.model_dump() for item in result.judgements]


async def judge_checkpoint_coverage(
    system_prompt: str,
    user_prompt: str,
    config: RuntimeModelConfig,
) -> list[int]:
    result = await invoke_structured(
        system_prompt,
        user_prompt,
        CoverageDecision,
        config,
        purpose="evaluation",
    )
    return result.covered_indexes
