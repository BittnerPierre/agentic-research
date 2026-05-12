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
        self.spans: dict[str, dict] = {}  # span_id -> span_data

    def on_trace_start(self, trace: Trace) -> None:
        """Capture trace start event."""
        exported = self._safe_export(trace) or {}
        trace_id = getattr(trace, "trace_id", None) or exported.get("id")
        if not trace_id:
            return
        trace_name = (
            getattr(trace, "name", None) or exported.get("name") or exported.get("workflow_name")
        )
        trace_metadata = getattr(trace, "metadata", None)
        if trace_metadata is None:
            trace_metadata = exported.get("metadata", {})

        self.traces[trace_id] = {
            "trace_id": trace_id,
            "name": trace_name,
            "started_at": self._as_iso_timestamp(
                getattr(trace, "started_at", None) or exported.get("started_at")
            ),
            "ended_at": None,
            "metadata": trace_metadata,
            "spans": [],
        }

    def on_trace_end(self, trace: Trace) -> None:
        """Capture trace end event."""
        exported = self._safe_export(trace) or {}
        trace_id = getattr(trace, "trace_id", None) or exported.get("id")
        if trace_id in self.traces:
            self.traces[trace_id]["ended_at"] = self._as_iso_timestamp(
                getattr(trace, "ended_at", None) or exported.get("ended_at")
            )
            if self.traces[trace_id]["started_at"] is None:
                self.traces[trace_id]["started_at"] = self._as_iso_timestamp(
                    exported.get("started_at")
                )

    def on_span_start(self, span: Span[Any]) -> None:
        """Capture span start event."""
        exported = self._safe_export(span) or {}
        span_id = getattr(span, "span_id", None) or exported.get("id")
        trace_id = getattr(span, "trace_id", None) or exported.get("trace_id")
        if not span_id or not trace_id:
            return

        span_data_export = exported.get("span_data", {})
        span_name = (
            getattr(span, "name", None)
            or exported.get("name")
            or (span_data_export.get("name") if isinstance(span_data_export, dict) else None)
        )
        span_metadata: dict[str, Any] = {}
        if isinstance(exported.get("metadata"), dict):
            span_metadata.update(exported.get("metadata", {}))
        if isinstance(span_data_export, dict):
            # Preserve span_data type/name for downstream analyzers.
            if span_data_export.get("type"):
                span_metadata["span_type"] = span_data_export.get("type")
            if span_data_export.get("name"):
                span_metadata["span_name"] = span_data_export.get("name")

        span_data = {
            "span_id": span_id,
            "trace_id": trace_id,
            "parent_id": getattr(span, "parent_id", None) or exported.get("parent_id"),
            "name": span_name,
            "started_at": self._as_iso_timestamp(
                getattr(span, "started_at", None) or exported.get("started_at")
            ),
            "ended_at": None,
            "metadata": span_metadata,
            # Full span_data export preserved for debugging. For generation
            # spans this includes input (conversation history), output (model
            # response), model, model_config, usage. For function spans:
            # input args, output. For handoff spans: from_agent/to_agent.
            # Snapshot at span_start; updated again at span_end for completion.
            "span_data": span_data_export if isinstance(span_data_export, dict) else None,
        }

        # Track error field from exported payload if present.
        if exported.get("error") is not None:
            span_data["metadata"]["error"] = exported.get("error")

        self.spans[span_id] = span_data

        # Add span to its trace
        if trace_id in self.traces:
            self.traces[trace_id]["spans"].append(span_id)

    def on_span_end(self, span: Span[Any]) -> None:
        """Capture span end event."""
        exported = self._safe_export(span) or {}
        span_id = getattr(span, "span_id", None) or exported.get("id")
        if span_id in self.spans:
            self.spans[span_id]["ended_at"] = self._as_iso_timestamp(
                getattr(span, "ended_at", None) or exported.get("ended_at")
            )

            # Update metadata with final state
            if exported and isinstance(exported, dict):
                self.spans[span_id]["metadata"].update(exported.get("metadata", {}))
                if exported.get("error") is not None:
                    self.spans[span_id]["metadata"]["error"] = exported.get("error")
                # Re-capture span_data at span_end: SDK populates input/output
                # once the LLM call completes, so the end snapshot is the rich
                # one we need for debugging tool-call mismatches etc.
                end_span_data = exported.get("span_data")
                if isinstance(end_span_data, dict):
                    self.spans[span_id]["span_data"] = end_span_data

            # ResponseSpanData (Responses API path) carries `response` and
            # `input` as Python attributes but exports only `response_id`.
            # We bypass export() and read the attributes directly — exactly
            # the hook the SDK docstring points at:
            #   "not used by the OpenAI trace processors, but is useful for
            #    other tracing processor implementations".
            raw_span_data = getattr(span, "span_data", None)
            if raw_span_data is not None and getattr(raw_span_data, "type", None) == "response":
                self.spans[span_id]["span_data"] = self._capture_response_span_data(
                    raw_span_data
                )

    def _capture_response_span_data(self, raw_span_data: Any) -> dict:
        """Extract response and input from a ResponseSpanData via attributes.

        Falls back gracefully if model_dump / dict conversion fails — we want
        the trace to be best-effort, never to crash the bench.
        """
        result: dict[str, Any] = {"type": "response"}

        response = getattr(raw_span_data, "response", None)
        if response is not None:
            result["response_id"] = getattr(response, "id", None)
            # Pydantic v2 model on the OpenAI SDK side.
            for serializer in ("model_dump", "to_dict"):
                fn = getattr(response, serializer, None)
                if callable(fn):
                    try:
                        result["response"] = fn()
                        break
                    except Exception as exc:
                        result["response_dump_error"] = f"{type(exc).__name__}: {exc}"

        input_value = getattr(raw_span_data, "input", None)
        if input_value is not None:
            # input is str | list[ResponseInputItemParam]. The list items are
            # TypedDicts → JSON-serializable as-is. str passes through.
            try:
                # Round-trip through json to verify serializability and to
                # normalize Pydantic objects nested inside (defensive).
                result["input"] = json.loads(json.dumps(input_value, default=str))
            except Exception as exc:
                result["input_dump_error"] = f"{type(exc).__name__}: {exc}"
                result["input_repr"] = repr(input_value)[:2000]

        return result

    def _as_iso_timestamp(self, value: Any) -> str | None:
        """Normalize timestamp values from agents SDK to ISO string."""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        return str(value)

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
                self.spans[span_id] for span_id in trace_data["spans"] if span_id in self.spans
            ]
            output["traces"].append(trace_copy)

        # Save to file
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        return str(self.output_file)

    def get_trace_file(self) -> str:
        """Get the output file path."""
        return str(self.output_file)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """
        Force flush any buffered traces to storage.

        Args:
            timeout_millis: Timeout in milliseconds (unused, for interface compatibility)

        Returns:
            True if flush succeeded
        """
        try:
            self.save()
            return True
        except Exception:
            return False

    def shutdown(self) -> None:
        """Shutdown the processor and save final traces."""
        self.save()
