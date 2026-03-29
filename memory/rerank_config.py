# memory/rerank_config.py
"""环境变量解析 → 类型化 Rerank 配置对象"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class RerankConfig:
    enabled: bool
    provider: str  # "reranker"（专用 Reranker API）或 "llm"（通用 Chat Completion）
    model: str
    api_base: str
    api_key: str
    fetch_k: int
    timeout_ms: int
    flat_gap_threshold: float
    low_conf_threshold: float
    min_candidates: int
    force: bool
    debug: bool

    @classmethod
    def from_env(cls) -> "RerankConfig":
        return cls(
            enabled=_to_bool(os.getenv("RERANK_ENABLED"), True),
            provider=os.getenv("RERANK_PROVIDER", "reranker"),
            model=os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3"),
            api_base=os.getenv("RERANK_API_BASE", os.getenv("EMBEDDING_API_BASE", "")),
            api_key=os.getenv("RERANK_API_KEY", os.getenv("EMBEDDING_API_KEY", "")),
            fetch_k=int(os.getenv("RERANK_FETCH_K", "40")),
            timeout_ms=int(os.getenv("RERANK_TIMEOUT_MS", "8000")),
            flat_gap_threshold=float(os.getenv("RERANK_FLAT_GAP_THRESHOLD", "0.03")),
            low_conf_threshold=float(os.getenv("RERANK_LOW_CONF_THRESHOLD", "0.45")),
            min_candidates=int(os.getenv("RERANK_MIN_CANDIDATES", "8")),
            force=_to_bool(os.getenv("RERANK_FORCE"), False),
            debug=_to_bool(os.getenv("RERANK_DEBUG"), False),
        )
