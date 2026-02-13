import pytest

from evaluations.schemas import EvaluationResult, Grades, SpecComplianceResult
from evaluations.scoring import compute_score_breakdown, efficiency_score_100, quality_score_100
from evaluations.spec_compliance_evaluator import evaluate_spec_compliance


def test_quality_score_100_weighted_mapping():
    result = EvaluationResult(
        judgment="PASS",
        grades=Grades(format="A", grounding="B", agenda="A", usability="C"),
        reasoning="ok",
    )
    score = quality_score_100(result)
    assert score == 89.5


def test_efficiency_score_100_penalizes_duration_and_failures():
    score_fast = efficiency_score_100({"total_seconds": 30.0}, {"total": 5, "failures": 0})
    score_slow_fail = efficiency_score_100(
        {"total_seconds": 180.0},
        {"total": 10, "tool_calls_total": 20, "failures": 2},
    )
    assert score_fast > score_slow_fail


def test_compute_score_breakdown_combines_components():
    spec = SpecComplianceResult(score_100=80.0)
    quality = EvaluationResult(
        judgment="PASS",
        grades=Grades(format="A", grounding="A", agenda="B", usability="B"),
        reasoning="ok",
    )
    breakdown = compute_score_breakdown(
        spec_result=spec,
        quality_result=quality,
        rag_triad_average=0.9,
        rag_context_relevance=0.9,
        timing={"total_seconds": 40.0},
        agent_calls={"total": 5, "tool_calls_total": 8, "failures": 0},
    )
    assert 0 <= breakdown.overall_100 <= 100
    assert breakdown.rag_compliance_100 == 90.0


def test_compute_score_breakdown_caps_when_context_relevance_is_weak():
    spec = SpecComplianceResult(score_100=98.0)
    quality = EvaluationResult(
        judgment="PASS",
        grades=Grades(format="A", grounding="A", agenda="A", usability="A"),
        reasoning="ok",
    )
    breakdown = compute_score_breakdown(
        spec_result=spec,
        quality_result=quality,
        rag_triad_average=0.85,
        rag_context_relevance=0.5,
        timing={"total_seconds": 35.0},
        agent_calls={"total": 6, "tool_calls_total": 6, "failures": 0},
    )
    assert breakdown.content_quality_100 <= 85.0
    assert breakdown.overall_100 <= 79.0


@pytest.mark.asyncio
async def test_spec_compliance_deterministic_checks_without_llm():
    syllabus = """
    Rédige un rapport au format FAQ.
    Maximum 60 mots.
    Inclure Introduction, Conclusion et Lexique.
    Utiliser uniquement ces sources:
    https://example.com/a
    """
    report = """
## Introduction
Q: Sujet?
A: Réponse courte.
## Conclusion
Q: Synthèse?
A: Fin.
## Lexique
- terme: definition
Source: https://example.com/a
"""
    raw_notes = "https://example.com/a"
    result = await evaluate_spec_compliance(report, syllabus, raw_notes)
    assert result.checks["faq_format"] is True
    assert result.checks["allowed_sources_only"] is True
    assert result.score_100 >= 70.0
