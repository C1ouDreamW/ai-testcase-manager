import unittest
from unittest.mock import MagicMock, patch

from app.ai.model_factory import create_chat_model
from app.services.settings_service import RuntimeModelConfig


class ChatModelFactoryTests(unittest.TestCase):
    @patch("app.ai.model_factory.ChatOpenAI")
    @patch("app.ai.model_factory.httpx.AsyncClient")
    def test_chat_model_ignores_machine_proxy(self, async_client_cls, chat_openai_cls):
        http_client = MagicMock()
        async_client_cls.return_value = http_client
        config = RuntimeModelConfig(
            llm_api_key="test-key",
            llm_base_url="https://api.openai.com/v1",
            llm_model="test-model",
        )

        create_chat_model(config)

        async_client_cls.assert_called_once_with(timeout=120.0, trust_env=False)
        self.assertIs(chat_openai_cls.call_args.kwargs["http_async_client"], http_client)

    @patch("app.ai.model_factory.ChatOpenAI")
    @patch("app.ai.model_factory.httpx.AsyncClient")
    def test_vision_model_uses_independent_config(self, async_client_cls, chat_openai_cls):
        config = RuntimeModelConfig(
            llm_api_key="text-key",
            llm_base_url="https://api.deepseek.com/v1",
            llm_model="deepseek-chat",
            vision_api_key="vision-key",
            vision_base_url="https://api.openai.com/v1",
            vision_model="gpt-4o-mini",
        )

        create_chat_model(config, "vision")

        kwargs = chat_openai_cls.call_args.kwargs
        self.assertEqual(kwargs["api_key"], "vision-key")
        self.assertEqual(kwargs["base_url"], "https://api.openai.com/v1")
        self.assertEqual(kwargs["model"], "gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()
