"""
Zilliz Cloud 向量记忆存储核心
- 自动初始化 Collection（含 dense+sparse 双索引）
- save()：写入一条记忆
- search()：混合搜索（Dense 语义 + Sparse 关键词，RRF 融合）
- build_prompt_context()：直接返回拼好的 Prompt 片段给 Agent 用
"""

from __future__ import annotations
import time
import os
from dotenv import load_dotenv
from pymilvus import (
    MilvusClient,
    DataType,
    AnnSearchRequest,
    RRFRanker,
)
from .embedder import Embedder, get_dense_dim
from .rerank_config import RerankConfig
from .rerank_policy import should_rerank, merge_reranked_candidates
from .reranker import LLMReranker, APIReranker

load_dotenv()


class MemoryStore:
    """OpenClaw 向量记忆存储，基于 Zilliz Cloud + BGE-M3"""

    def __init__(
        self,
        uri: str | None = None,
        token: str | None = None,
        collection_name: str | None = None,
    ):
        self._uri = uri or os.environ["ZILLIZ_URI"]
        self._token = token or os.environ["ZILLIZ_TOKEN"]
        self._col = collection_name or os.getenv("COLLECTION_NAME", "openclaw_memories")
        self._embedder = Embedder()
        self._client: MilvusClient | None = None
        self._rerank_config = RerankConfig.from_env()
        self._reranker = None
        if self._rerank_config.enabled:
            if self._rerank_config.provider == "reranker":
                self._reranker = APIReranker(
                    api_base=self._rerank_config.api_base,
                    api_key=self._rerank_config.api_key,
                    model=self._rerank_config.model,
                    timeout_ms=self._rerank_config.timeout_ms,
                )
            elif self._rerank_config.provider == "llm":
                self._reranker = LLMReranker(
                    client=None,
                    model=self._rerank_config.model,
                    timeout_ms=self._rerank_config.timeout_ms,
                )
        self._connect()

    def _connect(self):
        """连接 Zilliz Cloud 并确保 Collection 存在"""
        self._client = MilvusClient(uri=self._uri, token=self._token)
        if not self._client.has_collection(self._col):
            self._create_collection()
            print(f"✅ 已创建 Collection：{self._col}")
        else:
            print(f"✅ 已连接 Collection：{self._col}")

    def _debug(self, message: str) -> None:
        """rerank 调试日志"""
        if self._rerank_config.debug:
            print(f"[rerank-debug] {message}")

    def _create_collection(self):
        """创建双向量 Collection（dense + sparse）"""
        schema = self._client.create_schema(auto_id=True, enable_dynamic_field=True)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=get_dense_dim())
        schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field("text", DataType.VARCHAR, max_length=4096)
        schema.add_field("source", DataType.VARCHAR, max_length=256)
        schema.add_field("created_at", DataType.INT64)

        # 构建索引
        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="dense_vector",
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )
        index_params.add_index(
            field_name="sparse_vector",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="IP",
        )

        self._client.create_collection(
            collection_name=self._col,
            schema=schema,
            index_params=index_params,
        )

    def save(self, text: str, source: str = "agent", tags: list[str] | None = None) -> None:
        """
        写入一条记忆

        Args:
            text:   记忆内容
            source: 来源标记，如 "agent"、"daily_log"、"migrate"
            tags:   可选标签列表（存为 dynamic field）
        """
        dense_vec, sparse_vec = self._embedder.embed(text)
        row = {
            "dense_vector": dense_vec,
            "sparse_vector": sparse_vec,
            "text": text,
            "source": source,
            "created_at": int(time.time()),
        }
        if tags:
            row["tags"] = tags
        self._client.insert(collection_name=self._col, data=[row])

    def save_batch(self, texts: list[str], source: str = "migrate") -> None:
        """批量写入，迁移时使用"""
        if not texts:
            return
        dense_vecs, sparse_vecs = self._embedder.embed_batch(texts)
        now = int(time.time())
        rows = [
            {
                "dense_vector": dense_vecs[i],
                "sparse_vector": sparse_vecs[i],
                "text": texts[i],
                "source": source,
                "created_at": now,
            }
            for i in range(len(texts))
        ]
        self._client.insert(collection_name=self._col, data=rows)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        搜索记忆：
        - 本地 BGE-M3：Dense + Sparse 混合搜索（RRF 融合）
        - 远程 API：仅 Dense 语义搜索（API 不返回 sparse 向量）
        """
        dense_q, sparse_q = self._embedder.embed(query)

        if sparse_q:  # 有 sparse 向量 → 混合搜索
            dense_req = AnnSearchRequest(
                data=[dense_q],
                anns_field="dense_vector",
                param={"metric_type": "COSINE", "nprobe": 10},
                limit=top_k,
            )
            sparse_req = AnnSearchRequest(
                data=[sparse_q],
                anns_field="sparse_vector",
                param={"metric_type": "IP"},
                limit=top_k,
            )
            results = self._client.hybrid_search(
                collection_name=self._col,
                reqs=[dense_req, sparse_req],
                ranker=RRFRanker(),
                limit=top_k,
                output_fields=["text", "source", "created_at"],
            )
            hits_raw = results[0]
        else:  # 无 sparse → 纯 dense 搜索（remote 模式走这里）
            results = self._client.search(
                collection_name=self._col,
                data=[dense_q],
                anns_field="dense_vector",
                search_params={"metric_type": "COSINE", "nprobe": 10},
                limit=max(top_k, self._rerank_config.fetch_k),
                output_fields=["text", "source", "created_at"],
            )
            hits_raw = results[0]

        hits = []
        for r in hits_raw:
            hits.append({
                "text": r["entity"]["text"],
                "source": r["entity"].get("source", ""),
                "score": round(r["distance"], 4),
            })

        # 混合搜索路径不做 rerank，直接返回
        if sparse_q:
            return hits[:top_k]

        # ── Remote 路径：条件触发 LLM Rerank ──
        if not self._rerank_config.enabled or not self._reranker:
            return hits[:top_k]

        scores = [h["score"] for h in hits]
        do_rerank, reason = should_rerank(
            scores=scores,
            top_k=top_k,
            min_candidates=self._rerank_config.min_candidates,
            flat_gap_threshold=self._rerank_config.flat_gap_threshold,
            low_conf_threshold=self._rerank_config.low_conf_threshold,
            force=self._rerank_config.force,
        )
        self._debug(f"should={do_rerank}, reason={reason}, candidates={len(hits)}")
        if not do_rerank:
            return hits[:top_k]

        try:
            reranked_indices = self._reranker.rerank(query=query, candidates=hits)
            return merge_reranked_candidates(
                candidates=hits,
                reranked_indices=reranked_indices,
                top_k=top_k,
            )
        except Exception as exc:
            self._debug(f"rerank fallback due to: {exc}")
            return hits[:top_k]

    def build_prompt_context(self, query: str, top_k: int = 5) -> str:
        """
        直接返回可注入 Prompt 的记忆片段

        用法：
            context = store.build_prompt_context(user_input)
            prompt = f"{context}\\n\\n用户：{user_input}"
        """
        hits = self.search(query, top_k=top_k)
        if not hits:
            return ""
        lines = "\n".join(f"- {h['text']}" for h in hits)
        return f"## 相关记忆\n{lines}"

    def count(self) -> int:
        """返回当前 Collection 中的记忆总条数"""
        stats = self._client.get_collection_stats(self._col)
        return int(stats.get("row_count", 0))
