"""
Embedding 后端支持
  - local   本地 BGE-M3，完整 dense+sparse 混合搜索（默认）
  - remote  任意 OpenAI 兼容 API（硅基流动/OpenAI/自部署等），dense only

通过 .env 中的 EMBEDDING_PROVIDER 切换（local 或 remote）
"""

from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()


def get_dense_dim() -> int:
    """返回当前 provider 的 dense 向量维度"""
    provider = os.getenv("EMBEDDING_PROVIDER", "local")
    if provider == "local":
        return 1024  # BGE-M3 dense 维度
    # 远程 API 由模型决定，默认 1024（BGE-M3），可通过 EMBEDDING_DIM 覆盖
    return int(os.getenv("EMBEDDING_DIM", "1024"))


# ─── 本地 BGE-M3（完整 dense + sparse）───────────────────────────

class _LocalEmbedder:
    """本地 FlagEmbedding，单例懒加载"""
    _model = None

    def _load(self):
        if self._model is None:
            print("⏳ 加载 BGE-M3 模型（首次约需下载 2GB）...")
            from FlagEmbedding import BGEM3FlagModel
            self._model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
            print("✅ BGE-M3 加载完成")

    def embed(self, text: str):
        self._load()
        out = self._model.encode([text], return_dense=True, return_sparse=True, batch_size=1)
        return out["dense_vecs"][0].tolist(), dict(out["lexical_weights"][0])

    def embed_batch(self, texts: list[str]):
        self._load()
        out = self._model.encode(texts, return_dense=True, return_sparse=True, batch_size=16)
        return [v.tolist() for v in out["dense_vecs"]], [dict(w) for w in out["lexical_weights"]]


# ─── 远程 OpenAI 兼容 API（仅 dense）────────────────────────────

class _RemoteEmbedder:
    """
    任意 OpenAI 兼容 Embedding API
    只需在 .env 中配置：
        EMBEDDING_API_BASE  = https://api.siliconflow.cn/v1   # 或其他服务地址
        EMBEDDING_API_KEY   = sk-xxx
        EMBEDDING_MODEL     = BAAI/bge-m3                      # 按服务支持的模型填写
        EMBEDDING_DIM       = 1024                             # 模型输出维度
    """
    _client = None

    def _load(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=os.environ["EMBEDDING_API_KEY"],
                base_url=os.environ["EMBEDDING_API_BASE"],
            )
            self._model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

    def embed(self, text: str):
        self._load()
        resp = self._client.embeddings.create(model=self._model, input=text)
        return resp.data[0].embedding, {}  # 无 sparse

    def embed_batch(self, texts: list[str]):
        self._load()
        resp = self._client.embeddings.create(model=self._model, input=texts)
        dense_vecs = [d.embedding for d in sorted(resp.data, key=lambda x: x.index)]
        return dense_vecs, [{} for _ in texts]


# ─── 工厂函数 ────────────────────────────────────────────────────

_instance = None


def Embedder():
    """
    根据 EMBEDDING_PROVIDER 返回 Embedder 实例（单例）
      local   本地 BGE-M3（默认）
      remote  OpenAI 兼容远程 API
    """
    global _instance
    if _instance is None:
        provider = os.getenv("EMBEDDING_PROVIDER", "local")
        if provider == "local":
            _instance = _LocalEmbedder()
        elif provider == "remote":
            _instance = _RemoteEmbedder()
        else:
            raise ValueError(f"EMBEDDING_PROVIDER 仅支持 local / remote，当前值：{provider}")
    return _instance
