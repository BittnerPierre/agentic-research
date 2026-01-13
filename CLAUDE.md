# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multi-agent research assistant system that uses OpenAI Agents SDK and MCP (Model Context Protocol) servers to conduct in-depth research on topics by searching through a knowledge base, planning investigations, and producing comprehensive reports.

The system supports three different manager implementations:
- **agentic_manager** (default): Supervisor agent with Chain-of-Thought reasoning
- **deep_manager**: Deep research approach with knowledge preparation phase
- **manager**: Simple parallel search approach (standard implementation)

## Core Architecture

### Multi-Agent System

The system orchestrates multiple specialized agents working together:

1. **Research Supervisor Agent** (`agentic_research_agent.py`): Top-level orchestrator that coordinates the entire research workflow using handoffs and tool calls
2. **Knowledge Preparation Agent** (`knowledge_preparation_agent.py`): Prepares research agenda and identifies missing knowledge (used by deep_manager)
3. **File Search Planning Agent** (`file_search_planning_agent.py`): Creates structured search plans with queries and reasons
4. **File Search Agent** (`file_search_agent.py`): Executes searches against the OpenAI vector store using file_search tool
5. **Writer Agent** (`file_writer_agent.py`): Synthesizes research findings into comprehensive markdown reports

### Manager Implementations

Three manager classes orchestrate different research workflows in `src/`:

- **AgenticResearchManager** (`agentic_manager.py`): Uses a supervisor agent that coordinates sub-agents via handoffs. The supervisor has access to planning, search, and writer agents as tools.
- **DeepResearchManager** (`deep_research_manager.py`): Sequential workflow with explicit knowledge preparation, planning, parallel search, and report writing phases
- **StandardResearchManager** (`manager.py`): Basic workflow with web search (not file search) capabilities

### MCP Server Integration

Two MCP servers are used:

1. **Filesystem MCP Server** (external): Standard @modelcontextprotocol/server-filesystem for file operations in a temporary directory
2. **DataPrep MCP Server** (`src/mcp/dataprep_server.py`): Custom FastMCP server providing knowledge base management tools:
   - `download_and_store_url_tool`: Downloads URLs and stores them in local knowledge base
   - `upload_files_to_vectorstore_tool`: Uploads files to OpenAI vector store with optimization (reuses existing file IDs)
   - `get_knowledge_entries_tool`: Lists knowledge base contents

### Data Flow Architecture

```
User Query → Manager Selection → MCP Server Initialization
    ↓
Research Supervisor Agent
    ↓
Knowledge Preparation (optional, deep_manager only)
    ↓
File Search Planning → FileSearchPlan (list of FileSearchItem)
    ↓
Parallel File Searches → List of search results
    ↓
Writer Agent → ReportData (markdown report + summary + follow-up questions)
```

### Key Data Models

All schemas are defined in `src/agents/schemas.py`:

- **ResearchInfo**: Context passed to all agents containing vector_store_id, temp_dir, max_search_plan, output_dir
- **FileSearchItem**: Single search with query and reason
- **FileSearchPlan**: Collection of FileSearchItem objects
- **FileSearchResult**: Results from a search including file_name and summary
- **ReportData**: Final output with markdown_report, short_summary, follow_up_questions, research_topic

### Knowledge Base System

The DataPrep module (`src/dataprep/`) manages a thread-safe local knowledge base:

- **KnowledgeDB** (`knowledge_db.py`): Thread-safe JSON database with file locking using portalocker
- **Models** (`models.py`): Pydantic schemas for KnowledgeEntry and UploadResult
- **Web Loader** (`web_loader_improved.py`): Downloads and converts web pages to markdown
- **Vector Store Manager** (`vector_store_manager.py`): Handles OpenAI vector store operations
- **Workflow** (`workflow.py`): Orchestrates the complete data preparation pipeline

Key optimization: The system reuses OpenAI file IDs to avoid redundant uploads when the same content is needed in different vector stores.

## Configuration System

Configuration is managed via YAML files in the root directory and `configs/` folder:

- **config.yaml**: Default configuration (mixed models)
- **configs/config-*.yaml**: Alternative configurations for different model combinations

Configuration structure (`src/config.py`):
```python
Config
├── config_name: str
├── vector_store: VectorStoreConfig (name, description, expires_after_days, vector_store_id)
├── data: DataConfig (urls_file, knowledge_db_path, local_storage_dir)
├── debug: DebugConfig (enabled, output_dir, save_reports)
├── logging: LoggingConfig (level, format)
├── models: ModelsConfig (research_model, planning_model, search_model, writer_model, knowledge_preparation_model)
├── manager: ManagerConfig (default_manager)
└── agents: AgentsConfig (max_search_plan, output_dir)
```

Models support both OpenAI format (`openai/gpt-4.1-mini`) and LiteLLM format (`litellm/anthropic/claude-3-7-sonnet-20250219`).

Environment variable overrides:
- `DEBUG`: Override debug mode
- `DEFAULT_MANAGER`: Override default manager selection

## Development Commands

### Setup
```bash
# Install dependencies
poetry install

# Start the DataPrep MCP server (required for research workflows)
poetry run dataprep_server
```

### Running Research
```bash
# Interactive mode with default manager (agentic_manager)
poetry run agentic-research

# With specific manager
poetry run agentic-research --manager deep_manager
poetry run agentic-research --manager manager

# With query from command line
poetry run agentic-research --query "Retrieval Augmented Generation"

# With syllabus file
poetry run agentic-research --syllabus syllabus.md

# With custom configuration
poetry run agentic-research --config configs/config-gpt-4.1-mini.yaml

# With custom vector store name
poetry run agentic-research --vector-store "my-research-session"

# With custom output directory
poetry run agentic-research --output-dir "output/my-session/"

# Debug mode (keeps temporary files)
poetry run agentic-research --debug
```

### Data Preparation
```bash
# Run dataprep workflow (downloads URLs from urls.txt)
poetry run mcp-dataprep-workflow

# Legacy dataprep command
poetry run dataprep
```

### Testing
```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_file_search.py

# Run integration tests
poetry run pytest integration_tests/

# Verbose output
poetry run pytest -v

# With warnings
poetry run pytest -v --disable-warnings=false
```

### Evaluation
```bash
# Evaluate writer agent
poetry run evaluate_writer

# Test trajectory
poetry run test_trajectory
```

### Code Quality
```bash
# Run ruff linter
poetry run ruff check .

# Run ruff formatter
poetry run ruff format .

# Fix auto-fixable issues
poetry run ruff check --fix .
```

## Important Implementation Details

### Model Compatibility and Tool Filtering

The system handles different model capabilities through conditional tool filtering (`src/agents/utils.py`):

- **GPT models with file_search**: Can use the file_search tool directly in vector store interactions
- **Non-GPT models**: Cannot use file_search, so tools must be filtered out when handing off to writer agent
- The `should_apply_tool_filter()` function determines whether to apply `handoff_filters.remove_all_tools` based on model name

When creating handoffs in `agentic_research_agent.py`, the system checks the writer model and conditionally applies input filters to ensure compatibility.

### Tracing and Observability

The system includes comprehensive tracing:

- **OpenAI Agents Tracing**: Native tracing to OpenAI platform (https://platform.openai.com/traces/)
- **LangSmith Tracing**: Via OpenAIAgentsTracingProcessor
- **File-based Tracing**: Custom FileTraceProcessor writes traces to `traces/trace.log`

Traces can be viewed in the OpenAI platform using the trace_id printed at the start of each run.

### Agent Handoffs and Context

The supervisor agent uses the handoff pattern from openai-agents:
- Sub-agents are registered as handoffs with custom directives (e.g., WriterDirective)
- Context (ResearchInfo) is passed through all agent calls via the `context` parameter
- The writer agent receives search results through the directive's `search_results` field populated in the `on_handoff` callback

### Prompt Engineering

Agent prompts are loaded from markdown files in a `prompts/` directory (referenced in code but directory location should be verified). The supervisor uses a "research_lead_agent_revised.md" prompt with recommended handoff prefix.

### Vector Store Management

- Vector stores are created per session with configurable names
- The system checks if a vector store exists by name before creating a new one
- Files are uploaded to OpenAI Files API first, then attached to vector stores
- The knowledge base tracks `openai_file_id` to enable reuse across sessions

### Temporary Directory Usage

Each research session creates a temporary directory where:
- The filesystem MCP server operates
- Search results can be written as intermediate files
- Files are preserved in debug mode, otherwise cleaned up automatically

## Key Files to Understand

When modifying the system, these files form the core architecture:

- `src/main.py`: Entry point with CLI argument parsing and MCP server setup
- `src/config.py`: Configuration management with singleton pattern
- `src/agents/agentic_research_agent.py`: Supervisor agent factory function with handoff configuration
- `src/agents/schemas.py`: All Pydantic models for data passing between agents
- `src/agentic_manager.py`, `src/deep_research_manager.py`, `src/manager.py`: Three workflow orchestrators
- `src/dataprep/mcp_functions.py`: Core MCP tool implementations for knowledge management
- `src/dataprep/knowledge_db.py`: Thread-safe knowledge base with file locking

## External References

The `external-references/` directory contains reference implementations from other projects that inspired this architecture. These are for reference only and not used in the main codebase.
