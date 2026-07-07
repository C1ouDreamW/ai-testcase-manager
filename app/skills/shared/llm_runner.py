from app.services.llm import chat_completion
from app.skills.shared.output_parser import parse_cases_response


async def call_for_cases(system_prompt: str, user_prompt: str, skill_name: str) -> list[dict]:
    """
    调用 LLM 生成测试用例，将 LLM 返回值解析为测试用例字典列表，并标注来源skill_name。
    :param system_prompt: 系统提示词
    :param user_prompt: 用户提示词
    :param skill_name: 技能名称
    :return: 返回
    """
    result = await chat_completion(system_prompt, user_prompt)
    cases = parse_cases_response(result)
    for case in cases:
        case["skill_name"] = skill_name
    return cases
