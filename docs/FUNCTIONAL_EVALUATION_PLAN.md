# Functional Evaluation Implementation Plan

**Issue**: #8
**Status**: 🟡 In Progress
**Goal**: Validate that the agentic research system "works as expected"

---

## 🎯 Objectives

1. ✅ Define what "working" means (acceptance criteria)
2. ✅ Establish baseline before architectural changes
3. ✅ Enable regression testing after migrations
4. ✅ Automate validation without human review
5. ✅ **Manager-agnostic**: Works with StandardManager, AgenticManager, DeepManager
6. ✅ **Framework-agnostic**: Works offline, portable to PydanticAI/CrewAI

---

## 📋 Implementation Phases

### **Phase 1: Structured Trace Collection** 🔧 Foundation

Goal: Implement StructuredJSONTraceProcessor using Agents SDK (proven to work offline)

| Task | Status | Files | Testable Output |
|------|--------|-------|----------------|
| 1.1 Implement StructuredJSONTraceProcessor | ⬜ TODO | `src/tracing/processors/structured_json_processor.py` | Valid JSONL file created |
| 1.2 Integrate into main.py | ⬜ TODO | `src/main.py` | `traces/trace_<run_id>.jsonl` exists |
| 1.3 Create trace parsing utilities | ⬜ TODO | `evaluations/trace_utils.py` | `load_traces()` works |

**Acceptance**: Run workflow → structured traces generated → parseable with `jq` → **works offline**

**Architecture Decision**: Use Agents SDK TracingProcessor (proven to work offline)
- ✅ Works offline (validated: `tests/test_agents_sdk_tracing_offline.py`)
- ✅ Already integrated in codebase
- ✅ Captures all events automatically
- ✅ Manager-agnostic (traces any workflow)
- ✅ Optional OpenAI Platform / LangSmith integration

---

### **Phase 2: Acceptance Criteria Definition** 📝 Specification

Goal: Define what "working" means for a trivial test case

| Task | Status | Files | Testable Output |
|------|--------|-------|----------------|
| 2.1 Define baseline test case | ⬜ TODO | `evaluations/test_cases/trivial_research.yaml` | YAML validated |
| 2.2 Create trajectory specs | ⬜ TODO | `evaluations/trajectory_specs.py` | Specs cover all agents |

**Acceptance**: Test case YAML exists + trajectory specs defined for supervisor, research, writer

---

### **Phase 3: Functional Test Harness** 🔬 Validation

Goal: End-to-end evaluation of full workflow

| Task | Status | Files | Testable Output |
|------|--------|-------|----------------|
| 3.1 Implement FullWorkflowEvaluator | ⬜ TODO | `evaluations/full_workflow_evaluator.py` | Class runnable |
| 3.2 Trajectory validation from traces | ⬜ TODO | `evaluations/eval_utils.py` | Function exists |
| 3.3 Coverage validation | ⬜ TODO | `evaluations/coverage_validator.py` | Topics detected |
| 3.4 CLI entry point | ⬜ TODO | `pyproject.toml` + evaluator | `poetry run eval-full-workflow` works |

**Acceptance**: `poetry run eval-full-workflow --test-case trivial_research` → PASS/FAIL report

---

### **Phase 4: Baseline Establishment** 📊 Documentation

Goal: Document current system performance

| Task | Status | Files | Testable Output |
|------|--------|-------|----------------|
| 4.1 Run baseline evaluation | ⬜ TODO | `evaluations/baselines/baseline_trivial_<commit>.json` | Baseline saved |
| 4.2 Regression testing support | ⬜ TODO | `evaluations/full_workflow_evaluator.py` | Comparison works |

**Acceptance**: Baseline JSON exists + comparison against baseline detects regressions

---

### **Phase 5: Production Readiness** 🚀 Optional (Future)

Goal: Distributed observability for DGX Spark

| Task | Status | Files | Testable Output |
|------|--------|-------|----------------|
| 5.1 RedisTraceProcessor | ⬜ FUTURE | `src/tracing/processors/redis_processor.py` | Redis receives events |
| 5.2 LangfuseTraceProcessor | ⬜ FUTURE | `src/tracing/processors/langfuse_processor.py` | Langfuse dashboard shows traces |

**Acceptance**: Deploy on DGX Spark → traces appear in external observability platform

---

## 🧪 Testing Strategy

### Unit Tests (per task)
- `test_trace_utils.py` - JSONL parsing
- `test_coverage_validator.py` - topic detection
- `test_trajectory_validation.py` - workflow validation

### Integration Tests
- `test_structured_json_processor.py` - trace collection works
- `test_full_workflow_evaluator.py` - end-to-end evaluation

### Functional Test
```bash
# The ultimate test
poetry run eval-full-workflow --test-case trivial_research
# Expected: ✅ PASS with detailed breakdown
```

---

## 📦 Deliverables

### Phase 1-4 Complete = Success
1. ✅ Structured traces in `traces/trace_*.jsonl`
2. ✅ Test case definition in `evaluations/test_cases/trivial_research.yaml`
3. ✅ CLI tool: `poetry run eval-full-workflow`
4. ✅ Baseline report: `evaluations/baselines/baseline_trivial_<commit>.json`
5. ✅ Documentation: `EVALUATION.md`

### What This Enables
- ✅ **Pre-migration validation**: "System works on commit X"
- ✅ **Post-migration validation**: "System still works on commit Y"
- ✅ **Regression testing**: "No degradation after file_search → vector search"
- ✅ **CI/CD integration**: Gate deployments on evaluation PASS

---

## 🎯 Current Priority

**Next Task**: Phase 1, Task 1.1 - Implement `StructuredJSONTraceProcessor`

**Why this first?**
- Foundation for all other phases
- ✅ **Works offline** (proven: `tests/test_agents_sdk_tracing_offline.py`)
- ✅ **Leverage existing SDK** (already integrated)
- ✅ **Manager-agnostic** (traces any workflow automatically)
- Small, focused change (~100 lines, similar to FileTraceProcessor)
- Immediately useful for debugging (Issue #7)

**Estimated Time**: 2-3 hours

**Architecture**: Agents SDK TracingProcessor (extends existing pattern)

---

## 📊 Progress Tracking

```
Phase 1: ░░░░░░░░░░ 0/3 tasks (0%)
Phase 2: ░░░░░░░░░░ 0/2 tasks (0%)
Phase 3: ░░░░░░░░░░ 0/4 tasks (0%)
Phase 4: ░░░░░░░░░░ 0/2 tasks (0%)
Phase 5: ░░░░░░░░░░ 0/2 tasks (FUTURE)

Overall: ░░░░░░░░░░ 0/11 tasks (0%)
```

---

## 🔗 Related Issues

- Issue #7: Max turns exceeded - better traces would help debug
- Future: file_search → vector search migration needs regression testing

---

## 📝 Notes

- All tasks are **atomic** (can be completed independently)
- All tasks are **continuous** (build on previous tasks)
- All tasks are **testable** (clear acceptance criteria)
- Phases 1-4 are **required** for baseline
- Phase 5 is **optional** for production deployment

---

**Last Updated**: 2026-01-14
**Next Review**: After Phase 1 completion
