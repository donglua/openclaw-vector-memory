# memory/reranker.py
"""重排适配器：支持专用 Reranker API 和通用 LLM Chat Completion 两种模式"""
from __future__ import annotations

import json
import requests
from dataclasses import dataclass

from openai import OpenAI


class RerankError(Exception):
    """重排失败异常"""
    pass


@dataclass
class APIReranker:
    """专用 Reranker API 适配器（硅基流动 /v1/rerank 兼容接口）"""
    api_base: str
    api_key: str
    model: str
    timeout_ms: int

    def rerank(self, query: str, candidates: list[dict]) -> list[int]:
        """调用 /v1/rerank 接口，返回按相关性排序的索引列表"""
        url = f"{self.api_base.rstrip('/')}/rerank"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "query": query,
            "documents": [c["text"] for c in candidates],
        }

        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout_ms / 1000,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RerankError(f"Reranker API request failed: {exc}") from exc

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise RerankError("Invalid reranker response JSON") from exc

        results = data.get("results")
        if not isinstance(results, list):
            raise RerankError("Missing 'results' in reranker response")

        # 按 relevance_score 降序排列，提取原始索引
        sorted_results = sorted(results, key=lambda r: r.get("relevance_score", 0), reverse=True)
        return [r["index"] for r in sorted_results]


@dataclass
class LLMReranker:
    """通用 LLM Chat Completion 重排适配器（备用方案）"""
    client: OpenAI
    model: str
    timeout_ms: int

    def __init__(self, client: OpenAI | None, model: str, timeout_ms: int):
        self.client = client  # 惰性初始化：None 时在首次 rerank() 调用时创建
        self.model = model
        self.timeout_ms = timeout_ms

    def _get_client(self) -> OpenAI:
        if self.client is None:
            self.client = OpenAI()
        return self.client

    def rerank(self, query: str, candidates: list[dict]) -> list[int]:
        """调用 LLM 对候选项重排，返回排序后的索引列表"""
        indexed = [f"{i}. {c['text']}" for i, c in enumerate(candidates)]
        prompt = (
            "Rank candidates by relevance to query. "
            "Return JSON only with key ranked_indices as integer array.\n"
            f"Query: {query}\nCandidates:\n" + "\n".join(indexed)
        )

        resp = self._get_client().chat.completions.create(
            model=self.model,
            temperature=0,
            timeout=self.timeout_ms / 1000,
            messages=[
                {"role": "system", "content": "You are a reranker."},
                {"role": "user", "content": prompt},
            ],
        )

        content = resp.choices[0].message.content or ""
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RerankError("Invalid rerank JSON") from exc

        ranked = payload.get("ranked_indices")
        if not isinstance(ranked, list) or not all(isinstance(i, int) for i in ranked):
            raise RerankError("ranked_indices must be list[int]")
        return ranked
