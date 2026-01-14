"""
Manual script: offline tracing experiments (framework-agnostic JSONL logger).

Not a unit test: it's for interactive experimentation.

Run manually:
  poetry run python integration_tests/manual_offline_tracing.py
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path


class FrameworkAgnosticEventLogger:
    def __init__(self, output_file: str):
        self.output_file = Path(output_file)
        self.output_file.write_text("", encoding="utf-8")

    def _log_event(self, event_type: str, **kwargs) -> None:
        event = {"timestamp": datetime.now().isoformat(), "event_type": event_type, **kwargs}
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def log_workflow_start(self, workflow_name: str, input_data: dict) -> None:
        self._log_event("workflow_start", workflow_name=workflow_name, input=input_data)

    def log_tool_call(self, tool_name: str, success: bool, duration_ms: float, metadata: dict | None = None):
        self._log_event(
            "tool_call",
            tool_name=tool_name,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

    def log_generation(self, generation_type: str, output: str, metadata: dict | None = None):
        self._log_event(
            "generation",
            generation_type=generation_type,
            output=output[:500] + "..." if len(output) > 500 else output,
            output_length=len(output),
            metadata=metadata or {},
        )

    def log_workflow_end(self, workflow_name: str, success: bool, duration_ms: float) -> None:
        self._log_event("workflow_end", workflow_name=workflow_name, success=success, duration_ms=duration_ms)


def main() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        event_file = f.name

    logger = FrameworkAgnosticEventLogger(event_file)
    logger.log_workflow_start("research_workflow", {"syllabus": "Python basics"})
    logger.log_tool_call("download_and_store_url", success=True, duration_ms=12.3, metadata={"url": "https://example.com"})
    logger.log_generation("report_generation", output="# Research Report\n\n## Raw Notes\n...")
    logger.log_workflow_end("research_workflow", success=True, duration_ms=150.0)

    print(f"Wrote events to {event_file}")


if __name__ == "__main__":
    main()

"""
Manual script: offline tracing experiments.

This file used to live under `tests/` but it is not a reliable unit test:
- It may require external LLMs / environment configuration.
- It is meant for interactive experimentation and documentation.

Run manually:
  poetry run python integration_tests/manual_offline_tracing.py
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path


class FrameworkAgnosticEventLogger:
    """Simple JSONL event logger (framework-agnostic)."""

    def __init__(self, output_file: str):
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.output_file.write_text("", encoding="utf-8")

    def _log_event(self, event_type: str, **kwargs) -> None:
        event = {"timestamp": datetime.now().isoformat(), "event_type": event_type, **kwargs}
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def log_workflow_start(self, workflow_name: str, input_data: dict) -> None:
        self._log_event("workflow_start", workflow_name=workflow_name, input=input_data)

    def log_tool_call(self, tool_name: str, success: bool, duration_ms: float, metadata: dict | None = None):
        self._log_event(
            "tool_call",
            tool_name=tool_name,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

    def log_generation(self, generation_type: str, output: str, metadata: dict | None = None):
        self._log_event(
            "generation",
            generation_type=generation_type,
            output=output[:500] + "..." if len(output) > 500 else output,
            output_length=len(output),
            metadata=metadata or {},
        )

    def log_workflow_end(self, workflow_name: str, success: bool, duration_ms: float) -> None:
        self._log_event("workflow_end", workflow_name=workflow_name, success=success, duration_ms=duration_ms)

    def get_events(self) -> list[dict]:
        events: list[dict] = []
        with open(self.output_file, "r", encoding="utf-8") as f:
            for line in f:
                events.append(json.loads(line))
        return events


def main() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        event_file = f.name

    logger = FrameworkAgnosticEventLogger(event_file)
    logger.log_workflow_start("research_workflow", {"syllabus": "Python basics"})
    logger.log_tool_call("download_and_store_url", success=True, duration_ms=12.3, metadata={"url": "https://example.com"})
    logger.log_generation("report_generation", output="# Research Report\n\n## Raw Notes\n...", metadata={"sections": ["Raw Notes", "Agenda", "Report"]})
    logger.log_workflow_end("research_workflow", success=True, duration_ms=150.0)

    events = logger.get_events()
    print(f"Captured {len(events)} events in {event_file}")
    for e in events:
        print(f"- {e['event_type']}")


if __name__ == "__main__":
    main()

