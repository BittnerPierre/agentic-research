# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-24

First stable public release of Agentic Research: multi-agent workflow, ingestion + retrieval,
Docker deployment (local + DGX), benchmarks, and CI.

### Added
- Complete Docker deployment for local and DGX Spark (LLM + embeddings + DataPrep + ChromaDB).
- ChromaDB vector backend integrated via the DataPrep `vector_search` flow.
- Benchmarking framework: CLI runner, comparator, quality/compliance scores, and reports.
- Multi-model support for DGX (GLM, Qwen, GPT-OSS, Ministral, Mistral-Small/Magistral).
- GitHub Actions CI/CD (lint/format/tests on Python 3.12).
- Tracing and evaluation tools (trajectory specs, workflow evaluator, baseline/regression).
- Improved logging and diagnostics for debugging and traceability.

### Changed
- Retrieval flow unified through DataPrep (no parallel legacy paths).
- Retrieval quality improvements: query rewrite modes, file filtering, safer heuristics.
- Model configuration centralized for Docker/DGX with helper scripts.
- Documentation reorganized under `docs/`, with plans archived.

### Fixed
- Pipeline stability: MCP timeouts, parallel uploads, safer retrieval paths.
- ChromaDB integration: embedding config alignment, cache persistence, volume fixes.
- Benchmark reliability: better metrics, DGX remote fixes, robust scripts.
- Test stability: lint/format/test alignment and CI fixes.
