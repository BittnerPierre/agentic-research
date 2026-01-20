"""
Manual test: Does Agents SDK tracing work offline with Ollama?

Why it's manual:
- Requires Ollama running locally
- Requires internet to be disconnected
- Not suitable for CI / unit test suite

Run manually:
  poetry run python integration_tests/manual_agents_sdk_tracing_offline.py
"""

import json
import socket
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from agents import Agent, Runner, Span, Trace, TracingProcessor, set_trace_processors
from agents.extensions.models.litellm_model import LitellmModel


def check_internet_connection() -> bool:
    """Return True if online, False if offline (best-effort)."""
    test_sites = [
        ("www.google.com", 80),
        ("api.openai.com", 443),
        ("1.1.1.1", 80),  # Cloudflare DNS
    ]

    for host, port in test_sites:
        try:
            socket.create_connection((host, port), timeout=2)
            return True
        except (TimeoutError, OSError):
            continue

    return False


def verify_offline() -> None:
    """Raise if internet is still available."""
    if check_internet_connection():
        raise RuntimeError(
            "❌ Internet connection detected!\n"
            "   Please disconnect Wi-Fi/Ethernet to run this offline test.\n"
            "   This test validates that Agents SDK tracing works WITHOUT internet."
        )
    print("✓ Verified: No internet connection (offline mode)")
    print("  - Cannot reach google.com")
    print("  - Cannot reach api.openai.com")
    print("  - Cannot reach 1.1.1.1")


class OfflineJSONTraceProcessor(TracingProcessor):
    """
    Minimal TracingProcessor that writes to JSONL.
    Includes required abstract methods: force_flush, shutdown.
    """

    def __init__(self, output_file: str):
        self.output_file = Path(output_file)

    def _write_event(self, event: dict) -> None:
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def on_trace_start(self, trace: Trace) -> None:
        self._write_event(
            {
                "timestamp": datetime.now().isoformat(),
                "event_type": "trace_start",
                "trace_id": trace.trace_id,
                "name": trace.name,
            }
        )

    def on_trace_end(self, trace: Trace) -> None:
        self._write_event(
            {
                "timestamp": datetime.now().isoformat(),
                "event_type": "trace_end",
                "trace_id": trace.trace_id,
            }
        )

    def on_span_start(self, span: Span[Any]) -> None:
        self._write_event(
            {
                "timestamp": datetime.now().isoformat(),
                "event_type": "span_start",
                "span_id": span.span_id,
                "trace_id": span.trace_id,
            }
        )

    def on_span_end(self, span: Span[Any]) -> None:
        exported = span.export() if hasattr(span, "export") else {}
        self._write_event(
            {
                "timestamp": datetime.now().isoformat(),
                "event_type": "span_end",
                "span_id": span.span_id,
                "trace_id": span.trace_id,
                "span_type": type(span).__name__,
                "data": exported,
            }
        )

    def force_flush(self) -> None:
        pass

    def shutdown(self, timeout: float | None = None) -> None:
        pass


def test_tracing_offline_with_ollama() -> bool:
    """
    Manual test: tracing offline with Ollama.

    Prereqs:
    - Ollama running: `ollama serve`
    - Model pulled: `ollama pull qwen3:8b` (or adjust below)
    - Internet disconnected (Wi-Fi off)
    """
    print("\n" + "=" * 80)
    print("TEST: Agents SDK Tracing with Ollama (Offline)")
    print("=" * 80)

    print("\n🔍 Checking internet connectivity...")
    verify_offline()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        trace_file = f.name

    try:
        processor = OfflineJSONTraceProcessor(trace_file)
        set_trace_processors([processor])
        print(f"✓ Custom TracingProcessor registered: {trace_file}")

        model = LitellmModel(
            model="ollama/qwen3:8b",
            base_url="http://localhost:11434",
        )
        print("✓ Ollama model configured: qwen3:8b")

        agent = Agent(
            name="SimpleBot",
            model=model,
            instructions="You are a helpful assistant. Answer directly and concisely in one sentence.",
        )
        print("✓ Agent created (no tools, simple response)")

        agent_succeeded = False
        try:
            result = Runner.run_sync(agent, "Say hello", max_turns=3)
            print("✓ Agent executed successfully")
            print(f"   Output: {result.final_output[:100]}...")
            agent_succeeded = True
        except Exception as e:
            print(f"⚠️  Agent failed: {e}")
            print("   (This is OK - we're testing tracing, not agent behavior)")

        print("\n📊 Checking trace file...")
        with open(trace_file, encoding="utf-8") as f:
            events = [json.loads(line) for line in f]

        print(f"   Events captured: {len(events)}")
        if len(events) > 0:
            for event in events[:10]:
                print(f"   - {event['event_type']}: {event.get('span_type', 'N/A')}")
            if len(events) > 10:
                print(f"   ... ({len(events) - 10} more events)")
        else:
            print("   (no events captured)")

        assert len(events) > 0, "No events captured - tracing failed"
        event_types = [e["event_type"] for e in events]
        assert "trace_start" in event_types, "Missing trace_start"
        assert "span_end" in event_types, "Missing span events"

        print("\n✅ SUCCESS: Agents SDK tracing works offline!")
        if not agent_succeeded:
            print("  ⚠️  Agent hit an error (not a tracing issue)")
        return True
    except Exception as e:
        print(f"\n❌ FAILURE: {e}")
        return False


if __name__ == "__main__":
    ok = test_tracing_offline_with_ollama()
    raise SystemExit(0 if ok else 1)

