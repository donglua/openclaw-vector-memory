# memory/reranker.py
"""LLM 重排适配器：调用 OpenAI 兼容 API 对候选项重新排序"""
from __future__ import annotations

import json
from dataclasses import dataclass

from openai import OpenAI


class RerankError(Exception):
    """重排失败异常"""
    pass


@dataclass
class LLMReranker:
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
