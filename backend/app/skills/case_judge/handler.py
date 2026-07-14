import json
from pathlib import Path

from app.services.llm import chat_completion, parse_json_response
from app.skills.base import SkillContext
from app.skills.shared.prompt_loader import load_prompt

SKILL_DIR = Path(__file__).resolve().parent
SKILL_NAME = "case_judge"

DIMENSIONS = ("relevance", "executability", "verifiability")


def _clamp(value, lo=1, hi=5) -> int:
    """将分值限制在 [lo, hi] 范围内，非数值默认为 3。

    Args:
        value: 原始分值。
        lo (int, optional): 下限。默认为 1。
        hi (int, optional): 上限。默认为 5。

    Returns:
        int: 限制后的整型分值。
    """
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return 3


def _normalize_judgement(raw: dict) -> dict:
    """将原始评分数据标准化，计算综合分（三维度平均值）。

    Args:
        raw (dict): 原始评分字典，包含 relevance、executability、verifiability 等字段。

    Returns:
        dict: 标准化后的评分字典，包含 overall、hallucination 等字段。
    """
    scores = {dim: _clamp(raw.get(dim)) for dim in DIMENSIONS}
    overall = round(sum(scores.values()) / len(scores), 1)
    return {
        "index": raw.get("index"),
        **scores,
        "overall": overall,
        "hallucination": bool(raw.get("hallucination", False)),
        "hallucination_reason": (raw.get("hallucination_reason") or "").strip(),
        "comment": (raw.get("comment") or "").strip(),
    }


def _mock_judgements(cases: list) -> list[dict]:
    """生成模拟的 AI 评分结果，用于 mock 模式。

    每条用例返回基于索引的模拟分值，不标记幻觉。

    Args:
        cases (list): 用例列表。

    Returns:
        list[dict]: 模拟评分结果列表。
    """
    result = []
    for i in range(len(cases)):
        result.append(
            _normalize_judgement(
                {
                    "index": i,
                    "relevance": 5 - (i % 2),
                    "executability": 4,
                    "verifiability": 4 + (i % 2),
                    "hallucination": False,
                }
            )
        )
    return result


def _cases_to_prompt(feature_item: dict, cases: list[dict]) -> str:
    """将功能点和待评分用例列表组装为传给 LLM 的评分 prompt。

    Args:
        feature_item (dict): 功能点字典。
        cases (list[dict]): 待评分的用例列表。

    Returns:
        str: 组装好的评分 prompt 字符串。
    """
    lines = [
        "功能点：",
        json.dumps(feature_item, ensure_ascii=False, indent=2),
        "",
        "待评分用例：",
    ]
    for idx, case in enumerate(cases):
        steps = case.get("steps")
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except json.JSONDecodeError:
                steps = [steps]
        lines.append(
            json.dumps(
                {
                    "index": idx,
                    "title": case.get("title", ""),
                    "precondition": case.get("precondition", ""),
                    "steps": steps or [],
                    "expected_result": case.get("expected_result", ""),
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


async def run(inputs: dict, context: SkillContext) -> dict:
    """对功能点下的一组测试用例进行 AI 评分。

    从相关性、可执行性、可验证性三个维度评分（1~5），检测幻觉，使用评测专用模型避免自评偏置。
    mock 模式下返回模拟评分。

    Args:
        inputs (dict): 包含 feature_item（功能点）和 cases（用例列表）的字典。
        context (SkillContext): 技能执行上下文。

    Returns:
        dict: 包含 judgements（评分结果列表）的结果字典。
    """
    feature_item = inputs["feature_item"]
    cases = inputs["cases"]
    if not cases:
        return {"judgements": []}

    if context.use_mock:
        return {"judgements": _mock_judgements(cases)}

    prompt = load_prompt(SKILL_DIR, "prompt.md")
    user_prompt = _cases_to_prompt(feature_item, cases)
    # Judge 用评测专用模型，与生成模型分离，避免"自评偏置"
    text = await chat_completion(prompt, user_prompt, use_eval_model=True)

    data = parse_json_response(text)
    raw_list = data.get("judgements", []) if isinstance(data, dict) else data
    if not isinstance(raw_list, list):
        raw_list = []

    # 按 index 对齐，缺失的条目不返回评分（保持未评状态）
    judgements = []
    seen = set()
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        item = _normalize_judgement(raw)
        idx = item["index"]
        if isinstance(idx, int) and 0 <= idx < len(cases) and idx not in seen:
            seen.add(idx)
            judgements.append(item)
    return {"judgements": judgements}
