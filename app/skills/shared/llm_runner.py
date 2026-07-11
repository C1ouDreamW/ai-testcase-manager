from app.services.llm import chat_completion
from app.skills.shared.output_parser import parse_cases_response


async def call_for_cases(system_prompt: str, user_prompt: str, skill_name: str) -> list[dict]:
    """调用 LLM 生成测试用例，解析返回值并为每条用例标注来源技能。

    Args:
        system_prompt (str): 系统提示词。
        user_prompt (str): 用户提示词。
        skill_name (str): 来源技能名称，会注入到每条用例的 skill_name 字段。

    Returns:
        list[dict]: 标注了 skill_name 的测试用例列表。
    """
    result = await chat_completion(system_prompt, user_prompt)
    cases = parse_cases_response(result)
    for case in cases:
        case["skill_name"] = skill_name
    return cases
