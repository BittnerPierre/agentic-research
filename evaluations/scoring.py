"""Scoring helpers for benchmark ranking."""

from __future__ import annotations

from .schemas import EvaluationResult, ScoreBreakdown, SpecComplianceResult

GRADE_TO_SCORE = {
    "A": 100.0,
    "B": 85.0,
    "C": 70.0,
    "D": 50.0,
    "E": 30.0,
}


def quality_score_100(quality_result: EvaluationResult) -> float:
    grades = quality_result.grades
    weighted = (
        GRADE_TO_SCORE[grades.grounding] * 0.40
        + GRADE_TO_SCORE[grades.agenda] * 0.25
        + GRADE_TO_SCORE[grades.format] * 0.20
        + GRADE_TO_SCORE[grades.usability] * 0.15
    )
    return round(weighted, 2)


def efficiency_score_100(timing: dict, agent_calls: dict) -> float:
    total_seconds = float(timing.get("total_seconds", 0.0))
    failures = int(agent_calls.get("failures", 0))
    total_calls = int(agent_calls.get("total", 0))
    tool_calls = int(agent_calls.get("tool_calls_total", 0))

    duration_penalty = min(40.0, total_seconds / 3.0)
    failure_penalty = min(40.0, failures * 15.0)
    call_penalty = min(10.0, max(0, total_calls - 6) * 2.0)
    tool_penalty = min(10.0, max(0, tool_calls - 12) * 1.0)

    score = 100.0 - duration_penalty - failure_penalty - call_penalty - tool_penalty
    return round(max(0.0, score), 2)


def build_analysis(
    spec: float,
    quality: float,
    rag: float,
    efficiency: float,
    rag_context_relevance: float | None,
    unauthorized_sources: list[str],
) -> str:
    strengths = []
    weaknesses = []

    if spec >= 80:
        strengths.append("Good syllabus compliance")
    else:
        weaknesses.append("Syllabus compliance is weak")

    if quality >= 80:
        strengths.append("Report quality is strong")
    else:
        weaknesses.append("Report quality needs improvement")

    if rag >= 80:
        strengths.append("RAG relevance/grounding is strong")
    else:
        weaknesses.append("RAG relevance/grounding is limited")
    if rag_context_relevance is not None and rag_context_relevance < 0.6:
        weaknesses.append("Retrieved context relevance is weak")

    if efficiency >= 80:
        strengths.append("Execution efficiency is good")
    else:
        weaknesses.append("Execution efficiency is low")

    if unauthorized_sources:
        weaknesses.append("Unauthorized sources detected")

    strengths_text = ", ".join(strengths) if strengths else "No major strengths detected"
    weaknesses_text = ", ".join(weaknesses) if weaknesses else "No major weaknesses detected"
    return f"Good: {strengths_text}. Needs work: {weaknesses_text}."


def compute_score_breakdown(
    spec_result: SpecComplianceResult,
    quality_result: EvaluationResult,
    rag_triad_average: float,
    rag_context_relevance: float | None,
    timing: dict,
    agent_calls: dict,
) -> ScoreBreakdown:
    spec = round(spec_result.score_100, 2)
    quality = quality_score_100(quality_result)
    rag = round(max(0.0, min(100.0, rag_triad_average * 100.0)), 2)
    efficiency = efficiency_score_100(timing, agent_calls)
    overall = round((0.40 * spec) + (0.30 * quality) + (0.20 * rag) + (0.10 * efficiency), 2)

    # Guardrail: if retrieval context is weak, block misleadingly high global scores.
    if rag_context_relevance is not None:
        if rag_context_relevance < 0.4:
            quality = min(quality, 75.0)
            overall = min(overall, 69.0)
        elif rag_context_relevance < 0.6:
            quality = min(quality, 85.0)
            overall = min(overall, 79.0)

    return ScoreBreakdown(
        spec_compliance_100=spec,
        content_quality_100=quality,
        rag_compliance_100=rag,
        efficiency_100=efficiency,
        overall_100=overall,
        analysis=build_analysis(
            spec,
            quality,
            rag,
            efficiency,
            rag_context_relevance,
            spec_result.unauthorized_sources,
        ),
    )
