import unittest

from app.workflows.generation.graph import build_generation_graph
from app.workflows.generation.nodes import (
    _structured_output_failure,
    route_after_generation,
    route_after_validation,
    route_next_feature,
)


class GenerationGraphRoutingTests(unittest.TestCase):
    def test_graph_contains_expected_nodes(self):
        nodes = set(build_generation_graph().get_graph().nodes)
        self.assertTrue(
            {
                "load_task",
                "retrieve_knowledge",
                "generate_core_cases",
                "generate_specialist_cases",
                "validate_cases",
                "detect_duplicates",
                "run_judge",
                "build_report",
                "finalize_task",
            }.issubset(nodes)
        )

    def test_structured_error_routes_to_retry_node(self):
        state = {"generation_error": "invalid json", "retry_count": 0}
        self.assertEqual(route_after_generation(state), "retry")

    def test_second_structured_error_fails_at_generation_node_for_resumability(self):
        from langchain_core.exceptions import OutputParserException

        error = OutputParserException("invalid json")
        self.assertIn(
            "invalid json",
            _structured_output_failure({"retry_count": 0}, error)["generation_error"],
        )
        with self.assertRaises(RuntimeError):
            _structured_output_failure({"retry_count": 1}, error)

    def test_empty_valid_cases_retries_once_then_persists_uncovered_feature(self):
        self.assertEqual(route_after_validation({"current_cases": [], "retry_count": 0}), "retry")
        self.assertEqual(route_after_validation({"current_cases": [], "retry_count": 1}), "persist")

    def test_feature_loop_routes_to_quality_after_last_item(self):
        self.assertEqual(route_next_feature({"feature_index": 1, "feature_ids": [1, 2]}), "next")
        self.assertEqual(route_next_feature({"feature_index": 2, "feature_ids": [1, 2]}), "quality")


if __name__ == "__main__":
    unittest.main()
