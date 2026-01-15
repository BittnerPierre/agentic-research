"""
Trajectory Specifications for Evaluation

Defines expected execution trajectories for all agents in the research workflow.
Used with `validate_trajectory_spec()` from `eval_utils.py`.

Each spec contains a list of checkpoints that validate:
- Function calls executed (type: "function_call")
- Content generated (type: "generation" with regex matching)

Specs are manager-agnostic: validate OUTCOMES, not HOW (internal execution).
"""

# ============================================================================
# SUPERVISOR TRAJECTORY SPEC
# ============================================================================

SUPERVISOR_TRAJECTORY_SPEC = {
    "trajectory_spec": [
        {
            "id": "plan_search",
            "type": "function_call",
            "name": "plan_file_search",
            "required": True,
            "description": "Supervisor plans the file search strategy"
        },
        {
            "id": "execute_search",
            "type": "function_call",
            "name": "file_search",
            "required": True,
            "description": "Supervisor executes file search (may occur multiple times)"
        },
        {
            "id": "display_agenda",
            "type": "function_call",
            "name": "display_agenda",
            "required": False,
            "description": "Supervisor displays research agenda (optional)"
        },
        {
            "id": "handoff_to_writer",
            "type": "function_call",
            "name": "write_report",
            "required": True,
            "description": "Supervisor hands off to writer agent"
        }
    ]
}

# ============================================================================
# RESEARCH AGENT TRAJECTORY SPEC
# ============================================================================

RESEARCH_TRAJECTORY_SPEC = {
    "trajectory_spec": [
        {
            "id": "search_vectorstore",
            "type": "function_call",
            "name": "file_search",  # FileSearchTool
            "required": True,
            "description": "Research agent searches vector store"
        },
        {
            "id": "output_results",
            "type": "generation",
            "match_regex": r"file_name",  # FileSearchResult output
            "expected_content": "file_name",
            "required": True,
            "description": "Research agent outputs FileSearchResult with file_name"
        }
    ]
}

# ============================================================================
# WRITER AGENT TRAJECTORY SPEC
# ============================================================================

# Imported from existing write_agent_eval.py
WRITER_TRAJECTORY_SPEC = {
    "trajectory_spec": [
        {
            "id": "load_data",
            "type": "function_call",
            "name": "read_multiple_files",
            "required": True,
            "description": "Writer loads search results from files"
        },
        {
            "id": "report_generation_raw_notes",
            "type": "generation",
            "match_regex": r"## Raw Notes",
            "expected_content": "## Raw Notes",
            "required": True,
            "description": "Writer generates Raw Notes section"
        },
        {
            "id": "report_generation_detailed_agenda",
            "type": "generation",
            "match_regex": r"## Detailed Agenda",
            "expected_content": "## Detailed Agenda",
            "required": True,
            "description": "Writer generates Detailed Agenda section"
        },
        {
            "id": "report_generation_report",
            "type": "generation",
            "match_regex": r"## Report",
            "expected_content": "## Report",
            "required": True,
            "description": "Writer generates final Report section"
        },
        {
            "id": "save_report",
            "type": "function_call",
            "name": "save_report",
            "required": True,
            "description": "Writer saves report to file"
        }
    ]
}

# ============================================================================
# FULL WORKFLOW TRAJECTORY SPEC
# ============================================================================

# Combined spec for end-to-end validation
# Validates entire research workflow from start to finish
FULL_WORKFLOW_TRAJECTORY_SPEC = {
    "trajectory_spec": [
        # Phase 1: Supervisor plans and coordinates
        {
            "id": "supervisor_plan_search",
            "type": "function_call",
            "name": "plan_file_search",
            "required": True,
            "description": "Supervisor plans research strategy"
        },
        {
            "id": "supervisor_execute_search",
            "type": "function_call",
            "name": "file_search",
            "required": True,
            "description": "Supervisor coordinates file search"
        },
        # Phase 2: Research agent(s) search
        # Note: Research agent execution is internal, validated separately

        # Phase 3: Writer generates report
        {
            "id": "writer_load_data",
            "type": "function_call",
            "name": "read_multiple_files",
            "required": True,
            "description": "Writer loads search results"
        },
        {
            "id": "writer_raw_notes",
            "type": "generation",
            "match_regex": r"## Raw Notes",
            "expected_content": "## Raw Notes",
            "required": True,
            "description": "Writer generates Raw Notes"
        },
        {
            "id": "writer_agenda",
            "type": "generation",
            "match_regex": r"## Detailed Agenda",
            "expected_content": "## Detailed Agenda",
            "required": True,
            "description": "Writer generates Agenda"
        },
        {
            "id": "writer_report",
            "type": "generation",
            "match_regex": r"## Report",
            "expected_content": "## Report",
            "required": True,
            "description": "Writer generates final Report"
        },
        {
            "id": "writer_save",
            "type": "function_call",
            "name": "save_report",
            "required": True,
            "description": "Writer saves final report"
        }
    ]
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_spec_by_agent_name(agent_name: str) -> dict:
    """
    Get trajectory spec by agent name.

    Args:
        agent_name: Name of agent (supervisor, research, writer, full_workflow)

    Returns:
        Trajectory spec dictionary

    Raises:
        ValueError: If agent_name not recognized
    """
    specs = {
        "supervisor": SUPERVISOR_TRAJECTORY_SPEC,
        "research": RESEARCH_TRAJECTORY_SPEC,
        "writer": WRITER_TRAJECTORY_SPEC,
        "full_workflow": FULL_WORKFLOW_TRAJECTORY_SPEC,
    }

    if agent_name not in specs:
        raise ValueError(
            f"Unknown agent name: {agent_name}. "
            f"Valid options: {list(specs.keys())}"
        )

    return specs[agent_name]


def validate_spec_format(spec: dict) -> bool:
    """
    Validate that a trajectory spec is well-formed.

    Args:
        spec: Trajectory spec to validate

    Returns:
        True if valid

    Raises:
        ValueError: If spec is malformed
    """
    if "trajectory_spec" not in spec:
        raise ValueError("Spec missing 'trajectory_spec' key")

    trajectory = spec["trajectory_spec"]
    if not isinstance(trajectory, list):
        raise ValueError("'trajectory_spec' must be a list")

    for i, checkpoint in enumerate(trajectory):
        if not isinstance(checkpoint, dict):
            raise ValueError(f"Checkpoint {i} must be a dict")

        if "id" not in checkpoint:
            raise ValueError(f"Checkpoint {i} missing 'id'")

        if "type" not in checkpoint:
            raise ValueError(f"Checkpoint {i} missing 'type'")

        if checkpoint["type"] not in ["function_call", "generation"]:
            raise ValueError(
                f"Checkpoint {i} has invalid type: {checkpoint['type']}. "
                "Must be 'function_call' or 'generation'"
            )

        if checkpoint["type"] == "function_call" and "name" not in checkpoint:
            raise ValueError(f"Function call checkpoint {i} missing 'name'")

        if checkpoint["type"] == "generation" and "match_regex" not in checkpoint:
            raise ValueError(f"Generation checkpoint {i} missing 'match_regex'")

    return True


# Validate all specs on import
for spec_name, spec in [
    ("SUPERVISOR_TRAJECTORY_SPEC", SUPERVISOR_TRAJECTORY_SPEC),
    ("RESEARCH_TRAJECTORY_SPEC", RESEARCH_TRAJECTORY_SPEC),
    ("WRITER_TRAJECTORY_SPEC", WRITER_TRAJECTORY_SPEC),
    ("FULL_WORKFLOW_TRAJECTORY_SPEC", FULL_WORKFLOW_TRAJECTORY_SPEC),
]:
    try:
        validate_spec_format(spec)
    except ValueError as e:
        raise ValueError(f"Invalid {spec_name}: {e}")
