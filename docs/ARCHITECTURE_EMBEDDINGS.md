Embeddings Architecture (Local + Service)
=========================================

This note documents how embeddings are computed in two modes:

1) In-process (local CPU) embedding
2) Remote embedding service (GPU)

The goal is to keep the **same embedding function** for both indexing (dataprep)
and retrieval (MCP / chroma-mcp). This is achieved by persisting the embedding
function on the Chroma collection at creation time.

---

## A) In‑process embeddings (local)

```
┌────────────────────────────┐
│ agentic-research (CLI)     │
│  └─ chroma-mcp (client)    │
└─────────────┬──────────────┘
              │ query_texts
              ▼
   (Collection embedding function)
   default Chroma embedding (ONNX)
              │ query_embeddings
              ▼
         chromadb (server)

┌────────────────────────────┐
│ dataprep (MCP server)      │
└─────────────┬──────────────┘
              │ docs
              ▼
   (EmbeddingFactory: in-process)
   default Chroma embedding (ONNX)
              │ embeddings
              ▼
         chromadb (server)
```

**Key points**
- Embeddings are computed **inside the app containers** (agentic-research, dataprep).
- Chroma only stores vectors and serves similarity search.
- The embedding function is persisted on the collection by dataprep and reused by chroma-mcp.

---

## B) Remote embeddings (GPU service)

```
┌────────────────────────────┐
│ agentic-research (CLI)     │
│  └─ chroma-mcp (client)    │
└─────────────┬──────────────┘
              │ query_texts
              ▼
   (Collection embedding function)
   embeddings-gpu service (OpenAI-compatible /v1/embeddings)
              │ query_embeddings
              ▼
         chromadb (server)

┌────────────────────────────┐
│ dataprep (MCP server)      │
└─────────────┬──────────────┘
              │ docs
              ▼
   (EmbeddingFactory: remote)
   embeddings-gpu service (OpenAI-compatible /v1/embeddings)
              │ embeddings
              ▼
         chromadb (server)
```

**Key points**
- Dataprep attaches a remote embedding function (OpenAIEmbeddingFunction) to the collection.
- chroma-mcp uses the persisted embedding function when querying with query_texts.
- Chroma never computes embeddings on its own; it only stores and queries vectors.

---

## EmbeddingFactory (current)

```
EmbeddingFactory
  ├─ in-process: sentence-transformers / local
  └─ remote: /v1/embeddings (embeddings-gpu)
```

The factory is used in dataprep (indexing). chroma-mcp does not call the factory
directly; it uses the embedding function persisted on the collection. This
guarantees consistent vectors across index + retrieval.
