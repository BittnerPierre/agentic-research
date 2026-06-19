"""Outline step (D1) — turn the agenda + source index into a structured plan.

This is the one step of the decomposed writer where reasoning helps, so it is a
good fit for a higher ``reasoning_effort`` (set it on ``outline_model`` in the
config). It never loads source content — only the compact ``[S#] topic`` index —
so its context stays small.
"""

from __future__ import annotations

from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

from agents import Agent, Runner

from ..agents.schemas import Chapter, ReportOutline, ResearchInfo, SourceDocument
from ..agents.utils import load_prompt_from_file
from ..config import get_config
from ._model_settings import build_model

prompt_file = "outline_prompt.md"


def create_outline_agent() -> Agent:
    config = get_config()
    model_spec = config.models.outline_model or config.models.writer_model
    model, model_settings = build_model(model_spec)

    prompt = load_prompt_from_file("prompts", prompt_file)
    if prompt is None:
        raise ValueError(f"{prompt_file} is None")
    instructions = prompt.format(RECOMMENDED_PROMPT_PREFIX=RECOMMENDED_PROMPT_PREFIX)

    return Agent(
        name="outline_agent",
        instructions=instructions,
        model=model,
        output_type=ReportOutline,
        model_settings=model_settings,
    )


def _source_index(sources: list[SourceDocument]) -> str:
    return "\n".join(f"- [{s.source_id}] {s.topic}" for s in sources)


def fallback_outline(query: str, sources: list[SourceDocument]) -> ReportOutline:
    """Deterministic single-chapter plan used when the outline agent fails.

    Guarantees the pipeline never hard-fails on a flaky structured-output call:
    one chapter, all sources, the writer figures out the rest.
    """
    title = query.strip().splitlines()[0][:120] if query.strip() else "Report"
    return ReportOutline(
        title=title,
        chapters=[
            Chapter(
                title="Rapport",
                objective=f"Répondre de façon complète à la demande : {title}",
                source_ids=[s.source_id for s in sources],
            )
        ],
    )


async def build_outline(
    query: str,
    agenda: str,
    sources: list[SourceDocument],
    research_info: ResearchInfo,
    usage_sink=None,
) -> ReportOutline:
    """Run the outline agent; fall back to a deterministic plan on any failure."""
    try:
        agent = create_outline_agent()
        user_input = (
            f"Demande utilisateur :\n{query}\n\n"
            f"Agenda proposé :\n{agenda}\n\n"
            f"Sources disponibles (identifiant - sujet) :\n{_source_index(sources)}"
        )
        result = await Runner.run(agent, user_input, context=research_info)
        if usage_sink is not None:
            usage_sink(result, "writing")
        outline = result.final_output_as(ReportOutline)
        if outline.chapters:
            return outline
    except Exception:
        pass
    return fallback_outline(query, sources)
