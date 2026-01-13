# ChromaDB Migration Plan - Remove OpenAI file_search Dependency

## Goal

Remove dependency on OpenAI Response API file_search to enable operation without OpenAI platform. Prepare for deployment on DGX Spark with multi-agent services running in Docker containers.

## Motivation

- **Platform Independence**: Operate without OpenAI platform dependency
- **Cost Control**: Use self-hosted models and vector storage
- **DGX Spark Deployment**: Run on-premises with vLLM serving models
- **Flexibility**: Support multiple embedding and reasoning models

## Current File Search Dependencies

1. **`file_search_agent.py`**: Creates agent with `file_search` tool attached via vector_store_id
2. **`vector_store_manager.py`**: Manages OpenAI vector stores
3. **`mcp_functions.py`**: `upload_files_to_vectorstore()` uploads to OpenAI
4. **`web_loader_improved.py`**: Prepares content but uploads to OpenAI Files API
5. **`should_apply_tool_filter()`**: Workaround for model compatibility with OpenAI's file_search

## Target Architecture

### Docker Services (Future)
```
services:
  embedding-service:    # vLLM + embedding model
  reasoning-service:    # vLLM + reasoning model
  instruct-service:     # vLLM + instruct model
  litellm-proxy:        # LiteLLM gateway to vLLM services
  chromadb:             # Vector database
  mcp-dataprep:         # Custom MCP server
  backend:              # Agent orchestration (main application)
```

### Technology Stack
- **Vector DB**: ChromaDB (not Milvus or others)
- **Model Serving**: vLLM + LiteLLM
- **Embeddings**: Local model via vLLM (sentence-transformers for development)
- **Container Orchestration**: Docker Compose
- **Reference**: Inspired by https://github.com/NVIDIA/dgx-spark-playbooks/tree/main/nvidia/multi-agent-chatbot

## Implementation Phases

### Phase 1: Replace Vector Store Backend (Local ChromaDB)

**New modules to create:**

```
src/vectordb/
├── __init__.py
├── base.py              # Abstract base class for vector store operations
├── chromadb_store.py    # ChromaDB implementation
├── openai_store.py      # Existing OpenAI implementation (for backward compat)
└── schemas.py           # Common schemas for vector operations
```

**Abstract interface** (`base.py`):
```python
from abc import ABC, abstractmethod
from typing import List
from pydantic import BaseModel

class Document(BaseModel):
    id: str
    content: str
    metadata: dict

class SearchResult(BaseModel):
    document_id: str
    content: str
    score: float
    metadata: dict

class VectorStoreBase(ABC):
    @abstractmethod
    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to vector store, return document IDs"""
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Semantic search, return top_k results"""
        pass

    @abstractmethod
    def delete_collection(self, collection_name: str) -> None:
        """Delete entire collection"""
        pass

    @abstractmethod
    def get_collection_stats(self) -> dict:
        """Get collection statistics"""
        pass
```

**ChromaDB implementation** (`chromadb_store.py`):
- Use ChromaDB's persistent storage
- Handle embedding generation
- Implement similarity search
- Support metadata filtering

**Configuration updates** (`config.yaml`):
```yaml
vector_store:
  backend: "chromadb"  # or "openai" for backward compatibility
  name: "agent-engineer-basic-course"

  chromadb:
    persist_directory: "data/chromadb"
    collection_name: "${vector_store.name}"
    distance_metric: "cosine"  # or "l2", "ip"

  openai:
    vector_store_id: ""  # legacy, for backward compatibility

embedding:
  provider: "local"  # or "litellm" for vLLM endpoint
  model: "sentence-transformers/all-MiniLM-L6-v2"

  # Future: vLLM via LiteLLM
  litellm:
    base_url: "http://embedding-service:8000"
    model: "BAAI/bge-large-en-v1.5"
```

**Dependencies to add** (`pyproject.toml`):
```toml
chromadb = "^0.5.0"
sentence-transformers = "^2.2.0"
```

### Phase 2: Replace file_search Tool

**Create custom search tool** (`src/agents/tools/semantic_search.py`):

```python
from typing import List
from src.vectordb import get_vector_store
from src.agents.schemas import SearchResult

def semantic_search_tool(
    query: str,
    top_k: int = 5,
    collection_name: str | None = None
) -> List[SearchResult]:
    """
    Custom semantic search replacing OpenAI file_search.

    Args:
        query: Search query
        top_k: Number of results to return
        collection_name: Optional collection name override

    Returns:
        List of search results with content and metadata
    """
    vector_store = get_vector_store(collection_name)
    results = vector_store.search(query, top_k)
    return results

def get_vector_store(collection_name: str | None = None):
    """Factory function to get vector store based on config"""
    config = get_config()

    if config.vector_store.backend == "chromadb":
        from src.vectordb.chromadb_store import ChromaDBStore
        return ChromaDBStore(collection_name)
    elif config.vector_store.backend == "openai":
        from src.vectordb.openai_store import OpenAIStore
        return OpenAIStore(collection_name)
    else:
        raise ValueError(f"Unknown vector store backend: {config.vector_store.backend}")
```

**Update file_search_agent.py**:
- Remove dependency on OpenAI's file_search tool
- Use custom `semantic_search_tool` instead
- Agent receives search results directly instead of via vector_store_id parameter
- Remove vector_store_id from agent creation

**Before:**
```python
def create_file_search_agent(mcp_servers: list[MCPServer], vector_store_id: str):
    return Agent(
        name="FileSearchAgent",
        tools=[...],  # file_search implicitly available
        tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}}
    )
```

**After:**
```python
def create_file_search_agent(mcp_servers: list[MCPServer], collection_name: str):
    from src.agents.tools.semantic_search import semantic_search_tool

    return Agent(
        name="FileSearchAgent",
        tools=[semantic_search_tool, ...],
        # No tool_resources needed
    )
```

### Phase 3: Update DataPrep Pipeline

**Modify `mcp_functions.py`**:

```python
def add_files_to_vectorstore(
    inputs: List[str],  # URLs or filenames
    config: Config,
    collection_name: str,
) -> UploadResult:
    """
    Add files to vector store (ChromaDB or OpenAI).

    Instead of uploading to OpenAI, chunk documents and add to vector store.
    """
    vector_store = get_vector_store(collection_name)

    # Load documents from knowledge DB
    kb = KnowledgeDB(config)
    documents = []

    for input_ref in inputs:
        entry = kb.get_entry(input_ref)
        if entry:
            # Load file content
            file_path = Path(config.data.local_storage_dir) / entry.filename
            content = file_path.read_text()

            # Chunk content (implement chunking strategy)
            chunks = chunk_document(content, chunk_size=1000, overlap=200)

            # Create Document objects
            for i, chunk in enumerate(chunks):
                documents.append(Document(
                    id=f"{entry.filename}_chunk_{i}",
                    content=chunk,
                    metadata={
                        "filename": entry.filename,
                        "url": entry.url,
                        "title": entry.title,
                        "chunk_index": i,
                        "keywords": entry.keywords
                    }
                ))

    # Add to vector store
    doc_ids = vector_store.add_documents(documents)

    # Update knowledge DB with vector IDs
    # ... (implementation)

    return UploadResult(
        collection_name=collection_name,
        total_files_requested=len(inputs),
        documents_added=len(doc_ids),
        # ... other fields
    )
```

**Update `knowledge_db.py` schema**:

```python
class KnowledgeEntry(BaseModel):
    url: str
    filename: str
    title: str
    keywords: List[str]
    summary: str = ""
    created_at: str

    # Vector store tracking
    vector_backend: str = ""  # "chromadb", "openai", etc.
    vector_ids: List[str] = []  # ChromaDB document IDs
    chunk_count: int = 0        # Track how many chunks created

    # Legacy OpenAI support
    openai_file_id: str = ""  # Keep for backward compatibility
    last_uploaded_at: str = ""
```

**Document chunking** (`src/vectordb/chunking.py`):

```python
def chunk_document(
    content: str,
    chunk_size: int = 1000,
    overlap: int = 200,
    separators: List[str] = ["\n\n", "\n", ". ", " "]
) -> List[str]:
    """
    Split document into chunks with overlap.

    Strategy:
    1. Try to split on paragraph boundaries (\n\n)
    2. Fall back to sentences (. )
    3. Fall back to words ( )
    4. Maintain overlap between chunks for context
    """
    # Implementation using recursive character text splitter
    # or similar strategy
    pass
```

### Phase 4: Embedding Model Integration

**New module** (`src/embeddings/`):

```
src/embeddings/
├── __init__.py
├── base.py           # Abstract embedder interface
├── local.py          # sentence-transformers local embeddings
└── litellm.py        # LiteLLM endpoint for vLLM embeddings
```

**Abstract interface** (`base.py`):
```python
from abc import ABC, abstractmethod
from typing import List

class EmbedderBase(ABC):
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents"""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embed single query"""
        pass
```

**Local implementation** (`local.py`):
```python
from sentence_transformers import SentenceTransformer
from .base import EmbedderBase

class LocalEmbedder(EmbedderBase):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.model.encode([text])[0].tolist()
```

**vLLM via LiteLLM** (`litellm.py`):
```python
import litellm
from .base import EmbedderBase

class LiteLLMEmbedder(EmbedderBase):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        response = litellm.embedding(
            model=self.model,
            input=texts,
            api_base=self.base_url
        )
        return [item['embedding'] for item in response.data]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]
```

**Factory function** (`src/embeddings/__init__.py`):
```python
def get_embedder() -> EmbedderBase:
    """Get embedder based on configuration"""
    config = get_config()

    if config.embedding.provider == "local":
        from .local import LocalEmbedder
        return LocalEmbedder(config.embedding.model)
    elif config.embedding.provider == "litellm":
        from .litellm import LiteLLMEmbedder
        return LiteLLMEmbedder(
            base_url=config.embedding.litellm.base_url,
            model=config.embedding.litellm.model
        )
    else:
        raise ValueError(f"Unknown embedding provider: {config.embedding.provider}")
```

### Phase 5: Remove Obsolete Code

**Files/Functions to remove or refactor:**

1. **`should_apply_tool_filter()`** in `src/agents/utils.py`:
   - No longer needed since we're not using OpenAI's file_search
   - Remove from `agentic_research_agent.py` handoff configuration

2. **`vector_store_manager.py`**:
   - Move OpenAI-specific code to `src/vectordb/openai_store.py`
   - Keep as legacy support during transition

3. **Update all agent factories**:
   - Replace `vector_store_id` parameter with `collection_name`
   - Remove `tool_resources` configuration

### Phase 6: Testing Strategy

**Unit tests** (`tests/vectordb/`):
```
tests/vectordb/
├── test_chromadb_store.py
├── test_embeddings.py
└── test_chunking.py
```

**Integration tests** (`integration_tests/`):
```
integration_tests/
├── test_chromadb_integration.py
├── test_search_agent_chromadb.py
└── test_dataprep_chromadb.py
```

**Test scenarios:**
1. Add documents to ChromaDB
2. Search with various queries
3. Verify chunking strategy
4. Test embedding generation
5. Compare results with OpenAI baseline (if available)
6. Performance benchmarks (search latency, throughput)

### Phase 7: Backward Compatibility

**Support both backends during transition:**

```python
# In main.py
if config.vector_store.backend == "openai":
    # Legacy path
    vector_store_id = get_vector_store_id_by_name(client, config.vector_store.name)
    research_info = ResearchInfo(
        vector_store_id=vector_store_id,
        ...
    )
else:
    # New ChromaDB path
    research_info = ResearchInfo(
        collection_name=config.vector_store.name,
        vector_backend="chromadb",
        ...
    )
```

**Update ResearchInfo schema:**
```python
class ResearchInfo(BaseModel):
    vector_store_name: str

    # Backend-specific fields
    vector_store_id: str = ""  # OpenAI (legacy)
    collection_name: str = ""   # ChromaDB
    vector_backend: str = "chromadb"  # Default to new backend

    temp_dir: str
    max_search_plan: str
    output_dir: str
```

## Implementation Order

1. ✅ **Document the plan** (this file)
2. **Phase 1**: Create vector store abstraction + ChromaDB implementation
3. **Phase 4**: Add embedding support (needed for ChromaDB)
4. **Phase 3**: Update DataPrep pipeline to use ChromaDB
5. **Phase 2**: Replace file_search tool in agents
6. **Phase 5**: Remove obsolete code
7. **Phase 6**: Add comprehensive tests
8. **Phase 7**: Ensure backward compatibility

## Future: Docker Deployment on DGX Spark

Once local ChromaDB works, containerize:

### Docker Compose Structure

```yaml
services:
  # Model serving
  embedding-service:
    image: vllm/vllm-openai:latest
    command: --model BAAI/bge-large-en-v1.5 --port 8001
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  reasoning-service:
    image: vllm/vllm-openai:latest
    command: --model deepseek-ai/deepseek-r1 --port 8002
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  instruct-service:
    image: vllm/vllm-openai:latest
    command: --model meta-llama/Llama-3.1-8B-Instruct --port 8003
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  # LiteLLM proxy
  litellm-proxy:
    image: ghcr.io/berriai/litellm:latest
    ports:
      - "4000:4000"
    environment:
      - LITELLM_CONFIG=/app/litellm_config.yaml
    volumes:
      - ./litellm_config.yaml:/app/litellm_config.yaml

  # Vector database
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - ./data/chromadb:/chroma/chroma
    environment:
      - ANONYMIZED_TELEMETRY=False

  # MCP DataPrep server
  mcp-dataprep:
    build:
      context: .
      dockerfile: docker/Dockerfile.mcp
    ports:
      - "8001:8001"
    depends_on:
      - chromadb
      - litellm-proxy
    volumes:
      - ./data:/app/data

  # Main application backend
  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    depends_on:
      - embedding-service
      - reasoning-service
      - instruct-service
      - litellm-proxy
      - chromadb
      - mcp-dataprep
    environment:
      - VECTOR_STORE_BACKEND=chromadb
      - CHROMADB_HOST=chromadb
      - LITELLM_BASE_URL=http://litellm-proxy:4000
```

### LiteLLM Configuration

```yaml
# litellm_config.yaml
model_list:
  - model_name: embedding
    litellm_params:
      model: openai/BAAI/bge-large-en-v1.5
      api_base: http://embedding-service:8001/v1

  - model_name: reasoning
    litellm_params:
      model: openai/deepseek-r1
      api_base: http://reasoning-service:8002/v1

  - model_name: instruct
    litellm_params:
      model: openai/llama-3.1-8b-instruct
      api_base: http://instruct-service:8003/v1
```

## Success Criteria

- [ ] ChromaDB stores and retrieves documents correctly
- [ ] Semantic search returns relevant results
- [ ] All existing functionality works with ChromaDB backend
- [ ] Performance is acceptable (search <500ms for typical queries)
- [ ] Tests cover all vector store operations
- [ ] Can switch between OpenAI and ChromaDB via configuration
- [ ] Documentation updated with new architecture
- [ ] Ready for Docker containerization

## Notes

- Start with local ChromaDB and sentence-transformers for development
- Test thoroughly before moving to vLLM + Docker
- Keep OpenAI backend as fallback during transition
- Monitor performance and adjust chunking strategy as needed
- Consider implementing caching for frequently accessed chunks
