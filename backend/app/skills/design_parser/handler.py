from pathlib import Path

from app.ai.chains import parse_design_image
from app.skills.base import SkillContext
from app.skills.shared.prompt_loader import load_prompt

SKILL_DIR = Path(__file__).resolve().parent

MOCK_SOURCE = "mock"

MOCK_DESIGN_INSIGHTS = [
    {
        "page": "示例页面（Mock 数据，未调用视觉模型）",
        "module": "页面交互",
        "feature": "提交表单",
        "description": "用户填写必填信息后提交表单",
        "acceptance_criteria": "必填信息完整时提交按钮可用，提交后展示成功反馈",
        "constraints": "必填项为空时按钮保持禁用",
        "priority": "P1",
    },
]


async def run(inputs: dict, context: SkillContext) -> dict:
    """返回 insights / source / is_design / image_summary，供上层如实处理。"""
    if context.use_mock:
        return {
            "insights": MOCK_DESIGN_INSIGHTS,
            "source": MOCK_SOURCE,
            "is_design": True,
            "image_summary": "",
        }
    prompt = load_prompt(SKILL_DIR, "prompt.md")
    result = await parse_design_image(
        prompt,
        inputs["image_data"],
        inputs["content_type"],
        context.model_config,
    )
    return {
        "insights": result.get("features") or [],
        "source": f"vision:{context.model_config.vision_model}",
        "is_design": bool(result.get("is_design", True)),
        "image_summary": result.get("image_summary") or "",
    }
