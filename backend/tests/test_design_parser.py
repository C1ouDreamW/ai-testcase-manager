import asyncio
import unittest

from fastapi import HTTPException

from app.api.designs import _detect_image, _validate_figma_url
from app.services.settings_service import RuntimeModelConfig
from app.skills.base import SkillContext
from app.skills.registry import get_registry


class DesignValidationTests(unittest.TestCase):
    def test_detects_supported_image_signatures(self):
        self.assertEqual(_detect_image(b"\x89PNG\r\n\x1a\nrest"), (".png", "image/png"))
        self.assertEqual(_detect_image(b"\xff\xd8\xffrest"), (".jpg", "image/jpeg"))
        self.assertEqual(_detect_image(b"RIFF1234WEBPrest"), (".webp", "image/webp"))
        self.assertIsNone(_detect_image(b"<svg></svg>"))

    def test_figma_url_requires_official_https_host(self):
        value = "https://www.figma.com/design/abc/example"
        self.assertEqual(_validate_figma_url(value), value)
        for invalid in (
            "http://www.figma.com/design/abc",
            "https://figma.example.com/design/abc",
            "https://www.figma.com/community/file/abc",
        ):
            with self.assertRaises(HTTPException):
                _validate_figma_url(invalid)

    def test_design_parser_mock_is_stable(self):
        result = asyncio.run(get_registry().run(
            "design_parser",
            {"image_data": b"image", "content_type": "image/png"},
            SkillContext(model_config=RuntimeModelConfig(), use_mock=True),
        ))
        self.assertTrue(result["insights"])
        self.assertEqual(result["insights"][0]["feature"], "提交表单")
        self.assertEqual(result["source"], "mock")
        self.assertIn("Mock", result["insights"][0]["page"])

    def test_design_parser_vision_source_label(self):
        async def fake_parse(prompt, image_data, content_type, model_config):
            return {
                "is_design": True,
                "image_summary": "登录页",
                "features": [{"feature": "登录按钮", "module": "账号", "priority": "P0"}],
            }

        from unittest.mock import patch

        config = RuntimeModelConfig(
            vision_api_key="k",
            vision_base_url="https://example.com",
            vision_model="Qwen/Qwen3-VL-Demo",
        )
        # Skill handler 由 importlib 动态加载，需 patch 其自身 globals
        handler = get_registry()._handlers["design_parser"]
        with patch.dict(handler.__globals__, {"parse_design_image": fake_parse}):
            result = asyncio.run(handler(
                {"image_data": b"image", "content_type": "image/png"},
                SkillContext(model_config=config, use_mock=False),
            ))
        self.assertEqual(result["source"], "vision:Qwen/Qwen3-VL-Demo")
        self.assertTrue(result["is_design"])
        self.assertEqual(result["insights"][0]["feature"], "登录按钮")

    def test_design_parser_non_design_image(self):
        async def fake_parse(prompt, image_data, content_type, model_config):
            return {
                "is_design": False,
                "image_summary": "一张冰川风景照",
                "features": [],
            }

        from unittest.mock import patch

        config = RuntimeModelConfig(
            vision_api_key="k",
            vision_base_url="https://example.com",
            vision_model="Qwen/Qwen3-VL-Demo",
        )
        handler = get_registry()._handlers["design_parser"]
        with patch.dict(handler.__globals__, {"parse_design_image": fake_parse}):
            result = asyncio.run(handler(
                {"image_data": b"image", "content_type": "image/png"},
                SkillContext(model_config=config, use_mock=False),
            ))
        self.assertFalse(result["is_design"])
        self.assertEqual(result["insights"], [])
        self.assertEqual(result["image_summary"], "一张冰川风景照")


if __name__ == "__main__":
    unittest.main()
