# Repository Guidelines

## Project Structure & Module Organization
- `src/` contains the application code (CLI entrypoints, managers, agents, MCP integrations).
- `tests/` holds pytest-based unit/integration tests (e.g., `tests/test_*.py`).
- `evaluations/` contains evaluation runners and baselines used for research experiments.
- `configs/` and `configs/config-default.yaml` store runtime configuration defaults.
- `data/`, `output/`, `logs/`, and `traces/` are runtime artifacts and should not be treated as source of truth.
- `docs/` and `external-references/` collect supporting documentation and references.

## Build, Test, and Development Commands
- `poetry install` installs dependencies.
- `poetry run agentic-research` runs the interactive CLI.
- `poetry run agentic-research --query "..."` runs a non-interactive query.
- `poetry run dataprep_server` starts the MCP dataprep server used by the agents.
- `poetry run pytest` runs the test suite (pytest is configured in `pyproject.toml`).
- `poetry run ruff check .` and `poetry run ruff format .` enforce linting and formatting.
- These commands mirror CI checks; run them locally before pushing.

## Coding Style & Naming Conventions
- Python 3.12, 4-space indentation, line length 100 (ruff).
- `ruff` is the single source of truth for linting and formatting.
- Use `snake_case` for functions/modules, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants.
- Keep imports absolute from project root (e.g., `import src.main`) to avoid module shadowing.

## Testing Guidelines
- Framework: `pytest` with `pytest-asyncio` for async tests.
- Place tests in `tests/` and name them `test_*.py`.
- Prefer deterministic tests; avoid external network calls unless explicitly mocked.

## Commit & Pull Request Guidelines
- Work must start from a GitHub issue with explicit approval before coding begins.
- Each issue is handled independently on its own branch; avoid mixing concerns.
- Commit messages follow Conventional Commits (e.g., `feat: ...`, `fix: ...`, `docs: ...`, `test: ...`).
- Add a co-author trailer for this agent: `Co-Authored-By: Codex <noreply@openai.com>`.
- PRs should describe scope, link issues, and include test evidence (command output or notes).
- PRs are required for all changes; direct push to `main` is blocked by branch protection.
- CI/CD checks are mandatory and must pass before merge: Lint, Format, Tests (Python 3.11 & 3.12).
- The CI workflow is defined in `.github/workflows/ci.yml` and typically runs in ~2–3 minutes.

## Configuration & Runtime Notes
- Default manager selection lives in `configs/config-default.yaml` (`manager.default_manager`).
- You can override the default manager with `DEFAULT_MANAGER` environment variable.

## Architecture & Planning Notes
- The multi-agent flow is: supervisor → (optional) knowledge prep → plan → parallel search → writer report.
- MCP servers include a filesystem server and the custom DataPrep server in `src/mcp/dataprep_server.py`.
- Future architecture changes are tracked in `CHROMADB_MIGRATION_PLAN.md`.
- Active roadmap items live in GitHub issues #11–#13 (vector store integration, Response API removal, DGX Spark deployment).
- Evaluation work targets cross-LLM comparisons (OpenAI, Claude, Mistral) plus open-source models via `vllm` or `llama.cpp`.
