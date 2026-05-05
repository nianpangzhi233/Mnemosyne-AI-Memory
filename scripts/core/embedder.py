#!/usr/bin/env python3
"""Embedder 接口 — 嵌入模型抽象层

基于现有 BGE-M3 加载逻辑，定义统一的嵌入模型接口。
预留 Harrier / Qwen 实现。
"""

import os

from abc import ABC, abstractmethod
from typing import List

import numpy as np


class AbstractEmbedder(ABC):
    """嵌入模型抽象基类"""

    @abstractmethod
    def encode(self, text: str, **kwargs) -> np.ndarray:
        """编码单条文本，返回归一化向量 (dim,)"""

    @abstractmethod
    def encode_batch(self, texts: List[str], **kwargs) -> List[np.ndarray]:
        """编码多条文本，返回向量列表"""

    @abstractmethod
    def get_dimension(self) -> int:
        """返回向量维度"""


def _ensure_offline():
    os.environ.setdefault('HF_HUB_OFFLINE', '1')


class _SentenceTransformerEmbedder(AbstractEmbedder):
    """SentenceTransformer 通用基类，消除 Harrier/BGE-M3 重复代码"""

    MODEL_NAME = ""

    def __init__(self, model_name: str = None, model_kwargs: dict = None):
        self._model = None
        self._model_name = model_name or self.MODEL_NAME
        self._model_kwargs = model_kwargs or {}

    def _load(self):
        if self._model is None:
            _ensure_offline()
            from sentence_transformers import SentenceTransformer
            if self._model_kwargs:
                self._model = SentenceTransformer(
                    self._model_name, model_kwargs=self._model_kwargs)
            else:
                self._model = SentenceTransformer(self._model_name)

    def encode(self, text: str, **kwargs) -> np.ndarray:
        self._load()
        return self._model.encode(text, normalize_embeddings=True)

    def encode_batch(self, texts: List[str], **kwargs) -> List[np.ndarray]:
        self._load()
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        if isinstance(embeddings, np.ndarray):
            return [e for e in embeddings]
        return list(embeddings)


class BgeM3Embedder(_SentenceTransformerEmbedder):
    MODEL_NAME = "BAAI/bge-m3"

    def get_dimension(self) -> int:
        self._load()
        test = self._model.encode("test", normalize_embeddings=True)
        return test.shape[0]


class HarrierEmbedder(_SentenceTransformerEmbedder):
    MODEL_NAME = "microsoft/harrier-oss-v1-0.6b"

    def __init__(self, model_name: str = None):
        super().__init__(model_name, model_kwargs={"dtype": "auto"})

    def get_dimension(self) -> int:
        return 1024


class QwenEmbedder(AbstractEmbedder):
    """Qwen 嵌入模型（备选）

    预留接口，未来可接入 Qwen3-VL-Embeddings 等多模态模型。
    """

    def __init__(self, model_name: str = None):
        self._model_name = model_name

    def encode(self, text: str, **kwargs) -> np.ndarray:
        raise NotImplementedError("QwenEmbedder 为备选，暂不可用")

    def encode_batch(self, texts: List[str], **kwargs) -> List[np.ndarray]:
        raise NotImplementedError("QwenEmbedder 为备选，暂不可用")

    def get_dimension(self) -> int:
        raise NotImplementedError("QwenEmbedder 为备选，暂不可用")
