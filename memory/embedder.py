"""
BGE-M3 Embedding 封装
- 懒加载模型，首次调用时才下载（约 2GB）
- 输出 dense 向量（1024维）+ sparse 向量（词频权重）
"""

from __future__ import annotations
from typing import Tuple
import numpy as np


class Embedder:
    """BGE-M3 懒加载封装，单例模式避免重复加载模型"""

    _instance: "Embedder | None" = None
    _model = None

    def __new__(cls) -> "Embedder":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load(self):
        """首次调用时加载模型"""
        if self._model is None:
            print("⏳ 正在加载 BGE-M3 模型（首次约需下载 2GB）...")
            from FlagEmbedding import BGEM3FlagModel
            self._model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
            print("✅ BGE-M3 模型加载完成")

    def embed(self, text: str) -> Tuple[list, dict]:
        """
        对单条文本生成 dense + sparse 双向量

        返回:
            dense_vec: list[float]，1024 维语义向量
            sparse_vec: dict，稀疏词频权重，用于关键词检索
        """
        self._load()
        output = self._model.encode(
            [text],
            return_dense=True,
            return_sparse=True,
            batch_size=1,
        )
        dense_vec = output["dense_vecs"][0].tolist()
        sparse_vec = dict(output["lexical_weights"][0])
        return dense_vec, sparse_vec

    def embed_batch(self, texts: list[str]) -> Tuple[list, list]:
        """
        批量生成向量，迁移大量记忆时使用

        返回:
            dense_vecs: list of list[float]
            sparse_vecs: list of dict
        """
        self._load()
        output = self._model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            batch_size=16,
        )
        dense_vecs = [v.tolist() for v in output["dense_vecs"]]
        sparse_vecs = [dict(w) for w in output["lexical_weights"]]
        return dense_vecs, sparse_vecs
