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
        self._connect()

    def _connect(self):
        """连接 Zilliz Cloud 并确保 Collection 存在"""
        self._client = MilvusClient(uri=self._uri, token=self._token)
        if not self._client.has_collection(self._col):
            self._create_collection()
            print(f"✅ 已创建 Collection：{self._col}")
        else:
            print(f"✅ 已连接 Collection：{self._col}")

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
        else:  # 无 sparse → 纯 dense 搜索
            results = self._client.search(
                collection_name=self._col,
                data=[dense_q],
                anns_field="dense_vector",
                search_params={"metric_type": "COSINE", "nprobe": 10},
                limit=top_k,
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
        return hits

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
