"""Embedding and rerank providers used by the document engine.

The engine's search code accepts model objects with ``encode`` /
``encode_queries`` (embeddings) and ``similarity`` (rerank) methods;
:class:`EmbeddingModel` and :class:`RerankModel` implement them on top of the
configured HTTP services. Both are configured once through :func:`configure`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import requests
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)


class EmbeddingUnavailable(RuntimeError):
    pass


@dataclass
class ProviderConfig:
    embedding_base_url: str = ""
    embedding_api_key: str | None = None
    embedding_model: str = "text-embedding-v3"
    embedding_dimensions: int = 1024
    batch_size: int = 10
    rerank_url: str = ""
    rerank_api_key: str | None = None
    rerank_model: str = "gte-rerank-v2"
    timeout: float = 60.0


_config = ProviderConfig()
_client: OpenAI | None = None


def configure(config: ProviderConfig) -> None:
    global _config, _client
    _config = config
    _client = None


def _embedding_client() -> OpenAI:
    global _client
    if not _config.embedding_api_key:
        raise EmbeddingUnavailable("Set TP_EMBEDDING_API_KEY to enable document search.")
    if _client is None:
        _client = OpenAI(
            api_key=_config.embedding_api_key, base_url=_config.embedding_base_url, timeout=_config.timeout
        )
    return _client


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed ``texts`` in provider-sized batches; any failure raises."""
    client = _embedding_client()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _config.batch_size):
        batch = [text if text.strip() else " " for text in texts[start : start + _config.batch_size]]
        try:
            response = client.embeddings.create(
                model=_config.embedding_model,
                input=batch,
                dimensions=_config.embedding_dimensions,
                encoding_format="float",
            )
        except OpenAIError as exc:
            raise EmbeddingUnavailable(f"The embedding service failed: {exc}") from exc
        vectors.extend(item.embedding for item in sorted(response.data, key=lambda item: item.index))
    return vectors


def rerank_similarity(query: str, texts: list[str]) -> tuple[np.ndarray, None]:
    """Relevance scores in input order; zeros (no-op) when rerank is not configured."""
    if not texts:
        return np.array([]), None
    if not _config.rerank_api_key:
        return np.zeros(len(texts)), None
    try:
        response = requests.post(
            _config.rerank_url,
            headers={"Authorization": f"Bearer {_config.rerank_api_key}"},
            json={
                "model": _config.rerank_model,
                "input": {"query": query, "documents": texts},
                "parameters": {"return_documents": False, "top_n": len(texts)},
            },
            timeout=_config.timeout,
        )
        response.raise_for_status()
        scores = np.zeros(len(texts))
        for result in response.json().get("output", {}).get("results", []):
            scores[int(result["index"])] = float(result["relevance_score"])
        return scores, None
    except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
        logger.warning("Rerank unavailable, falling back to keyword and vector scores: %s", exc)
        return np.zeros(len(texts)), None


def rerank_available() -> bool:
    return bool(_config.rerank_api_key)


class EmbeddingModel:
    """Adapter for the engine's embedding interface (vectors, token count)."""

    def encode(self, texts: list[str]) -> tuple[np.ndarray, int]:
        return np.array(embed_batch(list(texts))), 0

    def encode_queries(self, text: str) -> tuple[np.ndarray, int]:
        return np.array(embed_batch([text])[0]), 0


class RerankModel:
    """Adapter for the engine's rerank interface (scores, token count)."""

    def similarity(self, query: str, texts: list[str]) -> tuple[np.ndarray, int]:
        scores, _ = rerank_similarity(query, texts)
        return scores, 0
