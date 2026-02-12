"""
RAG Triad Evaluator - Evaluate Groundedness, Context Relevance, Answer Relevance

Uses LLM-as-a-judge to evaluate the quality of RAG (Retrieval-Augmented Generation)
along three critical dimensions.
"""

from agents import Agent, Runner
from pydantic import BaseModel, Field

from .schemas import RAGTriadResult


class RAGScore(BaseModel):
    """Score for a single RAG dimension."""

    score: float = Field(ge=0.0, le=1.0, description="Score from 0.0 to 1.0")
    reasoning: str = Field(description="Explanation for the score")


# ========== Prompts ==========

GROUNDEDNESS_PROMPT = """You are evaluating the GROUNDEDNESS of a research report.

Groundedness measures whether the report's claims are well-supported by the Raw Notes (source material).

**Task**: Evaluate how well the report is grounded in the provided Raw Notes.

**Scoring Guide**:
- **0.9-1.0**: Excellent - All key claims directly supported, proper citations, no hallucinations
- **0.7-0.8**: Good - Most claims supported, minor unsupported details
- **0.5-0.6**: Fair - Some claims supported, noticeable gaps or weak connections
- **0.3-0.4**: Poor - Many unsupported claims, significant hallucinations
- **0.0-0.2**: Very Poor - Little to no grounding, mostly hallucinated content

**Evaluation Criteria**:
1. Are claims backed by specific evidence from Raw Notes?
2. Are there hallucinations or unsupported assertions?
3. Does the report cite or reference sources appropriately?
4. Is the synthesis faithful to the source material?

**Input Format**:
```
===RAW NOTES===
[Raw notes from sources]

===REPORT===
[Generated report]
```

**Output**: Return a score (0.0-1.0) and reasoning.
"""

CONTEXT_RELEVANCE_PROMPT = """You are evaluating the CONTEXT RELEVANCE of retrieved sources.

Context Relevance measures whether the sources retrieved (Raw Notes) are relevant and useful for answering the research query.

**Task**: Evaluate how relevant the Raw Notes are to the research query.

**Scoring Guide**:
- **0.9-1.0**: Excellent - Highly relevant sources, comprehensive coverage
- **0.7-0.8**: Good - Mostly relevant, minor gaps in coverage
- **0.5-0.6**: Fair - Partially relevant, noticeable irrelevant content
- **0.3-0.4**: Poor - Mostly irrelevant sources
- **0.0-0.2**: Very Poor - Completely irrelevant sources

**Evaluation Criteria**:
1. Do the sources address the research query directly?
2. Is there sufficient coverage of the query topics?
3. Are sources focused or do they contain significant off-topic content?
4. Could better sources have been retrieved?

**Input Format**:
```
===QUERY===
[Research query]

===RAW NOTES===
[Raw notes from retrieved sources]
```

**Output**: Return a score (0.0-1.0) and reasoning.
"""

ANSWER_RELEVANCE_PROMPT = """You are evaluating the ANSWER RELEVANCE of a research report.

Answer Relevance measures whether the report actually answers the research query and addresses what was asked.

**Task**: Evaluate how well the report answers the research query.

**Scoring Guide**:
- **0.9-1.0**: Excellent - Directly answers all aspects of the query
- **0.7-0.8**: Good - Answers most aspects, minor gaps
- **0.5-0.6**: Fair - Partially answers, significant omissions
- **0.3-0.4**: Poor - Barely addresses the query
- **0.0-0.2**: Very Poor - Completely off-topic

**Evaluation Criteria**:
1. Does the report directly address the research query?
2. Are all key aspects of the query covered?
3. Is the report focused or does it diverge off-topic?
4. Does the structure align with the query's intent?

**Input Format**:
```
===QUERY===
[Research query]

===REPORT===
[Generated report]
```

**Output**: Return a score (0.0-1.0) and reasoning.
"""


# ========== Evaluator Functions ==========


async def evaluate_groundedness(
    report_markdown: str,
    raw_notes: str,
) -> RAGScore:
    """
    Evaluate groundedness: Is the report grounded in the Raw Notes?

    Args:
        report_markdown: The generated report
        raw_notes: The raw notes from sources

    Returns:
        RAGScore with score (0-1) and reasoning
    """
    judge_agent = Agent(
        name="groundedness_judge",
        instructions=GROUNDEDNESS_PROMPT,
        model="openai/gpt-4.1-mini",
        output_type=RAGScore,
    )

    input_text = f"""===RAW NOTES===
{raw_notes}

===REPORT===
{report_markdown}
"""

    result = await Runner.run(judge_agent, input_text)
    return result.final_output_as(RAGScore)


async def evaluate_context_relevance(
    raw_notes: str,
    query: str,
) -> RAGScore:
    """
    Evaluate context relevance: Are the retrieved sources relevant?

    Args:
        raw_notes: The raw notes from retrieved sources
        query: The original research query

    Returns:
        RAGScore with score (0-1) and reasoning
    """
    judge_agent = Agent(
        name="context_relevance_judge",
        instructions=CONTEXT_RELEVANCE_PROMPT,
        model="openai/gpt-4.1-mini",
        output_type=RAGScore,
    )

    input_text = f"""===QUERY===
{query}

===RAW NOTES===
{raw_notes}
"""

    result = await Runner.run(judge_agent, input_text)
    return result.final_output_as(RAGScore)


async def evaluate_answer_relevance(
    report_markdown: str,
    query: str,
) -> RAGScore:
    """
    Evaluate answer relevance: Does the report answer the query?

    Args:
        report_markdown: The generated report
        query: The original research query

    Returns:
        RAGScore with score (0-1) and reasoning
    """
    judge_agent = Agent(
        name="answer_relevance_judge",
        instructions=ANSWER_RELEVANCE_PROMPT,
        model="openai/gpt-4.1-mini",
        output_type=RAGScore,
    )

    input_text = f"""===QUERY===
{query}

===REPORT===
{report_markdown}
"""

    result = await Runner.run(judge_agent, input_text)
    return result.final_output_as(RAGScore)


async def evaluate_rag_triad(
    report_markdown: str,
    raw_notes: str,
    query: str,
) -> RAGTriadResult:
    """
    Evaluate all three RAG Triad dimensions.

    Args:
        report_markdown: The generated report
        raw_notes: The raw notes from sources
        query: The original research query

    Returns:
        RAGTriadResult with scores for all 3 dimensions
    """
    # Evaluate all 3 dimensions
    groundedness = await evaluate_groundedness(report_markdown, raw_notes)
    context_relevance = await evaluate_context_relevance(raw_notes, query)
    answer_relevance = await evaluate_answer_relevance(report_markdown, query)

    # Calculate average
    average = (
        groundedness.score + context_relevance.score + answer_relevance.score
    ) / 3.0

    return RAGTriadResult(
        groundedness=groundedness.score,
        context_relevance=context_relevance.score,
        answer_relevance=answer_relevance.score,
        average=average,
        reasoning={
            "groundedness": groundedness.reasoning,
            "context_relevance": context_relevance.reasoning,
            "answer_relevance": answer_relevance.reasoning,
        },
    )


def extract_raw_notes_from_report(report_markdown: str) -> str:
    """
    Extract the Raw Notes section from a report.

    The report format includes a "## Raw Notes" section with source material.

    Args:
        report_markdown: The full report markdown

    Returns:
        The Raw Notes section content, or empty string if not found
    """
    import re

    # Try to extract Raw Notes section
    match = re.search(
        r"##\s*Raw\s*Notes\s*\n(.*?)(?=\n##|\Z)", report_markdown, re.DOTALL | re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    # Fallback: look for any section with "notes" in the title
    match = re.search(r"##\s*.*Notes.*\n(.*?)(?=\n##|\Z)", report_markdown, re.DOTALL)

    if match:
        return match.group(1).strip()

    return ""
