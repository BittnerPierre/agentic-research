"""
Trace Analyzer - Extract metrics from benchmark traces

Analyzes structured traces to extract timing, agent calls, and other metrics
without requiring code instrumentation.
"""

import json
from datetime import datetime
from pathlib import Path

from .schemas import AgentCallsResult, TimingResult


class TraceAnalyzer:
    """
    Analyzer that extracts benchmark metrics from structured traces.

    This allows us to measure performance without instrumenting workflow code.
    """

    def __init__(self, trace_file: str):
        """
        Initialize analyzer with a trace file.

        Args:
            trace_file: Path to JSON trace file from BenchmarkTraceProcessor
        """
        self.trace_file = Path(trace_file)
        self.data = self._load_trace()

    def _load_trace(self) -> dict:
        """Load and parse trace JSON file."""
        if not self.trace_file.exists():
            raise FileNotFoundError(f"Trace file not found: {self.trace_file}")

        with open(self.trace_file, encoding="utf-8") as f:
            return json.load(f)

    def extract_timing(self) -> TimingResult:
        """
        Extract timing information from traces.

        Identifies workflow phases by span names and calculates durations.

        Returns:
            TimingResult with total and per-phase timing
        """
        phases = {
            "knowledge_preparation": 0.0,
            "planning": 0.0,
            "search": 0.0,
            "writing": 0.0,
        }

        total_seconds = 0.0

        # Analyze all traces (typically one main workflow trace)
        for trace in self.data.get("traces", []):
            # Calculate total timing from trace start/end
            if trace.get("started_at") and trace.get("ended_at"):
                start = datetime.fromisoformat(trace["started_at"])
                end = datetime.fromisoformat(trace["ended_at"])
                total_seconds = (end - start).total_seconds()

            # Analyze spans to identify phases
            for span in trace.get("spans", []):
                duration = self._calculate_span_duration(span)
                if duration is None:
                    continue

                span_name = span.get("name", "").lower()

                # Match span names to phases
                if "knowledge" in span_name or "preparation" in span_name or "preparing" in span_name:
                    phases["knowledge_preparation"] += duration
                elif "plan" in span_name or "planning" in span_name:
                    phases["planning"] += duration
                elif "search" in span_name or "searching" in span_name:
                    phases["search"] += duration
                elif "writ" in span_name or "report" in span_name:
                    phases["writing"] += duration

        return TimingResult(
            total_seconds=total_seconds,
            phases=phases,
        )

    def extract_agent_calls(self) -> AgentCallsResult:
        """
        Extract agent call statistics from traces.

        Counts agent invocations by analyzing span metadata.

        Returns:
            AgentCallsResult with calls per agent and totals
        """
        agent_calls = {
            "knowledge_preparation_agent": 0,
            "file_planner_agent": 0,
            "file_search_agent": 0,
            "writer_agent": 0,
            "total": 0,
            "failures": 0,
        }

        # Analyze all spans
        for trace in self.data.get("traces", []):
            for span in trace.get("spans", []):
                span_name = span.get("name", "").lower()
                metadata = span.get("metadata", {})

                # Detect agent type from span name or metadata
                agent_type = self._identify_agent_type(span_name, metadata)

                if agent_type:
                    agent_calls[agent_type] += 1
                    agent_calls["total"] += 1

                # Check for failures
                if self._is_failed_span(span, metadata):
                    agent_calls["failures"] += 1

        return AgentCallsResult(**agent_calls)

    def _calculate_span_duration(self, span: dict) -> float | None:
        """Calculate duration of a span in seconds."""
        if not span.get("started_at") or not span.get("ended_at"):
            return None

        try:
            start = datetime.fromisoformat(span["started_at"])
            end = datetime.fromisoformat(span["ended_at"])
            return (end - start).total_seconds()
        except (ValueError, TypeError):
            return None

    def _identify_agent_type(self, span_name: str, metadata: dict) -> str | None:
        """
        Identify agent type from span name or metadata.

        Args:
            span_name: Name of the span (lowercase)
            metadata: Span metadata dict

        Returns:
            Agent type key or None if not an agent call
        """
        # Check metadata first (more reliable)
        agent_name = metadata.get("agent_name", "").lower()
        if agent_name:
            if "knowledge" in agent_name or "preparation" in agent_name:
                return "knowledge_preparation_agent"
            elif "planner" in agent_name or "planning" in agent_name:
                return "file_planner_agent"
            elif "search" in agent_name:
                return "file_search_agent"
            elif "writer" in agent_name:
                return "writer_agent"

        # Fallback to span name analysis
        if "knowledge" in span_name or "preparation" in span_name:
            return "knowledge_preparation_agent"
        elif "planner" in span_name or "planning" in span_name:
            return "file_planner_agent"
        elif "search" in span_name:
            return "file_search_agent"
        elif "writer" in span_name or "report" in span_name:
            return "writer_agent"

        return None

    def _is_failed_span(self, span: dict, metadata: dict) -> bool:
        """Check if a span represents a failed operation."""
        # Check for error indicators in metadata
        if metadata.get("error") or metadata.get("exception"):
            return True

        # Check for None/null end time (incomplete span)
        if span.get("started_at") and not span.get("ended_at"):
            return True

        return False

    def get_summary(self) -> dict:
        """
        Get a complete summary of all metrics.

        Returns:
            Dict with timing and agent_calls data
        """
        return {
            "timing": self.extract_timing().model_dump(),
            "agent_calls": self.extract_agent_calls().model_dump(),
        }


def analyze_trace_file(trace_file: str) -> dict:
    """
    Convenience function to analyze a trace file.

    Args:
        trace_file: Path to trace JSON file

    Returns:
        Dict with timing and agent_calls metrics
    """
    analyzer = TraceAnalyzer(trace_file)
    return analyzer.get_summary()
