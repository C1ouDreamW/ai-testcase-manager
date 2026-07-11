from pathlib import Path

from app.services.llm import chat_completion, parse_json_response
from app.skills.base import SkillContext
from app.skills.shared.prompt_loader import load_prompt

SKILL_DIR = Path(__file__).resolve().parent

MOCK_SCOPE = {
    "in_scope": [
        "核心登录流程（账号密码、手机号验证码）",
        "密码错误提示与连续错误锁定策略",
        "输入校验与边界（空值、格式、长度）",
    ],
    "out_scope": [
        "第三方 OAuth / 扫码登录",
        "性能与并发压测",
        "UI 视觉走查",
    ],
    "risks": [
        "短信验证码通道稳定性未知",
        "锁定阈值与风控策略耦合，需与产品确认",
        "多端并发登录行为未在需求中明确",
    ],
}


def _normalize(data) -> dict:
    """将测试范围原始数据标准化为包含 in_scope、out_scope、risks 的字典。

    Args:
        data: JSON 解析后的原始数据。

    Returns:
        dict: 标准化后的测试范围字典。
    """
    if not isinstance(data, dict):
        data = {}
    return {
        "in_scope": list(data.get("in_scope") or []),
        "out_scope": list(data.get("out_scope") or []),
        "risks": list(data.get("risks") or []),
    }


async def run(inputs: dict, context: SkillContext) -> dict:
    """根据需求文档内容提出测试范围与风险建议。

    mock 模式下返回预置的模拟范围数据。

    Args:
        inputs (dict): 包含 raw_content（需求文档原始内容）的字典。
        context (SkillContext): 技能执行上下文。

    Returns:
        dict: 包含 scope（测试范围建议）的结果字典。
    """
    raw_content = inputs["raw_content"]
    if context.use_mock:
        return {"scope": MOCK_SCOPE}

    system_prompt = load_prompt(SKILL_DIR, "prompt.md")
    user_prompt = f"请基于以下需求文档，输出测试范围与风险提案：\n\n{raw_content}"
    result = await chat_completion(system_prompt, user_prompt)
    try:
        data = parse_json_response(result)
    except Exception:
        data = {}
    return {"scope": _normalize(data)}
