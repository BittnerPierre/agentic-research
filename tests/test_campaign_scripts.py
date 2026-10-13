import subprocess

from evaluations.campaign.scripts import regrade
from evaluations.campaign.scripts.compile_table import has_authoritative_conceptual_dimensions
from evaluations.campaign.scripts.regrade import exercise_kind


def test_conceptual_table_requires_semantic_authority_and_both_dimensions() -> None:
    dimensions = {
        "notions": {"hit": 12, "total": 14},
        "evidence_discipline": {"hit": 1, "total": 2},
    }

    assert has_authoritative_conceptual_dimensions(
        {
            "score_authority": "llm_categorical_requirement_coverage",
            "conceptual_dimensions": dimensions,
        }
    )
    assert not has_authoritative_conceptual_dimensions(
        {"score_authority": "lexical_diagnostic", "conceptual_dimensions": dimensions}
    )
    assert not has_authoritative_conceptual_dimensions(
        {"score_authority": "llm_categorical_requirement_coverage"}
    )


def test_regrade_kind_routing_matches_grader_routing() -> None:
    assert exercise_kind("camp-model-concept-1") == "concept"
    assert exercise_kind("bench-cal54m-1") == "capex"


def test_forged_control_disables_semantic_judge_instead_of_reusing_an_archive(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="fabrication (ZERO TOL): 3\n")

    monkeypatch.setattr(regrade, "run", fake_run)

    assert regrade.check_control()
    assert commands == [
        [
            "uv",
            "run",
            "python",
            "-m",
            "evaluations.deterministic_grade",
            "evaluations/controls/host_run",
            "--exercise",
            "evaluations/exercises/ai-capex-intensity",
            "--report",
            "evaluations/controls/fabricated_report.md",
            "--disable-semantic-judge",
        ]
    ]
