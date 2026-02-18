Architecture Vector Store
=========================

Scope
-----
This document covers retrieval, late attachment, and embeddings for the current
implementation and the supported modes.

Supported Modes (Architecture)
------------------------------

The system supports three vector_search modes:

1) local (mock)
   - Local indexing and local retrieval (test-only).
   - Uses the local vector search tool (no external DB required).

2) openai (file_search)
   - Uses the OpenAI Response API file_search tool.
   - For deployments fully relying on OpenAI services.

3) chroma
   - Uses ChromaDB as the vector store.
   - Goal: cover the functional surface of OpenAI file_search (late attachment,
     late chunking behavior).
   - Two setups:
     a) in-process (default ONNX all-MiniLM-L6-v2)
     b) remote embeddings service (DGX Spark; OpenAI-compatible /v1/embeddings)

Configuration entry points
--------------------------

- Vector provider selection:
  - config files: configs/config-*.yaml
  - key: vector_search.provider (local | openai | chroma)

- Embeddings (DGX service):
  - models.env: EMBEDDINGS_MODEL_PATH (model for embeddings-gpu)
  - configs/config-docker-dgx.yaml: vector_search.chroma_embedding_model (model name)
  - Note: these two must be kept in sync today (path vs model name). If you change
    the embedding model, update both places to avoid mismatches.

- Chunking & indexing:
  - config files: vector_search.chunk_size, vector_search.chunk_overlap

- Chroma connection:
  - config files: vector_search.chroma_host, chroma_port, chroma_ssl

Retrieval behavior (file_search parity)
---------------------------------------
For chroma/local, file search is routed through the internal vector search tool
to approximate OpenAI file_search behavior:

- Planner query fidelity: the provided planner query is used as-is as the
  primary retrieval query (no default simplification).
- Optional query expansion (KISS):
  - config: agents.file_search_rewrite_mode (none | paraphrase_lite | hyde_lite)
  - config: agents.file_search_rewrite_max_variants
  - HYDE mode is constrained to a single variant for predictable latency.
- Retrieval candidates are merged, deduplicated, and capped per document.
- This rewrite/expansion feature is experimental.
- Latency/cost warning: paraphrase_lite or hyde_lite can trigger one LLM call
  per file_search query.

Observability and tracing
-------------------------
The vector search tool emits diagnostic logs with:

- effective query list (primary + expansion variants)
- rewrite mode applied
- top_k, score_threshold
- hit counts and kept score range
- inferred or provided domain_hint

These logs are written via the standard logger (logs/run_*.log). The tool also
returns an observability payload (effective_queries, rewrite mode, etc.) that is
visible in trace outputs when tracing is enabled (see traces/).

Config quick reference
----------------------
- vector_search.provider: local | openai | chroma
- vector_search.chunk_size, vector_search.chunk_overlap
  - Units are characters (not tokens).
- agents.file_search_rewrite_mode: none | paraphrase_lite | hyde_lite
- agents.file_search_rewrite_max_variants: integer (HyDE forced to 1)
- agents.file_search_top_k (optional override)
- agents.file_search_score_threshold (optional override)


Current Implementation (as-is)
------------------------------

Retrieval path (chroma)
-----------------------
The retrieval path uses chroma-mcp (client) from agentic-research:

agentic-research -> chroma-mcp (client) -> chromadb (server)

The client sends query_texts, so the embedding function is executed on the
client side by chroma-mcp. The embedding function is taken from the collection
configuration that was persisted when the collection was created (by dataprep).
agentic-research does not choose the embedding function; it is passive here.

Late attachment
---------------
Late attachment is supported: if a knowledge entry exists, dataprep uploads only
when needed. The Chroma backend now checks whether the collection contains the
document; if missing, it re-indexes and updates the knowledge DB.

Embeddings today
----------------
There are two embedding paths:
1) Indexing (dataprep): dataprep creates the collection and persists the
   embedding function on it. That embedding function is then used for all
   subsequent inserts and queries.
2) Retrieval (agentic-research via chroma-mcp): chroma-mcp reads the collection
   configuration and executes the embedding function on the client side.

In local mode, we accept the default Chroma embedding (ONNX all-MiniLM-L6-v2).
That is effectively the same model as sentence-transformers/all-MiniLM-L6-v2,
so the behavior is acceptable for local development.


EmbeddingFactory
----------------
We use a shared EmbeddingFactory with two modes:
1) in-process: default Chroma embedding (ONNX all-MiniLM-L6-v2) for local dev
2) remote: embeddings-gpu service for DGX (OpenAI-compatible /v1/embeddings)

Dataprep uses the factory to attach the embedding function to the collection.
chroma-mcp then uses the persisted embedding function when handling query_texts.
agentic-research does not call the factory directly in the chroma-mcp path.

Two-mode diagram
----------------

Local (in-process)
  dataprep         -> EmbeddingFactory(in-process) -> collection embedding function (default ONNX)
  agentic-research -> chroma-mcp -> uses collection embedding function
  chromadb         -> stores vectors, no embedding computation

DGX (remote service)
  dataprep         -> EmbeddingFactory(remote) -> collection embedding function (custom, remote)
  agentic-research -> chroma-mcp -> uses collection embedding function
  chromadb         -> stores vectors, no embedding computation

Note: EmbeddingFactory is invoked by dataprep at collection creation time.
chroma-mcp uses the persisted embedding function from the collection.


Findings
--------
- The embedding function is executed in the chroma-mcp client, not in the
  chromadb server. The ONNX download observed in logs comes from the client
  container (agentic-research one-off run).
- Chroma persists an embedding function at the collection level. If a collection
  is created without an explicit embedding function, Chroma default (ONNX) is
  used for subsequent queries.
- For local runs we should rely on the default Chroma embedding (ONNX
  all-MiniLM-L6-v2) and its cache (persisted in docker-compose.yml).


Open follow-ups (issues)
------------------------
- Issue #54: remove duplication between models.env and config YAML for embedding model.

Reference implementations (Chroma)
----------------------------------
We will take inspiration from these embedding functions in Chroma:
- HuggingFaceEmbeddingFunction (huggingface_embedding_function.py)
- Chroma Cloud Qwen embedding function (chroma_cloud_qwen_embedding_function.py)
- OllamaEmbeddingFunction (ollama_embedding_function.py)
