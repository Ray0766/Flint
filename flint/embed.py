"""embedding 服务：bge-m3 封装 + 内容 hash 缓存（M1-020，技术方案 E1/E5）。

- 批量：每次后端调用 <=512 条（验收硬条款）。
- 缓存：sha256(内容) 为键，命中不再计算（计数器可断言）；同一调用内
  重复文本也只编码一次。
- 真实后端 SentenceTransformerBackend 惰性加载 bge-m3（模型 ~2.3GB，
  仅 worker 运行时载入；CI 永不联网，测试一律注入假后端）。
"""
from __future__ import annotations

import hashlib
from typing import Any, Final, Protocol

from flint.domain.models import Vector

BATCH_SIZE: Final[int] = 512

DEFAULT_MODEL: Final[str] = "BAAI/bge-m3"


class EncoderBackend(Protocol):
    def encode(self, texts: list[str]) -> list[Vector]: ...


class SentenceTransformerBackend:
    """bge-m3 真实后端；导入与模型加载推迟到首次编码。"""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model: Any = None

    def encode(self, texts: list[str]) -> list[Vector]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        raw = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, row)) for row in raw]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DeterministicHashBackend:
    """离线确定性后端（dev-replay / 测试 / CI）：sha256 种子伪随机单位向量。
    无语义、零依赖、跨进程稳定——断点续跑的产物 diff 依赖这一确定性；
    生产 worker 用 SentenceTransformerBackend。"""

    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim

    def encode(self, texts: list[str]) -> list[Vector]:
        import random

        result: list[Vector] = []
        for text in texts:
            rng = random.Random(hashlib.sha256(text.encode("utf-8")).digest())
            raw = [rng.gauss(0.0, 1.0) for _ in range(self._dim)]
            norm = sum(v * v for v in raw) ** 0.5 or 1.0
            result.append([v / norm for v in raw])
        return result


class EmbeddingService:
    def __init__(
        self,
        backend: EncoderBackend,
        cache: dict[str, Vector] | None = None,
        batch_size: int = BATCH_SIZE,
    ) -> None:
        self._backend = backend
        self._cache: dict[str, Vector] = cache if cache is not None else {}
        self._batch_size = batch_size
        self.cache_hits = 0
        self.cache_misses = 0

    def embed(self, texts: list[str]) -> list[Vector]:
        keys = [content_hash(t) for t in texts]
        pending: dict[str, str] = {}  # hash -> text, insertion-ordered, deduped
        for text, key in zip(texts, keys):
            if key in self._cache:
                self.cache_hits += 1
            elif key not in pending:
                self.cache_misses += 1
                pending[key] = text
        pending_items = list(pending.items())
        for start in range(0, len(pending_items), self._batch_size):
            chunk = pending_items[start : start + self._batch_size]
            vectors = self._backend.encode([text for _, text in chunk])
            for (key, _), vector in zip(chunk, vectors):
                self._cache[key] = vector
        return [self._cache[key] for key in keys]
