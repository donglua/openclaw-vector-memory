# tests/test_store_remote_rerank.py
import unittest
from unittest.mock import MagicMock, patch

from memory.store import MemoryStore


class TestStoreRemoteRerank(unittest.TestCase):
    @patch("memory.store.MilvusClient")
    @patch("memory.store.Embedder")
    def test_remote_rerank_reorders_candidates(self, mock_embedder_factory, mock_milvus_cls):
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = ([0.1, 0.2], {})
        mock_embedder_factory.return_value = mock_embedder

        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_client.search.return_value = [[
            {"entity": {"text": "A", "source": "s1"}, "distance": 0.61},
            {"entity": {"text": "B", "source": "s2"}, "distance": 0.60},
            {"entity": {"text": "C", "source": "s3"}, "distance": 0.59},
        ]]
        mock_milvus_cls.return_value = mock_client

        store = MemoryStore(uri="u", token="t", collection_name="c")
        store._rerank_config.enabled = True
        store._rerank_config.force = True
        store._reranker = MagicMock()
        store._reranker.rerank.return_value = [2, 0, 1]

        hits = store.search("q", top_k=2)
        self.assertEqual([h["text"] for h in hits], ["C", "A"])

    @patch("memory.store.MilvusClient")
    @patch("memory.store.Embedder")
    def test_remote_rerank_failure_fallback(self, mock_embedder_factory, mock_milvus_cls):
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = ([0.1, 0.2], {})
        mock_embedder_factory.return_value = mock_embedder

        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_client.search.return_value = [[
            {"entity": {"text": "A", "source": "s1"}, "distance": 0.61},
            {"entity": {"text": "B", "source": "s2"}, "distance": 0.60},
        ]]
        mock_milvus_cls.return_value = mock_client

        store = MemoryStore(uri="u", token="t", collection_name="c")
        store._rerank_config.enabled = True
        store._rerank_config.force = True
        store._reranker = MagicMock()
        store._reranker.rerank.side_effect = RuntimeError("timeout")

        hits = store.search("q", top_k=2)
        self.assertEqual([h["text"] for h in hits], ["A", "B"])


if __name__ == "__main__":
    unittest.main()
