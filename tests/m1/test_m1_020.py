"""M1-020 acceptance tests: embedding service (bge-m3 wrapper + cache).

Acceptance (tasks.json M1-020):
  - batching at 512 per backend call
  - content-hash cache hits skip recomputation (counter assertions)
"""
from __future__ import annotations

from flint.embed import BATCH_SIZE, EmbeddingService


class CountingBackend:
    """Deterministic fake encoder: records every batch it receives."""

    def __init__(self, dim: int = 4) -> None:
        self.dim = dim
        self.batches: list[list[str]] = []
        self.texts_encoded = 0

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        self.texts_encoded += len(texts)
        return [[float(len(t)), 1.0, 2.0, 3.0] for t in texts]


def make_service() -> tuple[EmbeddingService, CountingBackend]:
    backend = CountingBackend()
    return EmbeddingService(backend=backend), backend


def test_batch_size_is_512() -> None:
    assert BATCH_SIZE == 512


def test_batches_capped_at_512() -> None:
    service, backend = make_service()
    texts = [f"kw-{i}" for i in range(1100)]
    vectors = service.embed(texts)
    assert len(vectors) == 1100
    assert [len(b) for b in backend.batches] == [512, 512, 76]


def test_cache_hit_skips_recompute() -> None:
    service, backend = make_service()
    service.embed(["alpha", "beta"])
    assert backend.texts_encoded == 2

    vectors = service.embed(["alpha", "beta", "gamma"])
    assert backend.texts_encoded == 3, "cached texts must not be re-encoded"
    assert len(vectors) == 3
    assert service.cache_hits == 2
    assert service.cache_misses == 3


def test_duplicate_texts_in_one_call_encoded_once() -> None:
    service, backend = make_service()
    vectors = service.embed(["same", "same", "same"])
    assert backend.texts_encoded == 1
    assert vectors[0] == vectors[1] == vectors[2]


def test_cache_keyed_by_content_returns_stable_vectors() -> None:
    service, _ = make_service()
    first = service.embed(["位置无关"])[0]
    second = service.embed(["padding", "位置无关"])[1]
    assert first == second


def test_empty_input() -> None:
    service, backend = make_service()
    assert service.embed([]) == []
    assert backend.batches == []
