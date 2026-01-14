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
6. ✅ **Leverage existing code**: Extend `evaluations/write_agent_eval.py` pattern

---

## 🔑 Key Insight: Simpler Approach

**Existing `evaluations/write_agent_eval.py` already has everything we need!**

```python
# Run agent
result = Runner.run_streamed(agent, input, ...)

# Get output
report = result.final_output_as(ReportData)

# Get messages for validation
messages = result.to_input_list()

# Validate trajectory
validation = validate_trajectory_spec(messages, spec)

# Validate quality (LLM-as-a-judge)
quality = await Runner.run(quality_agent, report.markdown_report, ...)
```

**No custom tracing infrastructure needed!** Just extend existing pattern to cover full workflow.

---

## 📋 Implementation Phases

### **Phase 1: Define Trajectory Specs** 📝 Foundation

Goal: Create trajectory validation specs for supervisor and research agents

| Task | Status | Files | Testable Output |
|------|--------|-------|----------------|
| 1.1 Create trajectory_specs.py | ⬜ TODO | `evaluations/trajectory_specs.py` | Module created |
| 1.2 Define SUPERVISOR_TRAJECTORY_SPEC | ⬜ TODO | `evaluations/trajectory_specs.py` | Spec validates supervisor flow |
| 1.3 Define RESEARCH_TRAJECTORY_SPEC | ⬜ TODO | `evaluations/trajectory_specs.py` | Spec validates research agent flow |
| 1.4 Import WRITER_TRAJECTORY_SPEC | ⬜ TODO | `evaluations/trajectory_specs.py` | Reuses existing writer spec |

**Example Trajectory Spec** (from existing code):
```python
WRITER_TRAJECTORY_SPEC = {
    "trajectory_spec": [
        {"id": "load_data", "type": "function_call", "name": "read_multiple_files"},
        {"id": "raw_notes", "type": "generation", "match_regex": r"## Raw Notes"},
        {"id": "agenda", "type": "generation", "match_regex": r"## Detailed Agenda"},
        {"id": "report", "type": "generation", "match_regex": r"## Report"},
        {"id": "save_report", "type": "function_call", "name": "save_report"}
    ]
}
```

**Acceptance**: All trajectory specs defined with clear validation rules

---

### **Phase 2: Full Workflow Evaluator** 🔬 Implementation

Goal: Extend evaluation to cover complete research workflow

| Task | Status | Files | Testable Output |
|------|--------|-------|----------------|
| 2.1 Create full_workflow_evaluator.py | ⬜ TODO | `evaluations/full_workflow_evaluator.py` | Module created |
| 2.2 Add FullWorkflowEvaluator class | ⬜ TODO | `evaluations/full_workflow_evaluator.py` | Extends write_agent_eval pattern |
| 2.3 Validate supervisor trajectory | ⬜ TODO | `evaluations/full_workflow_evaluator.py` | Checks supervisor executed correctly |
| 2.4 Validate research agent trajectory | ⬜ TODO | `evaluations/full_workflow_evaluator.py` | Checks research completed |
| 2.5 Validate writer trajectory (reuse) | ⬜ TODO | `evaluations/full_workflow_evaluator.py` | Uses existing validation |
| 2.6 Quality evaluation (reuse LLM-as-a-judge) | ⬜ TODO | `evaluations/full_workflow_evaluator.py` | Uses existing prompts |
| 2.7 Add CLI entry point | ⬜ TODO | `pyproject.toml` | `poetry run eval-workflow` works |

**Acceptance**: Run full workflow → validate all agents → grade quality → PASS/FAIL

---

### **Phase 3: Test Case & Baseline** 📊 Documentation

Goal: Define trivial test case and establish baseline

| Task | Status | Files | Testable Output |
|------|--------|-------|----------------|
| 3.1 Define trivial test case | ⬜ TODO | `evaluations/test_cases/trivial_research.yaml` | YAML with syllabus + criteria |
| 3.2 Run baseline evaluation | ⬜ TODO | `evaluations/baselines/baseline_<commit>.json` | JSON baseline saved |
| 3.3 Add regression comparison | ⬜ TODO | `evaluations/full_workflow_evaluator.py` | Detects degradation |

**Test Case Example**:
```yaml
syllabus: "Python basics: variables, functions, loops"
expected_outcomes:
  - min_sources: 3
  - required_sections: ["Raw Notes", "Detailed Agenda", "Report"]
  - min_word_count: 500
  - topics_covered: ["variables", "functions", "loops"]
```

**Acceptance**: Baseline exists + regression testing works

---

## 🧪 Testing Strategy

### Unit Tests
- `tests/test_trajectory_specs.py` - Validate specs are well-formed
- `tests/test_full_workflow_evaluator.py` - Test evaluation logic

### Integration Test
```bash
# Run full workflow with evaluation
poetry run eval-workflow --syllabus "Python basics"
# Expected: ✅ PASS with detailed breakdown
```

### Regression Test
```bash
# Compare against baseline
poetry run eval-workflow --syllabus "Python basics" --compare-baseline
# Expected: No degradation detected
```

---

## 📦 Deliverables

### Success Criteria
1. ✅ Trajectory specs for all agents (supervisor, research, writer)
2. ✅ Full workflow evaluator using existing patterns
3. ✅ Test case definition for trivial research
4. ✅ Baseline report for regression testing
5. ✅ CLI tool: `poetry run eval-workflow`

### What This Enables
- ✅ **Pre-migration validation**: "System works on commit X"
- ✅ **Post-migration validation**: "System still works on commit Y"
- ✅ **Regression testing**: "No degradation after file_search → vector search"
- ✅ **Manager-agnostic**: Works with any manager implementation
- ✅ **CI/CD ready**: Gate deployments on evaluation PASS

---

## 🎯 Current Priority

**Next Task**: Phase 1, Task 1.1 - Create `evaluations/trajectory_specs.py`

**Why this first?**
- Foundation for all validation
- Small, focused file (~100 lines)
- Leverages existing pattern from `write_agent_eval.py`
- Immediately testable

**Estimated Time**: 1-2 hours

**Simplified Approach**:
- NO custom tracing infrastructure
- NO new logging systems
- Just extend existing evaluation code pattern

---

## 📊 Progress Tracking

```
Phase 1: ██████████ 4/4 tasks (100%) ✅ COMPLETE
Phase 2: ██████████ 7/7 tasks (100%) ✅ COMPLETE
Phase 3: ██████████ 3/3 tasks (100%) ✅ IMPLEMENTATION COMPLETE

Overall: ██████████ 14/14 tasks (100%) ⚠️ NEEDS TESTING
```

## ✅ Implemented (Not Yet Tested)

### Phase 1: Trajectory Specs ✅
- `evaluations/trajectory_specs.py` (300 lines)
- Specs for supervisor, research, writer agents
- 19 unit tests passing

### Phase 2: Full Workflow Evaluator ✅
- `evaluations/full_workflow_evaluator.py` (390 lines)
- Extends write_agent_eval.py pattern
- CLI: `poetry run eval-workflow --syllabus "..."`

### Phase 3: Baseline & Regression Testing ✅
- `evaluations/test_cases/trivial_research.yaml` (test case definition)
- `evaluations/baseline_runner.py` (450 lines)
- CLI: `poetry run baseline-eval --test-case trivial_research`

## 🧪 Next Step: Integration Testing

**Before marking complete**, need to:
1. Run `poetry run baseline-eval --test-case trivial_research --save-baseline`
2. Verify workflow executes without errors
3. Verify all trajectory checkpoints pass
4. Verify quality grades are reasonable
5. Test regression comparison works

**Estimated time**: 1-2 hours

---

## 🔗 Related Work

- ✅ Existing: `evaluations/write_agent_eval.py` - Working evaluation for writer
- ✅ Existing: `evaluations/eval_utils.py` - `validate_trajectory_spec()` function
- ✅ Existing: `evaluations/prompts.py` - LLM-as-a-judge prompts (V3)
- ✅ Existing: `evaluations/schemas.py` - Evaluation result schemas
- ✅ Proven: `tests/test_agents_sdk_tracing_offline.py` - Offline operation validated

---

## 📝 Architecture Decisions

### Decision 1: No Custom Tracing Infrastructure
**Rationale**: SDK Runner results already contain everything via `result.to_input_list()`

### Decision 2: Extend Existing Evaluation Code
**Rationale**: `write_agent_eval.py` proves the pattern works - just extend it

### Decision 3: Manager-Agnostic Evaluation
**Rationale**: Validate OUTCOMES (sources, report), not HOW (execution details)

### Decision 4: Simpler is Better
**Rationale**: User feedback - leverage existing code, don't over-engineer

---

**Last Updated**: 2026-01-14
**Next Review**: After Phase 1 completion
