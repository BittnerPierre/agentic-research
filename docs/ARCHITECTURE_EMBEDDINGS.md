# Embeddings Architecture (Local + Service)

This note documents how embeddings are computed in two modes:

1) In‑process (local CPU) embedding
2) Remote embedding service (GPU)

The goal is to keep the **same embedding function** for both indexing (dataprep)
and retrieval (MCP / chroma‑mcp).

---

## A) In‑process embeddings (local)

```
┌────────────────────────────┐
│ agentic-research (CLI)     │
│  └─ chroma-mcp (client)    │
└─────────────┬──────────────┘
              │ query_texts
              ▼
   (EmbeddingFactory: in-process)
   sentence-transformers / local model
              │ query_embeddings
              ▼
         chromadb (server)

┌────────────────────────────┐
│ dataprep (MCP server)      │
└─────────────┬──────────────┘
              │ docs
              ▼
   (EmbeddingFactory: in-process)
   sentence-transformers / local model
              │ embeddings
              ▼
         chromadb (server)
```

**Key points**
- Embeddings are computed **inside the app containers** (agentic-research, dataprep).
- Chroma only stores vectors and serves similarity search.
- The same embedding function must be used for both index and query.

---

## B) Remote embeddings (GPU service)

```
┌────────────────────────────┐
│ agentic-research (CLI)     │
│  └─ chroma-mcp (client)    │
└─────────────┬──────────────┘
              │ query_texts
              ▼
   (EmbeddingFactory: remote)
   embeddings-gpu service
              │ query_embeddings
              ▼
         chromadb (server)

┌────────────────────────────┐
│ dataprep (MCP server)      │
└─────────────┬──────────────┘
              │ docs
              ▼
   (EmbeddingFactory: remote)
   embeddings-gpu service
              │ embeddings
              ▼
         chromadb (server)
```

**Key points**
- Both dataprep and chroma‑mcp call the **same remote embeddings service**.
- Chroma never computes embeddings on its own; it only stores and queries vectors.

---

## EmbeddingFactory (proposed)

```
EmbeddingFactory
  ├─ in-process: sentence-transformers / local
  └─ remote: /v1/embeddings (embeddings-gpu)
```

The factory must be used in:
- dataprep (indexing)
- chroma-mcp client (query)

This guarantees consistent vectors across index + retrieval.
