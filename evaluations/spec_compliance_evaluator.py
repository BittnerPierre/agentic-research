"""
Syllabus-aware spec compliance evaluator.

Combines deterministic checks (format/sections/length/sources) with an optional
LLM judgment fallback for nuanced style/intent alignment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from agents import Agent, Runner

from .schemas import SpecComplianceResult

URL_PATTERN = re.compile(r"https?://[^\s)\]>\"']+")


class LLMSpecJudge(BaseModel):
    score_100: float = Field(ge=0.0, le=100.0)
    reasoning: str
    violations: list[str] = Field(default_factory=list)


@dataclass
class SyllabusConstraints:
    max_words: int | None = None
    max_chars: int | None = None
    min_chapters: int | None = None
    require_faq: bool = False
    require_intro: bool = False
    require_conclusion: bool = False
    require_lexique: bool = False
    restrict_sources: bool = False
    allowed_sources: set[str] | None = None


def _extract_constraints(syllabus: str) -> SyllabusConstraints:
    text = syllabus.lower()
    constraints = SyllabusConstraints(allowed_sources=set(URL_PATTERN.findall(syllabus)))

    words_match = re.search(r"(?:max(?:imum)?|au plus|moins de)\s*(\d+)\s*(?:mots|words)", text)
    chars_match = re.search(
        r"(?:max(?:imum)?|au plus|moins de)\s*(\d+)\s*(?:caract[eè]res|characters)", text
    )
    chap_match = re.search(r"(\d+)\s*(?:chapitres|chapters)", text)

    if words_match:
        constraints.max_words = int(words_match.group(1))
    if chars_match:
        constraints.max_chars = int(chars_match.group(1))
    if chap_match:
        constraints.min_chapters = int(chap_match.group(1))

    constraints.require_faq = any(token in text for token in ["faq", "questions / réponses", "q&a"])
    constraints.require_intro = "introduction" in text
    constraints.require_conclusion = "conclusion" in text
    constraints.require_lexique = any(token in text for token in ["lexique", "glossaire", "glossary"])
    constraints.restrict_sources = (
        any(token in text for token in ["uniquement", "strictement", "exclusivement", "only"])
        and "source" in text
        and bool(constraints.allowed_sources)
    )

    return constraints


def _extract_used_sources(report_markdown: str, raw_notes: str) -> set[str]:
    return set(URL_PATTERN.findall(report_markdown)) | set(URL_PATTERN.findall(raw_notes))


def _check_faq(report_markdown: str) -> bool:
    text = report_markdown.lower()
    q_count = len(re.findall(r"(^|\n)\s*(q(?:uestion)?\s*[:\-])", text))
    a_count = len(re.findall(r"(^|\n)\s*(a(?:nswer|nswer|nswer)?\s*[:\-]|r[eé]ponse\s*[:\-])", text))
    return q_count >= 2 and a_count >= 2


def _count_markdown_sections(report_markdown: str) -> int:
    return len(re.findall(r"(?m)^\s{0,3}#{2,3}\s+", report_markdown))


def _has_heading(report_markdown: str, keyword: str) -> bool:
    pattern = re.compile(rf"(?mi)^\s{{0,3}}#{{1,6}}\s+.*\b{re.escape(keyword)}\b")
    return bool(pattern.search(report_markdown))


def _deterministic_spec_score(
    report_markdown: str,
    raw_notes: str,
    constraints: SyllabusConstraints,
) -> SpecComplianceResult:
    checks: dict[str, bool] = {}
    violations: list[str] = []

    word_count = len(report_markdown.split())
    char_count = len(report_markdown)

    checks["length_words"] = constraints.max_words is None or word_count <= constraints.max_words
    checks["length_chars"] = constraints.max_chars is None or char_count <= constraints.max_chars
    checks["faq_format"] = (not constraints.require_faq) or _check_faq(report_markdown)
    checks["has_intro"] = (not constraints.require_intro) or _has_heading(report_markdown, "introduction")
    checks["has_conclusion"] = (not constraints.require_conclusion) or _has_heading(
        report_markdown, "conclusion"
    )
    checks["has_lexique"] = (not constraints.require_lexique) or any(
        _has_heading(report_markdown, key) for key in ("lexique", "glossaire", "glossary")
    )
    checks["chapters_count"] = (constraints.min_chapters is None) or (
        _count_markdown_sections(report_markdown) >= constraints.min_chapters
    )

    used_sources = _extract_used_sources(report_markdown, raw_notes)
    allowed_sources = constraints.allowed_sources or set()
    unauthorized_sources = sorted(used_sources - allowed_sources) if constraints.restrict_sources else []
    checks["allowed_sources_only"] = not constraints.restrict_sources or not unauthorized_sources

    for check_name, passed in checks.items():
        if not passed:
            violations.append(f"Failed check: {check_name}")
    if unauthorized_sources:
        violations.append(
            "Unauthorized sources used: " + ", ".join(unauthorized_sources[:5])
        )

    passed_checks = sum(1 for passed in checks.values() if passed)
    deterministic_score = 100.0 * passed_checks / max(1, len(checks))

    return SpecComplianceResult(
        score_100=deterministic_score,
        checks=checks,
        violations=violations,
        allowed_sources=sorted(allowed_sources),
        used_sources=sorted(used_sources),
        unauthorized_sources=unauthorized_sources,
        reasoning=(
            f"Deterministic checks passed: {passed_checks}/{len(checks)} "
            f"(words={word_count}, chars={char_count})."
        ),
    )


SPEC_JUDGE_PROMPT = """
You are a strict compliance grader.
Evaluate whether the report complies with the provided syllabus specification.
Focus on:
1) required structure/sections
2) requested format constraints
3) style/tone constraints
4) output adequation to syllabus intent

Return JSON only:
{
  "score_100": <0-100>,
  "reasoning": "<short reasoning>",
  "violations": ["..."]
}
"""


async def evaluate_spec_compliance(
    report_markdown: str,
    syllabus: str,
    raw_notes: str,
) -> SpecComplianceResult:
    constraints = _extract_constraints(syllabus)
    deterministic = _deterministic_spec_score(report_markdown, raw_notes, constraints)

    # Optional LLM adjustment for nuanced style/intent compliance.
    try:
        judge_agent = Agent(
            name="spec_compliance_judge",
            instructions=SPEC_JUDGE_PROMPT,
            model="openai/gpt-4.1-mini",
            output_type=LLMSpecJudge,
        )
        input_text = (
            "===SYLLABUS===\n"
            f"{syllabus}\n\n"
            "===REPORT===\n"
            f"{report_markdown}\n\n"
            "===DETERMINISTIC_CHECKS===\n"
            f"{deterministic.model_dump()}\n"
        )
        llm_result = (await Runner.run(judge_agent, input_text)).final_output_as(LLMSpecJudge)
        blended_score = (0.7 * deterministic.score_100) + (0.3 * llm_result.score_100)
        violations = list(dict.fromkeys(deterministic.violations + llm_result.violations))
        reasoning = (
            f"{deterministic.reasoning} LLM judge score={llm_result.score_100:.1f}. "
            f"{llm_result.reasoning}"
        )
        return deterministic.model_copy(
            update={
                "score_100": min(100.0, max(0.0, blended_score)),
                "violations": violations,
                "reasoning": reasoning,
            }
        )
    except Exception:
        return deterministic
