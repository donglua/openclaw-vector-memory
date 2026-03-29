# tests/test_reranker.py
import unittest
from unittest.mock import MagicMock, patch

from memory.reranker import LLMReranker, APIReranker, RerankError


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


class TestAPIReranker(unittest.TestCase):
    @patch("memory.reranker.requests.post")
    def test_returns_ranked_indices_by_score(self, mock_post):
        """验证 APIReranker 按 relevance_score 降序返回索引"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.3},
                {"index": 1, "relevance_score": 0.9},
                {"index": 2, "relevance_score": 0.7},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        reranker = APIReranker(
            api_base="https://api.example.com/v1",
            api_key="test-key",
            model="BAAI/bge-reranker-v2-m3",
            timeout_ms=5000,
        )
        indices = reranker.rerank(
            query="测试查询",
            candidates=[{"text": "A"}, {"text": "B"}, {"text": "C"}],
        )
        # 按 score 排序：B(0.9) > C(0.7) > A(0.3)
        self.assertEqual(indices, [1, 2, 0])

        # 验证请求参数
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://api.example.com/v1/rerank")
        self.assertEqual(call_args[1]["json"]["model"], "BAAI/bge-reranker-v2-m3")
        self.assertEqual(call_args[1]["json"]["documents"], ["A", "B", "C"])

    @patch("memory.reranker.requests.post")
    def test_request_failure_raises(self, mock_post):
        """验证网络请求失败时抛出 RerankError"""
        import requests as req
        mock_post.side_effect = req.ConnectionError("unreachable")

        reranker = APIReranker(
            api_base="https://api.example.com/v1",
            api_key="test-key",
            model="BAAI/bge-reranker-v2-m3",
            timeout_ms=5000,
        )
        with self.assertRaises(RerankError):
            reranker.rerank(query="q", candidates=[{"text": "A"}])


if __name__ == "__main__":
    unittest.main()
