"""
Benchmark Trace Processor - Capture traces for benchmark analysis

Extends the tracing system to capture structured traces that can be analyzed
for timing, agent calls, and other metrics without modifying workflow code.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agents import Span, Trace, TracingProcessor


class BenchmarkTraceProcessor(TracingProcessor):
    """
    Trace processor that captures structured traces for benchmark analysis.

    Unlike FileTraceProcessor which logs to files, this processor stores
    traces in a structured JSON format optimized for analysis.
    """

    def __init__(self, output_file: str | None = None):
        """
        Initialize the benchmark trace processor.

        Args:
            output_file: Path to save traces (default: auto-generated in benchmarks/)
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"benchmarks/traces/trace_{timestamp}.json"

        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # In-memory storage during execution
        self.traces: dict[str, dict] = {}  # trace_id -> trace_data
        self.spans: dict[str, dict] = {}   # span_id -> span_data

    def on_trace_start(self, trace: Trace) -> None:
        """Capture trace start event."""
        self.traces[trace.trace_id] = {
            "trace_id": trace.trace_id,
            "name": trace.name,
            "started_at": trace.started_at.isoformat() if trace.started_at else None,
            "ended_at": None,
            "metadata": trace.metadata,
            "spans": [],
        }

    def on_trace_end(self, trace: Trace) -> None:
        """Capture trace end event."""
        if trace.trace_id in self.traces:
            self.traces[trace.trace_id]["ended_at"] = (
                trace.ended_at.isoformat() if trace.ended_at else None
            )

    def on_span_start(self, span: Span[Any]) -> None:
        """Capture span start event."""
        span_data = {
            "span_id": span.span_id,
            "trace_id": span.trace_id,
            "parent_id": span.parent_id,
            "name": getattr(span, "name", None),
            "started_at": span.started_at.isoformat() if span.started_at else None,
            "ended_at": None,
            "metadata": {},
        }

        # Try to extract agent name from span
        exported = self._safe_export(span)
        if exported and isinstance(exported, dict):
            span_data["metadata"] = exported.get("metadata", {})
            span_data["name"] = exported.get("name", span_data["name"])

        self.spans[span.span_id] = span_data

        # Add span to its trace
        if span.trace_id in self.traces:
            self.traces[span.trace_id]["spans"].append(span.span_id)

    def on_span_end(self, span: Span[Any]) -> None:
        """Capture span end event."""
        if span.span_id in self.spans:
            self.spans[span.span_id]["ended_at"] = (
                span.ended_at.isoformat() if span.ended_at else None
            )

            # Update metadata with final state
            exported = self._safe_export(span)
            if exported and isinstance(exported, dict):
                self.spans[span.span_id]["metadata"].update(
                    exported.get("metadata", {})
                )

    def _safe_export(self, obj) -> dict | None:
        """Safely export trace/span data."""
        try:
            if hasattr(obj, "export"):
                return obj.export()
        except Exception:
            pass
        return None

    def save(self) -> str:
        """
        Save traces to file.

        Returns:
            Path to saved file
        """
        # Build complete trace structure
        output = {
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "traces": [],
        }

        for trace_data in self.traces.values():
            # Resolve span references
            trace_copy = trace_data.copy()
            trace_copy["spans"] = [
                self.spans[span_id] for span_id in trace_data["spans"]
                if span_id in self.spans
            ]
            output["traces"].append(trace_copy)

        # Save to file
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        return str(self.output_file)

    def get_trace_file(self) -> str:
        """Get the output file path."""
        return str(self.output_file)
