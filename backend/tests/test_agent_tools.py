"""测试助手工具层单测：项目隔离、筛选、截断与空数据兜底。

全部走内存 SQLite，search_knowledge 通过 mock retrieve 验证格式化与截断。
"""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  确保所有表注册到 Base.metadata
from app.agent.tools import MAX_LIST_ITEMS, SNIPPET_CHARS, build_agent_tools
from app.database import Base
from app.models.execution import TestBatch, TestBatchCase, TestTask
from app.models.requirement import RequirementDocument, RequirementItem
from app.models.testcase import TestCase
from app.services.settings_service import RuntimeModelConfig

PROJECT_ID = 1
OTHER_PROJECT_ID = 2


class AgentToolsTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self._seed()
        tools = build_agent_tools(self.db, PROJECT_ID, RuntimeModelConfig())
        self.tools = {t.name: t for t in tools}

    def tearDown(self):
        self.db.close()

    def _seed(self):
        doc = RequirementDocument(
            id=1, project_id=PROJECT_ID, title="需求", status="confirmed"
        )
        items = [
            RequirementItem(
                id=1, document_id=1, module="支付", feature="退款", confirmed=True
            ),
            RequirementItem(
                id=2, document_id=1, module="支付", feature="对账", confirmed=True
            ),
            RequirementItem(
                id=3,
                document_id=1,
                module="账户",
                feature="草稿功能点",
                confirmed=False,
            ),
        ]
        cases = [
            TestCase(
                id=1,
                project_id=PROJECT_ID,
                requirement_item_id=1,
                title="退款成功路径",
                priority="P0",
                case_type="functional",
                steps="1. 发起退款",
                expected_result="退款成功",
            ),
            TestCase(
                id=2,
                project_id=PROJECT_ID,
                requirement_item_id=1,
                title="退款金额超限",
                priority="P1",
                case_type="boundary",
                expected_result="提示金额超限",
            ),
            TestCase(
                id=3,
                project_id=OTHER_PROJECT_ID,
                title="其他项目的用例",
                priority="P0",
                expected_result="不应出现",
            ),
        ]
        task = TestTask(id=1, project_id=PROJECT_ID, name="预发验证")
        batch = TestBatch(id=1, task_id=1, name="预发测试")
        batch_cases = [
            TestBatchCase(id=1, batch_id=1, case_id=1, result="passed"),
            TestBatchCase(
                id=2,
                batch_id=1,
                case_id=2,
                result="failed",
                note="金额校验缺失",
                defect_ref="BUG-1",
            ),
        ]
        self.db.add_all([doc, *items, *cases, task, batch, *batch_cases])
        self.db.commit()

    # ---- list_testcases ----

    def test_list_testcases_scoped_to_project(self):
        data = json.loads(self.tools["list_testcases"].invoke({}))
        self.assertEqual(data["total"], 2)
        self.assertTrue(all(c["title"] != "其他项目的用例" for c in data["cases"]))

    def test_list_testcases_filters(self):
        data = json.loads(self.tools["list_testcases"].invoke({"priority": "p0"}))
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["cases"][0]["title"], "退款成功路径")

        data = json.loads(self.tools["list_testcases"].invoke({"keyword": "超限"}))
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["cases"][0]["case_type"], "boundary")

    def test_list_testcases_truncation_note(self):
        for i in range(MAX_LIST_ITEMS + 5):
            self.db.add(
                TestCase(
                    project_id=PROJECT_ID, title=f"批量用例{i}", expected_result="ok"
                )
            )
        self.db.commit()
        data = json.loads(self.tools["list_testcases"].invoke({"limit": 999}))
        self.assertEqual(data["returned"], MAX_LIST_ITEMS)
        self.assertIn("仅返回前", data["note"])

    # ---- get_testcase_detail ----

    def test_get_testcase_detail(self):
        data = json.loads(self.tools["get_testcase_detail"].invoke({"case_id": 1}))
        self.assertEqual(data["title"], "退款成功路径")
        self.assertEqual(data["module"], "支付")
        self.assertEqual(data["steps"], "1. 发起退款")

    def test_get_testcase_detail_cross_project_denied(self):
        data = json.loads(self.tools["get_testcase_detail"].invoke({"case_id": 3}))
        self.assertIn("error", data)

    # ---- get_coverage_summary ----

    def test_coverage_summary(self):
        data = json.loads(self.tools["get_coverage_summary"].invoke({}))
        # 已确认 2 个功能点，只有「退款」有用例；未确认的草稿功能点不参与统计
        self.assertEqual(data["confirmed_features"], 2)
        self.assertEqual(data["covered_features"], 1)
        self.assertEqual(data["coverage_rate"], 50.0)
        self.assertEqual(data["uncovered"], [{"module": "支付", "feature": "对账"}])

    def test_coverage_summary_without_confirmed_items(self):
        tools = {
            t.name: t
            for t in build_agent_tools(self.db, OTHER_PROJECT_ID, RuntimeModelConfig())
        }
        data = json.loads(tools["get_coverage_summary"].invoke({}))
        self.assertIn("message", data)

    # ---- get_test_task_stats ----

    def test_task_stats(self):
        data = json.loads(self.tools["get_test_task_stats"].invoke({}))
        task = data["tasks"][0]
        self.assertEqual(task["name"], "预发验证")
        self.assertEqual(task["stats"]["passed"], 1)
        self.assertEqual(task["stats"]["failed"], 1)
        self.assertEqual(task["stats"]["pass_rate"], 50.0)
        self.assertEqual(task["batches"][0]["name"], "预发测试")

    def test_task_stats_name_filter_no_match(self):
        data = json.loads(
            self.tools["get_test_task_stats"].invoke({"task_name": "不存在"})
        )
        self.assertIn("message", data)

    # ---- list_defects ----

    def test_list_defects(self):
        data = json.loads(self.tools["list_defects"].invoke({}))
        self.assertEqual(len(data["defects"]), 1)
        defect = data["defects"][0]
        self.assertEqual(defect["title"], "退款金额超限")
        self.assertEqual(defect["defect_ref"], "BUG-1")
        self.assertEqual(defect["task"], "预发验证")

    def test_list_defects_exclude_blocked(self):
        self.db.add(
            TestCase(
                id=4, project_id=PROJECT_ID, title="阻塞用例", expected_result="ok"
            )
        )
        self.db.add(TestBatchCase(id=3, batch_id=1, case_id=4, result="blocked"))
        self.db.commit()
        with_blocked = json.loads(
            self.tools["list_defects"].invoke({"include_blocked": True})
        )
        without = json.loads(
            self.tools["list_defects"].invoke({"include_blocked": False})
        )
        self.assertEqual(len(with_blocked["defects"]), 2)
        self.assertEqual(len(without["defects"]), 1)

    # ---- search_knowledge ----

    def test_search_knowledge_formats_and_clips(self):
        long_content = "规" * (SNIPPET_CHARS + 100)
        with patch(
            "app.agent.tools.knowledge_service.retrieve",
            new=AsyncMock(
                return_value=[
                    {
                        "content": long_content,
                        "title": "退款规则",
                        "heading": "支付 > 退款",
                        "source_type": "doc",
                        "score": 0.9,
                        "match": "both",
                    },
                ]
            ),
        ):
            data = json.loads(
                asyncio.run(self.tools["search_knowledge"].ainvoke({"query": "退款"}))
            )
        hit = data["hits"][0]
        self.assertEqual(hit["title"], "退款规则")
        self.assertEqual(hit["match"], "both")
        self.assertLess(len(hit["content"]), len(long_content))
        self.assertIn("已截断", hit["content"])

    def test_search_knowledge_no_hits(self):
        with patch(
            "app.agent.tools.knowledge_service.retrieve", new=AsyncMock(return_value=[])
        ):
            data = json.loads(
                asyncio.run(self.tools["search_knowledge"].ainvoke({"query": "x"}))
            )
        self.assertEqual(data["hits"], [])
        self.assertIn("message", data)

    def test_search_knowledge_error_degrades(self):
        with patch(
            "app.agent.tools.knowledge_service.retrieve",
            new=AsyncMock(side_effect=RuntimeError("embedding down")),
        ):
            data = json.loads(
                asyncio.run(self.tools["search_knowledge"].ainvoke({"query": "x"}))
            )
        self.assertIn("error", data)

    def test_design_tools_registered(self):
        for name in (
            "list_requirement_documents",
            "list_design_assets",
            "parse_design_asset",
            "get_design_insights",
            "merge_design_insights",
        ):
            self.assertIn(name, self.tools)

    def test_merge_requires_confirmed(self):
        data = json.loads(
            self.tools["merge_design_insights"].invoke(
                {
                    "document_id": 1,
                    "insight_ids": [1],
                    "confirmed": False,
                }
            )
        )
        self.assertIn("error", data)
        self.assertIn("confirmed", data["error"])

    def test_list_design_assets_project_scoped(self):
        from app.models.design import DesignAsset

        self.db.add(
            DesignAsset(
                id=10,
                project_id=PROJECT_ID,
                document_id=1,
                asset_type="image",
                title="登录页",
                status="uploaded",
            )
        )
        self.db.commit()
        data = json.loads(self.tools["list_design_assets"].invoke({"document_id": 1}))
        self.assertEqual(len(data["assets"]), 1)
        self.assertEqual(data["assets"][0]["title"], "登录页")

        other_tools = {
            t.name: t
            for t in build_agent_tools(self.db, OTHER_PROJECT_ID, RuntimeModelConfig())
        }
        data = json.loads(other_tools["list_design_assets"].invoke({"document_id": 1}))
        self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
