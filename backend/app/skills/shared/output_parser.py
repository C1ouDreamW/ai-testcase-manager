import json

from app.services.llm import parse_json_response


def parse_cases_response(text: str) -> list[dict]:
    """将 LLM 返回的文本解析为统一的测试用例列表。

    Args:
        text (str): LLM 返回的文本内容。

    Returns:
        list[dict]: 清洗后的测试用例字典列表。
    """
    if not text.strip():
        return []
    data = parse_json_response(text)
    if isinstance(data, dict):
        data = data.get("cases", data.get("items", [data]))
    if not isinstance(data, list):
        data = [data] if data else []
    return [c for c in data if isinstance(c, dict)]


def parse_items_response(text: str) -> list[dict]:
    """将 LLM 返回的文本解析为统一的功能点列表。

    Args:
        text (str): LLM 返回的文本内容。

    Returns:
        list[dict]: 清洗后的功能点字典列表。
    """
    if not text.strip():
        return []
    data = parse_json_response(text)
    if isinstance(data, dict):
        data = data.get("items", data.get("features", [data]))
    if not isinstance(data, list):
        data = [data] if data else []
    return [item for item in data if isinstance(item, dict)]


def format_scope_hint(scope: dict | None) -> str:
    """将测试范围和风险信息格式化为可拼入 prompt 的中文提示。

    生成时只关心 out_scope（跳过）与 risks（优先补测）；in_scope 已由功能点体现，
    此处不再重复。

    Args:
        scope (dict | None): 包含 in_scope、out_scope、risks 的测试范围字典。

    Returns:
        str: 格式化的中文提示字符串，无有效信息时返回空字符串。
    """
    if not isinstance(scope, dict):
        return ""
    out_scope = [str(s).strip() for s in (scope.get("out_scope") or []) if str(s).strip()]
    risks = [str(s).strip() for s in (scope.get("risks") or []) if str(s).strip()]
    if not out_scope and not risks:
        return ""

    lines = ["", "本次测试范围约束（来自需求评审）："]
    if out_scope:
        lines.append("- 不测范围（禁止生成相关用例）：")
        lines.extend(f"  · {s}" for s in out_scope)
    if risks:
        lines.append("- 风险 / 待澄清（优先覆盖，提高对应用例优先级）：")
        lines.extend(f"  · {s}" for s in risks)
    return "\n".join(lines)


def format_knowledge_hint(knowledge: list[dict] | None) -> str:
    """将检索到的知识库分块格式化为 prompt 段落，并附防幻觉约束。

    Args:
        knowledge (list[dict] | None): 知识库检索结果列表，每项包含 title、heading、content、score。

    Returns:
        str: 格式化的中文提示字符串，无知识时返回空字符串。
    """
    if not knowledge:
        return ""
    lines = ["", "相关业务知识（来自项目知识库，按相关度排序）："]
    for i, k in enumerate(knowledge, 1):
        source = f"《{k.get('title', '')}》"
        if k.get("heading"):
            source += f" - {k['heading']}"
        lines.append(f"[知识{i}] 来源：{source}")
        lines.append(k.get("content", "").strip())
    lines.append("")
    lines.append(
        "约束：设计用例时必须结合以上业务知识；"
        "业务规则只能来自功能点描述和以上知识，禁止编造未提及的规则、金额、阈值或流程。"
    )
    return "\n".join(lines)


def feature_to_user_prompt(
    feature_item: dict,
    scope: dict | None = None,
    knowledge: list[dict] | None = None,
) -> str:
    """将功能点、测试范围、知识库信息组装为传给 LLM 的完整 user prompt。

    Args:
        feature_item (dict): 功能点字典。
        scope (dict | None, optional): 测试范围字典。默认为 None。
        knowledge (list[dict] | None, optional): 知识库检索结果。默认为 None。

    Returns:
        str: 组装好的 user prompt 字符串。
    """
    base = f"功能点：\n{json.dumps(feature_item, ensure_ascii=False, indent=2)}"
    parts = [base]
    scope_hint = format_scope_hint(scope)
    if scope_hint:
        parts.append(scope_hint)
    knowledge_hint = format_knowledge_hint(knowledge)
    if knowledge_hint:
        parts.append(knowledge_hint)
    return "\n".join(parts)


def attach_skill_name(cases: list[dict], skill_name: str) -> list[dict]:
    """为每条用例字典添加来源技能名称字段。

    Args:
        cases (list[dict]): 用例列表。
        skill_name (str): 来源技能名称。

    Returns:
        list[dict]: 标注了 skill_name 的用例列表。
    """
    for case in cases:
        case["skill_name"] = skill_name
    return cases
