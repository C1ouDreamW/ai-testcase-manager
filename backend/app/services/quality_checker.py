import json


def normalize_steps(case: dict) -> tuple[str, list[str]]:
    """格式化并清理测试用例的操作步骤。

    如果 steps 是 JSON 字符串则尝试解析为列表，如果解析失败则按换行分割；
    非列表格式会转换为列表；去除空字符串和前后空格。

    Args:
        case (dict): 包含 steps 字段的测试用例字典。

    Returns:
        tuple[str, list[str]]: (JSON 字符串格式的步骤, 清理后的步骤列表)。
    """
    steps = case.get("steps", [])
    if isinstance(steps, str):
        text = steps.strip()
        if not text:
            return "[]", []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                steps = parsed
            else:
                steps = [str(parsed)]
        except json.JSONDecodeError:
            steps = [s.strip() for s in text.split("\n") if s.strip()]
    elif not isinstance(steps, list):
        steps = []

    cleaned = [str(s).strip() for s in steps if str(s).strip()]
    return json.dumps(cleaned, ensure_ascii=False), cleaned


def is_meaningful_case(case: dict, steps: list[str]) -> bool:
    """判断测试用例是否有实际内容，过滤空标题的无效用例。

    Args:
        case (dict): 测试用例字典。
        steps (list[str]): 已格式化的步骤列表。

    Returns:
        bool: 如果用例有标题且至少包含步骤或预期结果，则返回 True。
    """
    title = (case.get("title") or "").strip()
    expected = (case.get("expected_result") or "").strip()
    if not title:
        return False
    return bool(steps or expected)


def check_case(case: dict) -> tuple[str, list[str]]:
    """对单条测试用例进行规则化质量检查。

    检查项包括：标题缺失、预期结果缺失、步骤缺失、步骤过短不可执行、
    预期结果包含模糊词。

    Args:
        case (dict): 测试用例字典。

    Returns:
        tuple[str, list[str]]: (status, issues)，status 为 pass/warning/fail。
    """
    issues = []

    title = (case.get("title") or "").strip()
    if not title:
        issues.append("缺少标题")
    if not (case.get("expected_result") or "").strip():
        issues.append("缺少预期结果")

    steps = case.get("steps", [])
    if isinstance(steps, str):
        try:
            steps = json.loads(steps)
        except json.JSONDecodeError:
            steps = [s.strip() for s in steps.split("\n") if s.strip()]

    if not steps:
        issues.append("缺少操作步骤")

    for step in steps:
        if len(step) < 4:
            issues.append(f"步骤过短不可执行: {step}")
        vague_words = ["正常", "合理", "体验良好", "系统正确"]
        for word in vague_words:
            if word in case.get("expected_result", ""):
                issues.append(f"预期结果不可验证，包含模糊词: {word}")
                break

    if len(issues) == 0:
        return "pass", []
    if len(issues) <= 1:
        return "warning", issues
    return "fail", issues


def _trigrams(text: str) -> set[str]:
    """将文本拆分为三字符词组集合，用于计算文本相似度。

    Args:
        text (str): 输入文本。

    Returns:
        set[str]: 三字符词组集合。
    """
    text = "".join(text.split())
    if len(text) < 3:
        return {text} if text else set()
    return {text[i:i + 3] for i in range(len(text) - 2)}


def _similarity(a: str, b: str) -> float:
    """基于三字符词组的 Jaccard 相似度计算。

    Args:
        a (str): 文本 A。
        b (str): 文本 B。

    Returns:
        float: 相似度值，范围 [0.0, 1.0]。
    """
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


DUPLICATE_THRESHOLD = 0.8


def detect_duplicates(drafts: list) -> int:
    """在同一功能点内通过文本相似度检测疑似重复用例。

    将每个功能点内的用例两两比对（标题 + 步骤），相似度达到阈值时标记后出现的用例。
    只标记后出现的那条，保留先出现的用例不受影响。

    Args:
        drafts (list): GeneratedCaseDraft 对象列表。

    Returns:
        int: 检测到的重复用例条数。
    """
    by_item: dict = {}
    for d in drafts:
        by_item.setdefault(d.requirement_item_id, []).append(d)

    duplicate_count = 0
    for group in by_item.values():
        for i in range(1, len(group)):
            current = group[i]
            text_i = f"{current.title} {current.steps}"
            for j in range(i):
                other = group[j]
                if _similarity(text_i, f"{other.title} {other.steps}") >= DUPLICATE_THRESHOLD:
                    duplicate_count += 1
                    try:
                        issues = json.loads(current.quality_issues or "[]")
                    except json.JSONDecodeError:
                        issues = []
                    issues.append(f"与用例<{other.title}>疑似重复")
                    current.quality_issues = json.dumps(issues, ensure_ascii=False)
                    if current.quality_status == "pass":
                        current.quality_status = "warning"
                    break
    return duplicate_count


def judge_summary(drafts: list) -> tuple[float | None, int]:
    """从草稿的 AI Judge 评分字段汇总平均综合分和幻觉数。

    Args:
        drafts (list): GeneratedCaseDraft 对象列表。

    Returns:
        tuple[float | None, int]: (平均综合分, 幻觉标记数量)。
    """
    scores = [d.judge_score for d in drafts if d.judge_score is not None]
    avg = round(sum(scores) / len(scores), 2) if scores else None
    hallucination = 0
    for d in drafts:
        try:
            data = json.loads(d.judge_issues or "{}")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("hallucination"):
            hallucination += 1
    return avg, hallucination


def build_quality_report(
    drafts: list,
    requirement_items: list,
    item_case_map: dict[int, list],
    duplicate_count: int = 0,
) -> dict:
    """汇总所有草稿的质检结果，生成质检报告。

    计算通过率、覆盖率、AI 评分汇总、幻觉检测、重复检测，并生成改进建议。

    Args:
        drafts (list): GeneratedCaseDraft 对象列表。
        requirement_items (list): RequirementItem 对象列表。
        item_case_map (dict[int, list]): 功能点 ID 到用例列表的映射。
        duplicate_count (int, optional): 重复用例数量。默认为 0。

    Returns:
        dict: 质检报告字典。
    """
    total = len(drafts)
    pass_count = sum(1 for d in drafts if d.quality_status == "pass")
    warning_count = sum(1 for d in drafts if d.quality_status == "warning")
    fail_count = sum(1 for d in drafts if d.quality_status == "fail")

    confirmed_items = [i for i in requirement_items if i.confirmed]
    covered_ids = {item_id for item_id, cases in item_case_map.items() if cases}
    uncovered = [i.feature for i in confirmed_items if i.id not in covered_ids]
    coverage = (len(covered_ids) / len(confirmed_items) * 100) if confirmed_items else 0

    avg_judge_score, hallucination_count = judge_summary(drafts)

    suggestions = []
    if uncovered:
        suggestions.append(f"以下功能点尚未覆盖用例: {', '.join(uncovered)}")
    if fail_count > 0:
        suggestions.append(f"有 {fail_count} 条用例质量不合格，建议重新生成或人工编辑")
    if coverage < 80:
        suggestions.append("覆盖率偏低，建议补充异常和边界场景")
    if hallucination_count > 0:
        suggestions.append(f"AI 评分标记了 {hallucination_count} 条疑似幻觉用例（编造了需求中没有的规则），请评审时重点核对")
    if duplicate_count > 0:
        suggestions.append(f"检测到 {duplicate_count} 条疑似重复用例，建议去重后采纳")

    return {
        "total_cases": total,
        "pass_count": pass_count,
        "warning_count": warning_count,
        "fail_count": fail_count,
        "coverage_rate": round(coverage, 1),
        "uncovered_features": json.dumps(uncovered, ensure_ascii=False),
        "suggestions": "\n".join(suggestions) if suggestions else "质量良好，可进行人工评审",
        "avg_judge_score": avg_judge_score,
        "hallucination_count": hallucination_count,
        "duplicate_count": duplicate_count,
    }
