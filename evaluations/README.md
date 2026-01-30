# Evaluation Framework

Functional evaluation framework for the agentic research system.

## Overview

This framework validates that the agentic research system "works as expected" through:

1. **Trajectory Validation** - Verifies workflow execution (all agents ran in correct order)
2. **Quality Assessment** - LLM-as-a-judge grades report quality (format, grounding, agenda, usability)
3. **Regression Testing** - Detects degradation against previous baselines

**Manager-Agnostic**: Works with any manager implementation (AgenticManager, DeepManager, etc.)

Test cases describe inputs and expectations; the `--config` flag selects the model setup to evaluate.

## Components

### 1. Trajectory Specs (`trajectory_specs.py`)

Defines expected execution patterns for all agents:

```python
from evaluations.trajectory_specs import (
    SUPERVISOR_TRAJECTORY_SPEC,
    RESEARCH_TRAJECTORY_SPEC,
    WRITER_TRAJECTORY_SPEC,
    FULL_WORKFLOW_TRAJECTORY_SPEC,
)
```

### 2. Writer Agent Evaluator (`write_agent_eval.py`)

Runs the writer-only evaluation using YAML test cases (agenda + search results).

**CLI Usage:**
```bash
poetry run evaluate_writer \
    --test-case trivial_research \
    --config configs/config-default.yaml
```

### 3. Full Workflow Evaluator (`full_workflow_evaluator.py`)

Runs complete research workflow and evaluates:
- Trajectory correctness (all checkpoints passed)
- Report quality (A-E grades in 4 dimensions)

**CLI Usage:**
```bash
# Run evaluation (requires MCP servers running)
poetry run eval-workflow \
    --test-case trivial_research \
    --vector-store-name "agentic_research_data" \
    --config configs/config-default.yaml

# Or provide a custom syllabus directly
poetry run eval-workflow \
    --syllabus "Python basics" \
    --vector-store-name "agentic_research_data" \
    --config configs/config-gpt-4.1-mini.yaml
```

### 4. Baseline Runner (`baseline_runner.py`)

Executes evaluations against test cases and manages baselines.

**CLI Usage:**
```bash
# Run and save new baseline
poetry run baseline-eval \
    --test-case trivial_research \
    --vector-store-name "agentic_research_data" \
    --config configs/config-default.yaml \
    --save-baseline

# Compare against previous baseline
poetry run baseline-eval \
    --test-case trivial_research \
    --vector-store-name "agentic_research_data" \
    --config configs/config-gpt-4.1-mini.yaml \
    --compare-baseline baseline_trivial_abc123_20260114_153000.json
```

### 5. Test Cases (`test_cases/*.yaml`)

YAML definitions of test scenarios with expected outcomes.

**Example: `trivial_research.yaml`**
```yaml
name: "trivial_research"
syllabus: "Python basics: variables, functions, data structures"
expected_outcomes:
  min_sources: 2
  required_sections: ["Raw Notes", "Detailed Agenda", "Report"]
  min_word_count: 300
min_grades:
  format: "C"
  grounding: "C"
  agenda: "C"
  usability: "C"
writer_eval:
  agenda:
    - "Variables and data types"
  search_results:
    - name: "python_basics_overview.txt"
      content: "Short notes used by the writer agent"
```

## Prerequisites

### Running Evaluations

Evaluations require:

1. **MCP Filesystem Server** (automatically started)
2. **OpenAI API Key** (for LLM-as-a-judge and vector store)
3. **Vector Store** (automatically created/found from config)

### Environment Setup

```bash
# Set OpenAI API key
export OPENAI_API_KEY="your-api-key"

# Vector store name is required as CLI parameter:
# - Uses the name from your config (e.g., "agentic_research_data")
# - Looks up existing vector store by name
# - Creates it if it doesn't exist
# - Or use --vector-store-id to override (for testing specific data)
```

## Usage Examples

### Quick Start: Run Evaluation

```bash
# Run baseline evaluation with your vector store name
poetry run baseline-eval \
    --test-case trivial_research \
    --vector-store-name "agentic_research_data" \
    --config configs/config-default.yaml \
    --save-baseline

# Or specify a specific vector store ID for testing with specific data
poetry run baseline-eval \
    --test-case trivial_research \
    --vector-store-name "agentic_research_data" \
    --vector-store-id vs_abc123 \
    --config configs/config-gpt-4.1-mini.yaml \
    --save-baseline
```

**Expected Output:**
```
📋 Loading test case: trivial_research
🚀 Running evaluation...
✅ Validating results...

=== VALIDATION RESULTS ===
Overall: ✅ PASS
  ✅ min_grade_format: B (expected: >= C)
  ✅ min_grade_grounding: B (expected: >= C)
  ✅ min_grade_agenda: A (expected: >= C)
  ✅ min_grade_usability: B (expected: >= C)
  ✅ judgment: PASS (expected: in ['PASS', 'BORDERLINE'])

💾 Saving baseline...
✅ Baseline saved: evaluations/baselines/baseline_trivial_abc123_20260114_153000.json
```

### Regression Testing

```bash
# After making changes, run evaluation again and compare
poetry run baseline-eval \
    --test-case trivial_research \
    --vector-store-name "agentic_research_data" \
    --config configs/config-default.yaml \
    --compare-baseline baseline_trivial_abc123_20260114_153000.json

# Vector store is automatically found/created by name
# Or add --vector-store-id to test with specific data
```

**Expected Output (if no degradation):**
```
📊 Comparing against baseline...

=== BASELINE COMPARISON ===
Baseline: abc123 @ 20260114_153000
Degradation: ✅ NONE
  ✅ grade_format: B → B (no change)
  ✅ grade_grounding: B → B (no change)
  ✅ grade_agenda: A → A (no change)
  ✅ grade_usability: B → B (no change)
  ✅ judgment: PASS → PASS
```

**Expected Output (if degradation detected):**
```
📊 Comparing against baseline...

=== BASELINE COMPARISON ===
Baseline: abc123 @ 20260114_153000
Degradation: ❌ DETECTED
  ✅ grade_format: B → B (no change)
  ❌ grade_grounding: B → D (drop: 2, max allowed: 1)
  ✅ grade_agenda: A → A (no change)
  ✅ grade_usability: B → B (no change)
  ❌ judgment: PASS → BORDERLINE
```

## Creating Custom Test Cases

Create a new YAML file in `test_cases/`:

```yaml
name: "my_custom_test"
description: "Test for specialized research domain"
syllabus: "Your research query here"

expected_outcomes:
  min_sources: 3
  required_sections: ["Raw Notes", "Detailed Agenda", "Report"]
  min_word_count: 500
  topics_covered: ["topic1", "topic2"]

min_grades:
  format: "B"      # Require higher quality
  grounding: "B"
  agenda: "B"
  usability: "B"

baseline:
  max_degradation:
    grade_drop: 1  # Allow max 1 grade level drop
```

Then run:
```bash
poetry run baseline-eval \
    --test-case my_custom_test \
    --vector-store-name "agentic_research_data" \
    --save-baseline
```

## Integration with CI/CD

Add to your CI pipeline:

```yaml
# .github/workflows/evaluation.yml
- name: Run Baseline Evaluation
  run: |
    poetry run baseline-eval \
      --test-case trivial_research \
      --vector-store-name "agentic_research_data" \
      --compare-baseline evaluations/baselines/baseline_main.json
```

Exit code 0 = PASS (no degradation)
Exit code 1 = FAIL (degradation detected)

## Architecture

### Design Principles

1. **Manager-Agnostic** - Evaluate OUTCOMES (report generated), not HOW (which agent, handoff patterns)
2. **Leverage Existing Code** - Extends `write_agent_eval.py` pattern, reuses LLM-as-a-judge
3. **No Custom Tracing** - SDK Runner results contain everything via `result.to_input_list()`
4. **Simpler is Better** - YAML test cases, straightforward validation

### How It Works

```python
# 1. Run workflow
result = await Runner.run(supervisor_agent, syllabus, ...)

# 2. Extract results
report = result.final_output_as(ReportData)
messages = result.to_input_list()  # Contains full execution trace

# 3. Validate trajectory
validation = validate_trajectory_spec(messages, FULL_WORKFLOW_TRAJECTORY_SPEC)

# 4. Evaluate quality
quality = await Runner.run(llm_as_judge_agent, report.markdown_report)

# 5. Compare against baseline
if baseline_exists:
    comparison = compare_against_baseline(results, baseline)
    if comparison["degradation_detected"]:
        sys.exit(1)  # Fail CI
```

## Files

```
evaluations/
├── README.md                      # This file
├── trajectory_specs.py            # Trajectory validation specs
├── full_workflow_evaluator.py    # Full workflow evaluation
├── baseline_runner.py             # Baseline management & regression testing
├── eval_utils.py                  # Validation utilities (existing)
├── prompts.py                     # LLM-as-a-judge prompts (existing)
├── schemas.py                     # Evaluation result schemas (existing)
├── test_cases/
│   └── trivial_research.yaml     # Simple test case for baseline
└── baselines/
    └── baseline_*.json            # Saved baseline results
```

## Troubleshooting

### "Vector store not found"

You need a vector store with content. Create one using the normal workflow:

```bash
# Use dataprep workflow to create and populate vector store
poetry run mcp-dataprep-workflow \
    --syllabus "Python basics" \
    --input-files data/*.md

# This creates a vector store with the name from configs/config-default.yaml
# Then use that same name in evaluation:
poetry run baseline-eval \
    --test-case trivial_research \
    --vector-store-name "agentic_research_data" \
    --save-baseline
```

### "MCP server connection failed"

Ensure MCP servers are accessible. Check configuration in:
- `configs/config-default.yaml` - MCP server settings
- Environment variables for API keys

### "Grade degradation detected"

This is expected if your changes affected quality. Review:
1. What changed in the codebase?
2. Is the degradation acceptable?
3. Should you update the baseline?

To accept new behavior as baseline:
```bash
poetry run baseline-eval \
    --test-case trivial_research \
    --vector-store-name "agentic_research_data" \
    --save-baseline
```

## Next Steps

1. **Run First Baseline** - Execute evaluation and save baseline before migrations
2. **Document MCP Setup** - Add instructions for starting required MCP servers
3. **Add More Test Cases** - Create test cases for different research domains
4. **CI Integration** - Add evaluation to GitHub Actions workflow

## Contributing

When adding evaluation features:

1. **Update Trajectory Specs** - Add new checkpoints to `trajectory_specs.py`
2. **Add Test Cases** - Create YAML files in `test_cases/`
3. **Update Tests** - Add unit tests in `tests/test_trajectory_specs.py`
4. **Document Changes** - Update this README

## Related Documentation

- Issue #8: Functional Evaluation Framework
- `docs/FUNCTIONAL_EVALUATION_PLAN.md` - Implementation plan
- `evaluations/write_agent_eval.py` - Writer-only evaluation (existing pattern)
