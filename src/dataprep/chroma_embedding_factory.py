"""Chroma embedding function factory for collection creation and queries."""

from __future__ import annotations

import os

from chromadb.api.types import DefaultEmbeddingFunction
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction


def get_chroma_embedding_function(config):
    provider = config.vector_search.chroma_embedding_provider

    if provider == "default":
        return DefaultEmbeddingFunction()

    if provider == "openai":
        api_base = config.vector_search.chroma_embedding_api_base
        model_name = config.vector_search.chroma_embedding_model
        api_key_env = config.vector_search.chroma_embedding_api_key_env

        if not api_base or not model_name:
            raise ValueError(
                "chroma_embedding_api_base and chroma_embedding_model are required for "
                "chroma_embedding_provider=openai"
            )

        if not os.getenv(api_key_env):
            os.environ[api_key_env] = "dummy"

        return OpenAIEmbeddingFunction(
            api_key_env_var=api_key_env,
            model_name=model_name,
            api_base=api_base,
        )

    raise ValueError(f"Unknown chroma_embedding_provider: {provider}")
