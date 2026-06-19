"""Chapter drafting step (D2) — write each chapter in parallel.

Each chapter is an independent run with a minimal, dedicated context (its brief
+ the full but compact corpus). This is the core of the spike: splitting the
*generation* into short, bounded calls instead of one long monolithic pass, so
large hybrid models on the Spark cluster stay fast and reliable.

An objective, code-checkable guardrail retries a chapter that comes back empty
or without any [S#] citation. We deliberately do NOT judge subjective quality
(style, tone) — that needs an arbiter and loops forever.
"""

from __future__ import annotations

import asyncio
import re
import time

from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

from agents import Agent, Runner

from ..agents.schemas import Chapter, ReportOutline, ResearchInfo
from ..agents.utils import load_prompt_from_file
from ..config import get_config
from ._model_settings import build_model

prompt_file = "chapter_prompt.md"

_CITATION_RE = re.compile(r"\[S\d+\]")


def create_chapter_writer_agent() -> Agent:
    config = get_config()
    model_spec = config.models.chapter_writer_model or config.models.writer_model
    model, model_settings = build_model(model_spec)

    prompt = load_prompt_from_file("prompts", prompt_file)
    if prompt is None:
        raise ValueError(f"{prompt_file} is None")
    instructions = prompt.format(RECOMMENDED_PROMPT_PREFIX=RECOMMENDED_PROMPT_PREFIX)

    # No output_type: the chapter body is returned as plain markdown text.
    return Agent(
        name="chapter_writer_agent",
        instructions=instructions,
        model=model,
        model_settings=model_settings,
    )


def _chapter_prompt(report_title: str, chapter: Chapter, corpus: str) -> str:
    priorities = (
        ", ".join(chapter.source_ids) if chapter.source_ids else "(libre — choisis dans le corpus)"
    )
    return (
        f"Titre du rapport : {report_title}\n"
        f"Chapitre à rédiger : {chapter.title}\n"
        f"Objectif du chapitre : {chapter.objective}\n"
        f"Sources prioritaires : {priorities}\n\n"
        f"Corpus complet (cite avec [S#]) :\n\n{corpus}"
    )


async def _write_one_chapter(
    agent: Agent,
    report_title: str,
    chapter: Chapter,
    corpus: str,
    research_info: ResearchInfo,
    max_revisions: int,
    require_citation: bool,
    usage_sink=None,
) -> tuple[str, float]:
    """Return the chapter body and its wall-clock duration (for concurrency stats)."""
    base = _chapter_prompt(report_title, chapter, corpus)
    start = time.perf_counter()
    text = ""
    for attempt in range(max_revisions + 1):
        prompt = base
        if attempt > 0:
            prompt += "\n\nRAPPEL : ton texte ne doit pas être vide et doit citer au moins une source au format [S#]."
        result = await Runner.run(agent, prompt, context=research_info)
        if usage_sink is not None:
            usage_sink(result, "writing")
        text = str(result.final_output or "").strip()
        ok = bool(text) and (not require_citation or _CITATION_RE.search(text) is not None)
        if ok:
            break
    return text, time.perf_counter() - start


async def write_chapters(
    outline: ReportOutline,
    corpus: str,
    research_info: ResearchInfo,
    require_citation: bool,
    usage_sink=None,
) -> tuple[list[tuple[Chapter, str]], list[float]]:
    """Draft every chapter concurrently.

    Returns the (chapter, body) pairs in order plus each chapter's wall-clock
    duration. Comparing sum(durations) to the gather wall-clock reveals whether
    the backend actually serves the chapters in parallel (vLLM batching) or
    serializes them (llama.cpp model switching).
    """
    config = get_config()
    max_revisions = config.agents.chapter_max_revisions
    agent = create_chapter_writer_agent()

    tasks = [
        _write_one_chapter(
            agent,
            outline.title,
            chapter,
            corpus,
            research_info,
            max_revisions,
            require_citation,
            usage_sink,
        )
        for chapter in outline.chapters
    ]
    results = await asyncio.gather(*tasks)
    bodies = [text for text, _ in results]
    durations = [duration for _, duration in results]
    return list(zip(outline.chapters, bodies, strict=True)), durations
