"""Embedding helpers for vector backends."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache


def _parse_embedding_spec(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise ValueError(
            "embedding_function must be in the form '<provider>:<model>', " f"got {spec!r}"
        )
    provider, model = spec.split(":", 1)
    return provider.strip(), model.strip()


@lru_cache(maxsize=4)
def _sentence_transformer_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError("sentence-transformers is required for this embedding_function") from exc
    return SentenceTransformer(model_name)


def get_embedding_function(config) -> Callable[[list[str]], list[list[float]]]:
    spec = config.vector_search.embedding_function
    provider, model = _parse_embedding_spec(spec)

    if provider == "sentence-transformers":
        model_instance = _sentence_transformer_model(model)

        def _embed(texts: list[str]) -> list[list[float]]:
            embeddings = model_instance.encode(texts, show_progress_bar=False)
            return [embedding.tolist() for embedding in embeddings]

        return _embed

    raise ValueError(f"Unknown embedding provider: {provider}")
