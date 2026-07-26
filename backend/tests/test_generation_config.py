import json
import unittest
from types import SimpleNamespace

from app.services.generation_service import build_strategy_config_payload
from app.services.settings_service import RuntimeModelConfig


class GenerationConfigSnapshotTests(unittest.TestCase):
    def test_snapshot_contains_reproducibility_fields_without_api_keys(self):
        data = SimpleNamespace(
            strategy="quick",
            specialist_skills=["security"],
            use_knowledge=True,
        )
        model_config = RuntimeModelConfig(
            llm_api_key="generation-secret",
            llm_base_url="https://api.openai.com/v1",
            llm_model="generation-model",
            eval_llm_api_key="evaluation-secret",
            eval_llm_base_url="https://api.openai.com/v1",
            eval_llm_model="evaluation-model",
            embedding_api_key="embedding-secret",
            embedding_model="embedding-model",
        )

        raw = build_strategy_config_payload(data, model_config)
        snapshot = json.loads(raw)

        self.assertEqual(snapshot["workflow_version"], "langgraph-v1")
        self.assertEqual(snapshot["strategy"], "quick")
        self.assertEqual(snapshot["specialist_skills"], ["security"])
        self.assertTrue(snapshot["use_knowledge"])
        self.assertIn("case_writer", snapshot["skill_versions"])
        self.assertIn("case_writer", snapshot["prompt_fingerprints"])
        self.assertEqual(snapshot["generation_parameters"]["temperature"], 0.3)
        self.assertEqual(snapshot["models"]["generation"]["model"], "generation-model")
        self.assertEqual(snapshot["retrieval"]["mode"], "vector_bm25_rrf_optional_rerank")
        self.assertEqual(snapshot["retrieval"]["embedding_adapter"], "langchain_openai")
        self.assertEqual(snapshot["retrieval"]["vector_store"], "langchain_chroma")
        self.assertEqual(snapshot["retrieval"]["collection_version"], "lc_v1")
        self.assertNotIn("generation-secret", raw)
        self.assertNotIn("evaluation-secret", raw)
        self.assertNotIn("embedding-secret", raw)


if __name__ == "__main__":
    unittest.main()
