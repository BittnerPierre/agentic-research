"""Tests for Chroma embedding factory and collection persistence."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from chromadb.api.types import DefaultEmbeddingFunction
from chromadb.utils import embedding_functions
from chromadb.utils.embedding_functions import config_to_embedding_function

from src.config import get_config
from src.dataprep.chroma_embedding_factory import get_chroma_embedding_function
from src.dataprep.vector_backends import ChromaVectorBackend


def _snapshot_config(config):
    return config.vector_search.model_copy(deep=True)


def _restore_config(config, snapshot):
    config.vector_search = snapshot


class _DummyEmbeddingFunction(embedding_functions.EmbeddingFunction[list[str]]):
    @staticmethod
    def name() -> str:
        return "agentic-dummy"

    def __call__(self, input: list[str]):
        return [[0.1, 0.2, 0.3] for _ in input]

    @staticmethod
    def build_from_config(config):
        return _DummyEmbeddingFunction()

    def get_config(self):
        return {}


@embedding_functions.register_embedding_function
class _RegisteredDummyEmbeddingFunction(_DummyEmbeddingFunction):
    pass


def test_chroma_embedding_factory_default():
    config = get_config()
    snapshot = _snapshot_config(config)

    config.vector_search.chroma_embedding_provider = "default"

    embedding_fn = get_chroma_embedding_function(config)
    assert isinstance(embedding_fn, DefaultEmbeddingFunction)

    _restore_config(config, snapshot)


def test_chroma_embedding_factory_openai_uses_base_url(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)

    config.vector_search.chroma_embedding_provider = "openai"
    config.vector_search.chroma_embedding_api_base = "http://embeddings:8003"
    config.vector_search.chroma_embedding_model = "Qwen3-Embedding-4B-Q8_0.gguf"
    config.vector_search.chroma_embedding_api_key_env = "CHROMA_OPENAI_API_KEY"
    monkeypatch.setenv("CHROMA_OPENAI_API_KEY", "dummy")

    embedding_fn = get_chroma_embedding_function(config)
    assert embedding_fn.name() == "openai"
    assert embedding_fn.api_base == "http://embeddings:8003"
    assert embedding_fn.model_name == "Qwen3-Embedding-4B-Q8_0.gguf"

    _restore_config(config, snapshot)


def test_openai_embedding_function_calls_openai_compatible_endpoint(monkeypatch):
    response_payload = {}

    class _EmbeddingHandler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - http.server API uses camelcase
            if not self.path.endswith("/embeddings"):
                self.send_response(404)
                self.end_headers()
                return

            length = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            request = json.loads(body)

            inputs = request.get("input", [])
            if isinstance(inputs, str):
                inputs = [inputs]

            response_payload["request"] = request
            response_payload["inputs"] = inputs

            data = [
                {"object": "embedding", "index": idx, "embedding": [0.1, 0.2]}
                for idx, _ in enumerate(inputs)
            ]
            response = {"object": "list", "model": request.get("model"), "data": data}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), _EmbeddingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    config = get_config()
    snapshot = _snapshot_config(config)

    config.vector_search.chroma_embedding_provider = "openai"
    config.vector_search.chroma_embedding_api_base = f"http://127.0.0.1:{server.server_port}/v1"
    config.vector_search.chroma_embedding_model = "qwen3-embed-test"
    config.vector_search.chroma_embedding_api_key_env = "CHROMA_OPENAI_API_KEY"
    monkeypatch.setenv("CHROMA_OPENAI_API_KEY", "dummy")

    embedding_fn = get_chroma_embedding_function(config)
    embeddings = embedding_fn(["hello"])

    assert len(embeddings) == 1
    assert response_payload["request"]["model"] == "qwen3-embed-test"
    assert response_payload["inputs"] == ["hello"]

    server.shutdown()
    server.server_close()
    _restore_config(config, snapshot)


def test_chroma_backend_passes_embedding_function_to_collection(monkeypatch):
    config = get_config()
    snapshot = _snapshot_config(config)

    config.vector_search.chroma_embedding_provider = "default"

    captured = {}

    class _FakeClient:
        def get_or_create_collection(self, name, embedding_function=None):
            captured["name"] = name
            captured["embedding_function"] = embedding_function
            return "collection"

    backend = ChromaVectorBackend()
    monkeypatch.setattr(backend, "_client", lambda _config: _FakeClient())

    collection = backend._collection(config, "test-collection")
    assert collection == "collection"
    assert captured["name"] == "test-collection"
    assert isinstance(captured["embedding_function"], DefaultEmbeddingFunction)

    _restore_config(config, snapshot)


def test_embedding_function_roundtrip_from_config():
    embedding_fn = _RegisteredDummyEmbeddingFunction()
    config = {"name": embedding_fn.name(), "config": embedding_fn.get_config()}
    rebuilt = config_to_embedding_function(config)
    assert rebuilt.name() == "agentic-dummy"
