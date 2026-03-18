"""
Embedding 多后端支持
支持：
  - local        本地 BGE-M3（FlagEmbedding），完整 dense+sparse
  - siliconflow  硅基流动 API，OpenAI 兼容，dense only
  - openai       OpenAI 或任意 OpenAI 兼容 API，dense only
  - custom_http  自部署 HTTP 服务，dense only（需自行实现服务端）

通过 .env 中的 EMBEDDING_PROVIDER 切换
"""

from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# 各 provider 输出的 dense 向量维度（需与 Zilliz Collection 一致）
PROVIDER_DIMS = {
    "local": 1024,        # BGE-M3 dense
    "siliconflow": 1024,  # BAAI/bge-m3
    "openai": 1536,       # text-embedding-3-small（或按模型改）
    "custom_http": 1024,  # 按实际服务调整
}


def get_dense_dim() -> int:
    """根据当前 provider 返回 dense 向量维度"""
    provider = os.getenv("EMBEDDING_PROVIDER", "local")
    return PROVIDER_DIMS.get(provider, 1024)


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
        dense = out["dense_vecs"][0].tolist()
        sparse = dict(out["lexical_weights"][0])
        return dense, sparse

    def embed_batch(self, texts: list[str]):
        self._load()
        out = self._model.encode(texts, return_dense=True, return_sparse=True, batch_size=16)
        dense_vecs = [v.tolist() for v in out["dense_vecs"]]
        sparse_vecs = [dict(w) for w in out["lexical_weights"]]
        return dense_vecs, sparse_vecs


# ─── 远程 API 基类（sparse 为空，支持 dense only）────────────────

class _RemoteEmbedder:
    """远程 API 基类，不支持 sparse 向量"""

    def _call(self, text: str) -> list[float]:
        raise NotImplementedError

    def _call_batch(self, texts: list[str]) -> list[list[float]]:
        """默认逐条调用，子类可覆盖为批量接口"""
        return [self._call(t) for t in texts]

    def embed(self, text: str):
        dense = self._call(text)
        return dense, {}  # sparse 为空

    def embed_batch(self, texts: list[str]):
        dense_vecs = self._call_batch(texts)
        return dense_vecs, [{} for _ in texts]


# ─── 硅基流动（SiliconFlow）─────────────────────────────────────

class _SiliconFlowEmbedder(_RemoteEmbedder):
    """
    硅基流动 OpenAI 兼容 API
    模型：BAAI/bge-m3（dense 1024 维）
    文档：https://docs.siliconflow.cn/api-reference/embeddings/create-embeddings
    """
    def __init__(self):
        from openai import OpenAI
        self._client = OpenAI(
            api_key=os.environ["SILICONFLOW_API_KEY"],
            base_url="https://api.siliconflow.cn/v1",
        )
        self._model = os.getenv("SILICONFLOW_MODEL", "BAAI/bge-m3")

    def _call(self, text: str) -> list[float]:
        resp = self._client.embeddings.create(model=self._model, input=text)
        return resp.data[0].embedding

    def _call_batch(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        # 按 index 排序确保顺序
        return [d.embedding for d in sorted(resp.data, key=lambda x: x.index)]


# ─── OpenAI 或任意 OpenAI 兼容 API ──────────────────────────────

class _OpenAIEmbedder(_RemoteEmbedder):
    """
    OpenAI API 或兼容接口（Ollama / Azure / 第三方）
    通过 OPENAI_BASE_URL 切换不同服务
    """
    def __init__(self):
        from openai import OpenAI
        self._client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        self._model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    def _call(self, text: str) -> list[float]:
        resp = self._client.embeddings.create(model=self._model, input=text)
        return resp.data[0].embedding

    def _call_batch(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in sorted(resp.data, key=lambda x: x.index)]


# ─── 自定义 HTTP 服务 ────────────────────────────────────────────

class _CustomHttpEmbedder(_RemoteEmbedder):
    """
    自部署 HTTP 服务
    期望接口：POST /embed?text=xxx → {"dense": [...]}
    """
    def __init__(self):
        import requests
        self._requests = requests
        self._url = os.environ["EMBEDDING_API_URL"]

    def _call(self, text: str) -> list[float]:
        resp = self._requests.post(self._url, params={"text": text}, timeout=10)
        resp.raise_for_status()
        return resp.json()["dense"]


# ─── 工厂函数 ────────────────────────────────────────────────────

_EMBEDDER_INSTANCE = None


def Embedder():
    """
    根据 EMBEDDING_PROVIDER 环境变量返回对应 Embedder 实例（单例）

    可选值：
        local          本地 BGE-M3（默认，完整 dense+sparse）
        siliconflow    硅基流动 API（需 SILICONFLOW_API_KEY）
        openai         OpenAI 兼容 API（需 OPENAI_API_KEY）
        custom_http    自定义 HTTP 服务（需 EMBEDDING_API_URL）
    """
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is not None:
        return _EMBEDDER_INSTANCE

    provider = os.getenv("EMBEDDING_PROVIDER", "local")
    if provider == "local":
        _EMBEDDER_INSTANCE = _LocalEmbedder()
    elif provider == "siliconflow":
        _EMBEDDER_INSTANCE = _SiliconFlowEmbedder()
    elif provider == "openai":
        _EMBEDDER_INSTANCE = _OpenAIEmbedder()
    elif provider == "custom_http":
        _EMBEDDER_INSTANCE = _CustomHttpEmbedder()
    else:
        raise ValueError(f"未知的 EMBEDDING_PROVIDER: {provider}，可选: local / siliconflow / openai / custom_http")

    return _EMBEDDER_INSTANCE
