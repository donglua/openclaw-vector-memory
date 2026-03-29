# tests/test_rerank_config.py
import os
import unittest
from unittest.mock import patch

from memory.rerank_config import RerankConfig


class TestRerankConfig(unittest.TestCase):
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = RerankConfig.from_env()
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.provider, "llm")
        self.assertEqual(cfg.fetch_k, 40)
        self.assertEqual(cfg.timeout_ms, 8000)
        self.assertEqual(cfg.flat_gap_threshold, 0.03)
        self.assertEqual(cfg.low_conf_threshold, 0.45)
        self.assertEqual(cfg.min_candidates, 8)
        self.assertFalse(cfg.force)
        self.assertFalse(cfg.debug)

    def test_env_overrides(self):
        with patch.dict(
            os.environ,
            {
                "RERANK_ENABLED": "false",
                "RERANK_PROVIDER": "llm",
                "RERANK_MODEL": "gpt-4.1-mini",
                "RERANK_FETCH_K": "64",
                "RERANK_TIMEOUT_MS": "12000",
                "RERANK_FLAT_GAP_THRESHOLD": "0.07",
                "RERANK_LOW_CONF_THRESHOLD": "0.52",
                "RERANK_MIN_CANDIDATES": "12",
                "RERANK_FORCE": "1",
                "RERANK_DEBUG": "true",
            },
            clear=True,
        ):
            cfg = RerankConfig.from_env()
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.model, "gpt-4.1-mini")
        self.assertEqual(cfg.fetch_k, 64)
        self.assertEqual(cfg.timeout_ms, 12000)
        self.assertAlmostEqual(cfg.flat_gap_threshold, 0.07)
        self.assertAlmostEqual(cfg.low_conf_threshold, 0.52)
        self.assertEqual(cfg.min_candidates, 12)
        self.assertTrue(cfg.force)
        self.assertTrue(cfg.debug)


if __name__ == "__main__":
    unittest.main()
