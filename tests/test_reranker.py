# tests/test_reranker.py
import unittest
from unittest.mock import MagicMock

from memory.reranker import LLMReranker, RerankError


class TestLLMReranker(unittest.TestCase):
    def test_returns_ranked_indices(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"ranked_indices": [2, 0, 1]}'
                    )
                )
            ]
        )

        reranker = LLMReranker(
            client=mock_client,
            model="gpt-4o-mini",
            timeout_ms=5000,
        )
        indices = reranker.rerank(
            query="用户喜欢什么语言",
            candidates=[{"text": "A"}, {"text": "B"}, {"text": "C"}],
        )
        self.assertEqual(indices, [2, 0, 1])

    def test_invalid_json_raises(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not json"))]
        )
        reranker = LLMReranker(client=mock_client, model="gpt-4o-mini", timeout_ms=5000)

        with self.assertRaises(RerankError):
            reranker.rerank(query="q", candidates=[{"text": "A"}])


if __name__ == "__main__":
    unittest.main()
