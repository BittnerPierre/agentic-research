# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Entries are written feature-first (what changed for a user of the project), one per merged pull request, newest
first; entries reconstructed after the fact may group closely related PRs. Earlier published history is kept below.

## [Unreleased]

### Docs
- Changelog history reconstructed between 0.1.0 and 2026-07-10 and entries reworded feature-first. ([#231](https://github.com/BittnerPierre/agentic-research/pull/231), closes #230)

## 2026-09-04

### Added
- DeepSeek-V4-Flash-0731 runs on the DGX Spark cluster: model-card campaign config, and the investigation that isolated
  its serving bug to the `vllm-node-b12x` build (`dev/infernal-invocation`) — confirmed fixed by the 2026-09-03 recipe
  (`dev/jovian-judgement`). Minimal reproduction kit published separately
  (https://github.com/BittnerPierre/dsv4f-0731-vllm-b12x-repro); REX on the checkpoint's obedience bias in the campaign
  report (§28). ([#208](https://github.com/BittnerPierre/agentic-research/pull/208), closes #207)

### Docs
- `CHANGELOG.md` restarted in Keep a Changelog format with one entry per merged PR since #197; rule added to CLAUDE.md
  and AGENTS.md that every PR adds its entry. ([#229](https://github.com/BittnerPierre/agentic-research/pull/229), closes #228)

## 2026-09-02

### Added
- Qwen3.8-27B-NVFP4 joins the bench, smoke-tested on the Spark: best conceptual coverage so far (81.2 %), finance A / 100 %.
  Along the way the campaign pre-flight's vLLM conformity check is fixed (it was silently disabled for generated configs)
  and battery summaries lose their pydantic noise. ([#224](https://github.com/BittnerPierre/agentic-research/pull/224), issue #223)
- OpenRouter — and any OpenAI-compatible cloud provider — usable as a model backend: provider keys are read from the
  environment (`.env`), never written in a config. DeepSeek-V4-Flash-0731 verified end-to-end through OpenRouter
  (finance A / 100 %, conceptual 87.5 %). ([#220](https://github.com/BittnerPierre/agentic-research/pull/220), issue #219)
- Benchmark campaigns can be run end-to-end by any agent (Claude Code, Codex) without touching the code base: the
  `benchmark-campaign` skill becomes a standard Agent Skills package (`evaluations/campaign/`, discovered from
  `.claude/skills/` and `.agents/skills/`), with model listing, config generation, frozen-corpus check before any
  battery, service conformity in the pre-flight, clearer battery output, and 22 tests. ([#210](https://github.com/BittnerPierre/agentic-research/pull/210), issue #209)

## 2026-09-01

### Added
- The benchmark becomes trustworthy: evidence-bound validator (chunk-level citation resolution, run-pack provenance,
  judge/contradictor adjudication, mandatory second reading) and the July 2026 eight-model campaign with its report,
  campaign tooling and post-exam adjustments registry. ([#204](https://github.com/BittnerPierre/agentic-research/pull/204), closes #201)
- Decomposed writer for mid-size open-weight models — programmatic source aggregation, outline, parallel chapters,
  assembly — behind the `writer_strategy` flag, with the benchmark spike harness (finance and conceptual exercises,
  deterministic grader). ([#197](https://github.com/BittnerPierre/agentic-research/pull/197), closes #196)

### Changed
- Ingestion no longer drops corpus documents whose content matched artifact filters. ([#204](https://github.com/BittnerPierre/agentic-research/pull/204))

## 2026-07-10

### Fixed
- File search agent more reliable on mid-size models: result handling and chunk citations hardened. ([#200](https://github.com/BittnerPierre/agentic-research/pull/200), closes #198)

## 2026-05-12

### Added
- vLLM on DGX Spark as a first-class benchmark setup (workstream WS1, round 2): start/stop/bench scripts resolve the
  active compose overlay instead of assuming the llama.cpp duo, vLLM "mono" setups for Qwen3.6-27B-NVFP4 and
  Mistral-Small-4-119B-NVFP4 (custom arm64/sm_121 image), and full-payload tracing of model spans to diagnose tool-call
  behavior on vLLM. ([#193](https://github.com/BittnerPierre/agentic-research/pull/193), closes #181, #182, #186)

## 2026-04-30

### Added
- Per-agent reasoning effort and verbosity: each agent role runs its model with its own reasoning setting — hybrid
  models can reason on planning and answer directly on search and drafting. ([#176](https://github.com/BittnerPierre/agentic-research/pull/176), closes #170)
- DGX benchmark harness runs any compose overlay per setup (llama.cpp duo or vLLM mono) with healthcheck-based
  restarts. ([#177](https://github.com/BittnerPierre/agentic-research/pull/177), closes #169)

## 2026-04-26

### Added
- Local OpenAI-compatible inference endpoints (vLLM, llama.cpp) served directly, without LiteLLM in between, with a
  per-endpoint choice between the Chat Completions and Responses APIs. ([#160](https://github.com/BittnerPierre/agentic-research/pull/160) closes #158, [#165](https://github.com/BittnerPierre/agentic-research/pull/165) closes #164)

## 2026-04-21

### Fixed
- Small-model robustness: a file search agent answering with a plain string is accepted, and `vector_search` tolerates
  string filenames. ([#161](https://github.com/BittnerPierre/agentic-research/pull/161), [#162](https://github.com/BittnerPierre/agentic-research/pull/162))

## 2026-04-17

### Added
- No report without sources: when searches produce no usable result the run is marked incomplete instead of writing an
  ungrounded report. ([#156](https://github.com/BittnerPierre/agentic-research/pull/156), closes #145)
- Product vision, roadmap analysis and Sprint 1 backlog documented. ([#153](https://github.com/BittnerPierre/agentic-research/pull/153), [#155](https://github.com/BittnerPierre/agentic-research/pull/155))

### Changed
- Build tooling migrated from Poetry to uv. ([#154](https://github.com/BittnerPierre/agentic-research/pull/154), closes #128)

## 2026-04-09

### Added
- Containerized llama.cpp instruct benchmark (llama-bench) on DGX Spark, producing markdown/CSV comparison tables.
  ([#143](https://github.com/BittnerPierre/agentic-research/pull/143))

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
