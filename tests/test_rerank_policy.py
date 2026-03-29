# tests/test_rerank_policy.py
import unittest

from memory.rerank_policy import should_rerank, merge_reranked_candidates


class TestRerankPolicy(unittest.TestCase):
    def test_force_always_triggers(self):
        should, reason = should_rerank(
            scores=[0.91, 0.89, 0.88],
            top_k=3,
            min_candidates=3,
            flat_gap_threshold=0.01,
            low_conf_threshold=0.2,
            force=True,
        )
        self.assertTrue(should)
        self.assertEqual(reason, "force")

    def test_not_enough_candidates(self):
        should, reason = should_rerank(
            scores=[0.9, 0.8],
            top_k=5,
            min_candidates=8,
            flat_gap_threshold=0.03,
            low_conf_threshold=0.45,
            force=False,
        )
        self.assertFalse(should)
        self.assertEqual(reason, "insufficient_candidates")

    def test_flat_gap_triggers(self):
        should, reason = should_rerank(
            scores=[0.57, 0.56, 0.55, 0.54, 0.54],
            top_k=5,
            min_candidates=5,
            flat_gap_threshold=0.05,
            low_conf_threshold=0.2,
            force=False,
        )
        self.assertTrue(should)
        self.assertEqual(reason, "flat_gap")

    def test_low_conf_triggers(self):
        should, reason = should_rerank(
            scores=[0.30, 0.20, 0.10],
            top_k=3,
            min_candidates=3,
            flat_gap_threshold=0.01,
            low_conf_threshold=0.4,
            force=False,
        )
        self.assertTrue(should)
        self.assertEqual(reason, "low_conf")

    def test_merge_reranked_candidates_sanitizes_and_fills(self):
        candidates = [{"id": i} for i in range(5)]
        merged = merge_reranked_candidates(
            candidates=candidates,
            reranked_indices=[3, 3, 10, -1, 1],
            top_k=4,
        )
        self.assertEqual([c["id"] for c in merged], [3, 1, 0, 2])


if __name__ == "__main__":
    unittest.main()
