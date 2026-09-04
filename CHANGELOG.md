# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
One entry per merged pull request, newest first. Earlier published history is kept below the dated entries.

## [Unreleased]

### Docs
- `CHANGELOG.md` restarted in Keep a Changelog format with one entry per merged PR since #197; rule added to
  CLAUDE.md and AGENTS.md that every PR adds its entry. ([#229](https://github.com/BittnerPierre/agentic-research/pull/229), closes #228)

## 2026-09-04

### Added
- DeepSeek-V4-Flash-0731 campaign config aligned on the model card (temperature 1.0, top_p 0.95, chat mode) and the
  investigation of its serving bug on the `vllm-node-b12x` build: minimal reproduction kit (now in its own repo,
  https://github.com/BittnerPierre/dsv4f-0731-vllm-b12x-repro), diagnostic (build `dev/infernal-invocation` at fault,
  fixed by the 2026-09-03 recipe on `dev/jovian-judgement`), and REX §28 of the campaign report on the checkpoint's
  obedience bias. ([#208](https://github.com/BittnerPierre/agentic-research/pull/208), closes #207)

## 2026-09-02

### Added
- Qwen3.8-27B-NVFP4 campaign config (model-card sampling), smoke-tested on the Spark: conceptual coverage 81.2 % (best
  on the bench so far), finance A / 100 %. Also fixes the campaign pre-flight (vLLM conformity guard silently disabled
  for generated configs, now keyed on `base_url spark1:8000`) and filters pydantic noise from battery summaries.
  ([#224](https://github.com/BittnerPierre/agentic-research/pull/224), issue #223)
- `api_key_env` on model endpoints: cloud provider keys are read from the environment (`.env`), never written in a
  YAML; explicit `api_key` still wins; a declared-but-missing variable fails clearly. OpenRouter diagnostic config for
  DSV4F-0731. ([#220](https://github.com/BittnerPierre/agentic-research/pull/220), issue #219)
- `benchmark-campaign` skill repackaged as a standard Agent Skills package under `evaluations/campaign/` (SKILL.md,
  scripts, references, evals), discovered by symlinks from `.claude/skills/` and `.agents/skills/` (Claude Code and
  Codex); campaigns run without modifying the code base. New tools: `list_models.py`, `new_model_config.py`,
  `verify_corpus.py`; frozen-corpus check before any battery; dataprep/embeddings/vLLM conformity in the pre-flight;
  22 tests. Also fixes `compile_table.py` tag matching (tags containing `concept`/`capex`), shows the E letter on
  conceptual rows, and makes batteries flag `evaluation_failed` and non-qualified packs in the console.
  ([#210](https://github.com/BittnerPierre/agentic-research/pull/210), issue #209)

## 2026-09-01

### Added
- Evidence-bound validator hardened (`filename:index` chunk resolution, run-pack provenance, judge/contradictor
  adjudication, second-reading doctrine) and the July 2026 eight-model campaign: report, campaign tooling
  (`check_services`, `run_battery`, `regrade`, `compile_table`), per-model configs, `adjustments.yaml`.
  ([#204](https://github.com/BittnerPierre/agentic-research/pull/204), closes #201)
- Decomposed writer behind the `writer_strategy` flag (programmatic source aggregation, outline, parallel chapters,
  assembly) plus the benchmark spike harness (exercises `ai-capex-intensity` and `ai-engineering-syllabus`, deterministic
  grader, spike comparison). ([#197](https://github.com/BittnerPierre/agentic-research/pull/197), closes #196)

### Changed
- Ingestion no longer filters out corpus artifacts that carried the subject matter (`vector_backends.py`).
  ([#204](https://github.com/BittnerPierre/agentic-research/pull/204))

## 2026-07-10

### Fixed
- File search reliability and citation handling. ([#200](https://github.com/BittnerPierre/agentic-research/pull/200), closes #198)

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
