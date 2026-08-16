"""测试助手 runner 单测：Mock 模式事件序列与历史消息裁剪。"""

import asyncio
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.agent.runner import HISTORY_LIMIT, _history_messages, run_agent
from app.database import Base
from app.models.testcase import TestCase
from app.services.settings_service import RuntimeModelConfig


async def _collect(iterator) -> list[dict]:
    return [event async for event in iterator]


class MockModeRunnerTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add(TestCase(project_id=1, title="用例A", expected_result="ok"))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_mock_event_sequence(self):
        # 默认 RuntimeModelConfig 无 API Key，use_mock_llm 为 True
        events = asyncio.run(_collect(run_agent(
            self.db, 1, "演示项目", "通过率怎么样", [], RuntimeModelConfig(),
        )))

        types = [e["type"] for e in events]
        self.assertEqual(types[0], "tool_start")
        self.assertEqual(events[0]["name"], "search_knowledge")
        self.assertEqual(types[1], "tool_end")
        self.assertIn("token", types)
        self.assertEqual(types[-1], "done")

        done = events[-1]
        self.assertIn("Mock 模式", done["content"])
        self.assertIn("1 条测试用例", done["content"])
        self.assertEqual(done["tool_calls"], [{"name": "search_knowledge"}])
        self.assertEqual(done.get("pending_insight_ids"), [])
        # token 事件拼接后应与最终回答一致
        streamed = "".join(e["content"] for e in events if e["type"] == "token")
        self.assertEqual(streamed, done["content"])

    def test_mock_design_parse_script(self):
        from app.models.design import DesignAsset, DesignInsight
        from app.models.project import Project
        from app.models.requirement import RequirementDocument
        from app.models.user import User

        self.db.add_all([
            User(id=1, username="u", password_hash="x"),
            Project(id=1, name="p", user_id=1),
            RequirementDocument(id=1, project_id=1, title="需求", status="structured"),
            DesignAsset(
                id=5,
                project_id=1,
                document_id=1,
                asset_type="image",
                title="截图",
                content_type="image/png",
                storage_path="1/1/x.png",
                status="uploaded",
            ),
        ])
        self.db.commit()

        with patch("app.agent.runner.design_service.parse_asset") as mock_parse:
            async def _fake_parse(db, project_id, asset_id):
                asset = db.get(DesignAsset, asset_id)
                db.add(DesignInsight(
                    asset_id=asset.id,
                    module="页面",
                    feature="提交",
                    description="提交表单",
                    priority="P1",
                    selected=True,
                ))
                asset.status = "parsed"
                db.commit()
                db.refresh(asset)
                return asset

            mock_parse.side_effect = _fake_parse
            events = asyncio.run(_collect(run_agent(
                self.db, 1, "演示项目", "请解析", [], RuntimeModelConfig(),
                document_id=1,
                attachments=[{"asset_id": 5, "asset_type": "image", "title": "截图"}],
            )))

        done = events[-1]
        self.assertEqual(done["type"], "done")
        self.assertEqual(done["tool_calls"], [{"name": "parse_design_asset"}])
        self.assertTrue(done["pending_insight_ids"])
        self.assertIn("确认", done["content"])


class HistoryMessagesTests(unittest.TestCase):
    def test_roles_and_order(self):
        messages = _history_messages([("user", "问1"), ("assistant", "答1")])
        self.assertEqual(messages[0].content, "问1")
        self.assertEqual(messages[0].type, "human")
        self.assertEqual(messages[1].type, "ai")

    def test_limit_and_empty_content_skipped(self):
        history = [("user", f"问{i}") for i in range(HISTORY_LIMIT + 5)] + [("assistant", "")]
        messages = _history_messages(history)
        self.assertLessEqual(len(messages), HISTORY_LIMIT)
        self.assertTrue(all(m.content for m in messages))


if __name__ == "__main__":
    unittest.main()
