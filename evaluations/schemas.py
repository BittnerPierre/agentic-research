from typing import Literal

from pydantic import BaseModel, Field

Judgment = Literal["PASS", "FAIL", "BORDERLINE"]
Grade = Literal["A", "B", "C", "D", "E"]


class Grades(BaseModel):
    format: Grade = Field(description="Format correctness: A-E")
    grounding: Grade = Field(description="Grounding in Raw Notes: A-E")
    agenda: Grade = Field(description="Agenda adherence: A-E")
    usability: Grade = Field(description="Output usability: A-E")


class EvaluationResult(BaseModel):
    judgment: Judgment = Field(description='Overall decision: "PASS" | "FAIL" | "BORDERLINE"')
    grades: Grades
    reasoning: str = Field(description="4-6 sentence summary of the evaluation")
    missing_raw_notes: list[str] = Field(
        default_factory=list, description="Unused key concepts from Raw Notes"
    )
    missing_agenda_items: list[str] = Field(
        default_factory=list, description="Agenda items not covered or weakly covered"
    )
    off_topic_signals: list[str] = Field(
        default_factory=list, description="Detected signals indicating non-research format"
    )

    # Optionnel : applique la règle métier pour proposer un jugement
    def compute_judgment(self) -> Judgment:
        """
        Business rule:
        - PASS if majority of grades are A/B and no hard fail.
        - FAIL if 2 or more grades are D/E.
        - Otherwise BORDERLINE.
        """
        g = [self.grades.format, self.grades.grounding, self.grades.agenda, self.grades.usability]
        de_count = sum(1 for x in g if x in ("D", "E"))
        ab_count = sum(1 for x in g if x in ("A", "B"))
        if de_count >= 2:
            return "FAIL"
        if ab_count >= 3:
            return "PASS"
        return "BORDERLINE"

    def __str__(self) -> str:
        return f"EvaluationResult(judgment={self.judgment}, reasoning={self.reasoning[:50]}...)"


# ========== Benchmark Schemas ==========


class RAGTriadResult(BaseModel):
    """RAG Triad evaluation scores (0-1 for each dimension)."""

    groundedness: float = Field(ge=0.0, le=1.0, description="Report grounded in Raw Notes")
    context_relevance: float = Field(ge=0.0, le=1.0, description="Sources are relevant")
    answer_relevance: float = Field(ge=0.0, le=1.0, description="Report answers the question")
    average: float = Field(ge=0.0, le=1.0, description="Average of the 3 scores")
    reasoning: dict[str, str] = Field(
        default_factory=dict, description="Reasoning for each dimension"
    )


class TimingResult(BaseModel):
    """Timing information for workflow phases."""

    total_seconds: float = Field(description="Total workflow duration in seconds")
    phases: dict[str, float] = Field(
        description="Duration of each phase (knowledge_preparation, planning, search, writing)"
    )


class AgentCallsResult(BaseModel):
    """Agent call statistics."""

    knowledge_preparation_agent: int = Field(default=0)
    file_planner_agent: int = Field(default=0)
    file_search_agent: int = Field(default=0)
    writer_agent: int = Field(default=0)
    total: int = Field(default=0, description="Total number of agent calls")
    tool_calls_total: int = Field(default=0, description="Total number of tool/function calls")
    failures: int = Field(default=0, description="Number of failed calls")


class TokensResult(BaseModel):
    """Token usage statistics (optional)."""

    requests: int | None = Field(default=None, description="Total requests")
    input_tokens: int | None = Field(default=None, description="Total input tokens")
    output_tokens: int | None = Field(default=None, description="Total output tokens")
    total_tokens: int | None = Field(default=None, description="Total tokens (input + output)")
    cached_tokens: int | None = Field(default=None, description="Cached tokens (if available)")
    reasoning_tokens: int | None = Field(
        default=None, description="Reasoning tokens (if available)"
    )


class SetupMetadata(BaseModel):
    """Metadata about the model setup used for benchmark."""

    setup_name: str = Field(description="Setup name (ministral, glm, etc.)")
    models_env_file: str = Field(description="Models env file used (models.ministral.env)")
    models: dict[str, dict] = Field(
        description="Model configurations (instruct, reasoning, embeddings)"
    )


class BenchmarkResult(BaseModel):
    """Complete benchmark result with all metrics."""

    # Existing metrics
    quality_result: EvaluationResult
    trajectory_report: str
    report_path: str

    # New benchmark metrics
    timing: TimingResult
    rag_triad: RAGTriadResult
    agent_calls: AgentCallsResult
    tokens: TokensResult | None = None
    setup_metadata: SetupMetadata

    # Additional context
    test_case: str | None = None
    config_file: str = "configs/config-docker-dgx.yaml"
    config_name: str | None = None
    trace_id: str | None = None


class SpecComplianceResult(BaseModel):
    """Compliance result against syllabus constraints."""

    score_100: float = Field(ge=0.0, le=100.0)
    checks: dict[str, bool] = Field(default_factory=dict)
    violations: list[str] = Field(default_factory=list)
    allowed_sources: list[str] = Field(default_factory=list)
    used_sources: list[str] = Field(default_factory=list)
    unauthorized_sources: list[str] = Field(default_factory=list)
    reasoning: str = ""


class ScoreBreakdown(BaseModel):
    """Normalized benchmark scores for ranking."""

    spec_compliance_100: float = Field(ge=0.0, le=100.0)
    content_quality_100: float = Field(ge=0.0, le=100.0)
    rag_compliance_100: float = Field(ge=0.0, le=100.0)
    efficiency_100: float = Field(ge=0.0, le=100.0)
    overall_100: float = Field(ge=0.0, le=100.0)
    analysis: str = ""
