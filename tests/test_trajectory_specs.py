"""
Unit Tests for Trajectory Specifications

Validates that trajectory specs are well-formed and cover all agents.
"""

import pytest

from evaluations.trajectory_specs import (
    FULL_WORKFLOW_TRAJECTORY_SPEC,
    RESEARCH_TRAJECTORY_SPEC,
    SUPERVISOR_TRAJECTORY_SPEC,
    WRITER_TRAJECTORY_SPEC,
    get_spec_by_agent_name,
    validate_spec_format,
)


def test_supervisor_trajectory_spec_structure():
    """Test that supervisor spec is well-formed."""
    assert "trajectory_spec" in SUPERVISOR_TRAJECTORY_SPEC
    trajectory = SUPERVISOR_TRAJECTORY_SPEC["trajectory_spec"]
    assert isinstance(trajectory, list)
    assert len(trajectory) > 0

    # Validate format
    validate_spec_format(SUPERVISOR_TRAJECTORY_SPEC)


def test_supervisor_trajectory_spec_checkpoints():
    """Test that supervisor spec has expected checkpoints."""
    trajectory = SUPERVISOR_TRAJECTORY_SPEC["trajectory_spec"]
    checkpoint_ids = [c["id"] for c in trajectory]

    # Expected checkpoints
    assert "plan_search" in checkpoint_ids
    assert "execute_search" in checkpoint_ids
    assert "handoff_to_writer" in checkpoint_ids

    # Verify critical checkpoints are required
    for checkpoint in trajectory:
        if checkpoint["id"] in ["plan_search", "execute_search", "handoff_to_writer"]:
            assert checkpoint["required"] is True
            assert checkpoint["type"] == "function_call"


def test_research_trajectory_spec_structure():
    """Test that research spec is well-formed."""
    assert "trajectory_spec" in RESEARCH_TRAJECTORY_SPEC
    trajectory = RESEARCH_TRAJECTORY_SPEC["trajectory_spec"]
    assert isinstance(trajectory, list)
    assert len(trajectory) > 0

    # Validate format
    validate_spec_format(RESEARCH_TRAJECTORY_SPEC)


def test_research_trajectory_spec_checkpoints():
    """Test that research spec has expected checkpoints."""
    trajectory = RESEARCH_TRAJECTORY_SPEC["trajectory_spec"]
    checkpoint_ids = [c["id"] for c in trajectory]

    # Expected checkpoints
    assert "search_vectorstore" in checkpoint_ids
    assert "output_results" in checkpoint_ids

    # Verify search checkpoint
    search_checkpoint = next(c for c in trajectory if c["id"] == "search_vectorstore")
    assert search_checkpoint["type"] == "function_call"
    assert search_checkpoint["name"] == "vector_search"
    assert search_checkpoint["required"] is True

    # Verify output checkpoint
    output_checkpoint = next(c for c in trajectory if c["id"] == "output_results")
    assert output_checkpoint["type"] == "generation"
    assert "match_regex" in output_checkpoint


def test_writer_trajectory_spec_structure():
    """Test that writer spec is well-formed."""
    assert "trajectory_spec" in WRITER_TRAJECTORY_SPEC
    trajectory = WRITER_TRAJECTORY_SPEC["trajectory_spec"]
    assert isinstance(trajectory, list)
    assert len(trajectory) > 0

    # Validate format
    validate_spec_format(WRITER_TRAJECTORY_SPEC)


def test_writer_trajectory_spec_checkpoints():
    """Test that writer spec has expected checkpoints (from existing code)."""
    trajectory = WRITER_TRAJECTORY_SPEC["trajectory_spec"]
    checkpoint_ids = [c["id"] for c in trajectory]

    # Expected checkpoints (from write_agent_eval.py)
    assert "load_data" in checkpoint_ids
    assert "report_generation_raw_notes" in checkpoint_ids
    assert "report_generation_detailed_agenda" in checkpoint_ids
    assert "report_generation_report" in checkpoint_ids
    assert "save_report" in checkpoint_ids

    # Verify all are required
    for checkpoint in trajectory:
        assert checkpoint["required"] is True


def test_full_workflow_trajectory_spec_structure():
    """Test that full workflow spec is well-formed."""
    assert "trajectory_spec" in FULL_WORKFLOW_TRAJECTORY_SPEC
    trajectory = FULL_WORKFLOW_TRAJECTORY_SPEC["trajectory_spec"]
    assert isinstance(trajectory, list)
    assert len(trajectory) > 0

    # Validate format
    validate_spec_format(FULL_WORKFLOW_TRAJECTORY_SPEC)


def test_full_workflow_trajectory_spec_phases():
    """Test that full workflow spec covers all phases."""
    trajectory = FULL_WORKFLOW_TRAJECTORY_SPEC["trajectory_spec"]
    checkpoint_ids = [c["id"] for c in trajectory]

    # Phase 1: Supervisor
    assert "supervisor_plan_search" in checkpoint_ids
    assert "supervisor_execute_search" in checkpoint_ids

    # Phase 2: Research (validated separately)

    # Phase 3: Writer
    assert "writer_load_data" in checkpoint_ids
    assert "writer_raw_notes" in checkpoint_ids
    assert "writer_agenda" in checkpoint_ids
    assert "writer_report" in checkpoint_ids
    assert "writer_save" in checkpoint_ids


def test_get_spec_by_agent_name():
    """Test helper function for retrieving specs."""
    # Valid agent names
    supervisor_spec = get_spec_by_agent_name("supervisor")
    assert supervisor_spec == SUPERVISOR_TRAJECTORY_SPEC

    research_spec = get_spec_by_agent_name("research")
    assert research_spec == RESEARCH_TRAJECTORY_SPEC

    writer_spec = get_spec_by_agent_name("writer")
    assert writer_spec == WRITER_TRAJECTORY_SPEC

    full_spec = get_spec_by_agent_name("full_workflow")
    assert full_spec == FULL_WORKFLOW_TRAJECTORY_SPEC

    # Invalid agent name
    with pytest.raises(ValueError, match="Unknown agent name"):
        get_spec_by_agent_name("invalid_agent")


def test_validate_spec_format_valid():
    """Test that validation passes for valid specs."""
    # All existing specs should be valid
    validate_spec_format(SUPERVISOR_TRAJECTORY_SPEC)
    validate_spec_format(RESEARCH_TRAJECTORY_SPEC)
    validate_spec_format(WRITER_TRAJECTORY_SPEC)
    validate_spec_format(FULL_WORKFLOW_TRAJECTORY_SPEC)


def test_validate_spec_format_missing_key():
    """Test that validation fails for missing trajectory_spec key."""
    invalid_spec = {"some_other_key": []}
    with pytest.raises(ValueError, match="missing 'trajectory_spec' key"):
        validate_spec_format(invalid_spec)


def test_validate_spec_format_not_list():
    """Test that validation fails if trajectory_spec is not a list."""
    invalid_spec = {"trajectory_spec": "not_a_list"}
    with pytest.raises(ValueError, match="must be a list"):
        validate_spec_format(invalid_spec)


def test_validate_spec_format_missing_id():
    """Test that validation fails for checkpoint missing id."""
    invalid_spec = {"trajectory_spec": [{"type": "function_call", "name": "test"}]}
    with pytest.raises(ValueError, match="missing 'id'"):
        validate_spec_format(invalid_spec)


def test_validate_spec_format_missing_type():
    """Test that validation fails for checkpoint missing type."""
    invalid_spec = {"trajectory_spec": [{"id": "test", "name": "test"}]}
    with pytest.raises(ValueError, match="missing 'type'"):
        validate_spec_format(invalid_spec)


def test_validate_spec_format_invalid_type():
    """Test that validation fails for invalid checkpoint type."""
    invalid_spec = {"trajectory_spec": [{"id": "test", "type": "invalid_type"}]}
    with pytest.raises(ValueError, match="invalid type"):
        validate_spec_format(invalid_spec)


def test_validate_spec_format_function_call_missing_name():
    """Test that validation fails for function_call missing name."""
    invalid_spec = {"trajectory_spec": [{"id": "test", "type": "function_call"}]}
    with pytest.raises(ValueError, match="missing 'name'"):
        validate_spec_format(invalid_spec)


def test_validate_spec_format_generation_missing_regex():
    """Test that validation fails for generation missing match_regex."""
    invalid_spec = {"trajectory_spec": [{"id": "test", "type": "generation"}]}
    with pytest.raises(ValueError, match="missing 'match_regex'"):
        validate_spec_format(invalid_spec)


def test_checkpoint_ordering():
    """Test that checkpoints are in logical execution order."""
    # Supervisor: plan → execute → handoff
    supervisor_ids = [c["id"] for c in SUPERVISOR_TRAJECTORY_SPEC["trajectory_spec"]]
    assert supervisor_ids.index("plan_search") < supervisor_ids.index("execute_search")
    assert supervisor_ids.index("execute_search") < supervisor_ids.index("handoff_to_writer")

    # Writer: load → raw notes → agenda → report → save
    writer_ids = [c["id"] for c in WRITER_TRAJECTORY_SPEC["trajectory_spec"]]
    assert writer_ids.index("load_data") < writer_ids.index("report_generation_raw_notes")
    assert writer_ids.index("report_generation_raw_notes") < writer_ids.index(
        "report_generation_detailed_agenda"
    )
    assert writer_ids.index("report_generation_detailed_agenda") < writer_ids.index(
        "report_generation_report"
    )
    assert writer_ids.index("report_generation_report") < writer_ids.index("save_report")

    # Full workflow: supervisor → writer
    full_ids = [c["id"] for c in FULL_WORKFLOW_TRAJECTORY_SPEC["trajectory_spec"]]
    assert full_ids.index("supervisor_plan_search") < full_ids.index("writer_load_data")
    assert full_ids.index("writer_load_data") < full_ids.index("writer_save")


def test_all_checkpoints_have_descriptions():
    """Test that all checkpoints have human-readable descriptions."""
    all_specs = [
        SUPERVISOR_TRAJECTORY_SPEC,
        RESEARCH_TRAJECTORY_SPEC,
        WRITER_TRAJECTORY_SPEC,
        FULL_WORKFLOW_TRAJECTORY_SPEC,
    ]

    for spec in all_specs:
        for checkpoint in spec["trajectory_spec"]:
            assert "description" in checkpoint, f"Checkpoint {checkpoint['id']} missing description"
            assert (
                len(checkpoint["description"]) > 0
            ), f"Checkpoint {checkpoint['id']} has empty description"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
