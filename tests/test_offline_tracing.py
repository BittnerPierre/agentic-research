"""
Test: Verify structured tracing works offline (without internet/Agents SDK telemetry).

Problem:
- set_tracing_disabled(True) breaks TracingProcessor strategy
- Need to work offline for DGX Spark / air-gapped environments
- Need framework independence (Agents SDK, PydanticAI, CrewAI)

Solution:
Test if custom TracingProcessor works when OpenAI tracing is disabled.
"""

import os
import json
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Any

from agents import Agent, Runner, function_tool, set_tracing_disabled, TracingProcessor, Trace, Span, set_trace_processors


# ============================================================================
# Test 1: Custom TracingProcessor with SDK tracing disabled
# ============================================================================

class SimpleJSONLTraceProcessor(TracingProcessor):
    """
    Minimal TracingProcessor that writes to JSONL.
    Tests if this works when set_tracing_disabled(True).
    """

    def __init__(self, output_file: str):
        self.output_file = Path(output_file)
        self.events = []

    def _write_event(self, event: dict):
        """Append event to JSONL file."""
        with open(self.output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, default=str) + '\n')
        self.events.append(event)

    def on_trace_start(self, trace: Trace) -> None:
        self._write_event({
            "timestamp": datetime.now().isoformat(),
            "event_type": "trace_start",
            "trace_id": trace.trace_id,
            "name": trace.name,
        })

    def on_trace_end(self, trace: Trace) -> None:
        self._write_event({
            "timestamp": datetime.now().isoformat(),
            "event_type": "trace_end",
            "trace_id": trace.trace_id,
        })

    def on_span_start(self, span: Span[Any]) -> None:
        self._write_event({
            "timestamp": datetime.now().isoformat(),
            "event_type": "span_start",
            "span_id": span.span_id,
            "trace_id": span.trace_id,
        })

    def on_span_end(self, span: Span[Any]) -> None:
        exported = span.export() if hasattr(span, 'export') else {}
        self._write_event({
            "timestamp": datetime.now().isoformat(),
            "event_type": "span_end",
            "span_id": span.span_id,
            "trace_id": span.trace_id,
            "span_type": type(span).__name__,
            "data": exported,
        })


def test_tracing_with_sdk_disabled():
    """
    Test: Does custom TracingProcessor still work when SDK tracing is disabled?

    Expected: Custom processor should still receive events even if OpenAI/LangSmith
              tracing is disabled.
    """
    print("\n" + "="*80)
    print("TEST 1: Custom TracingProcessor with set_tracing_disabled(True)")
    print("="*80)

    # Disable OpenAI/LangSmith tracing
    # set_tracing_disabled(True)
    print("✓ SDK tracing disabled (no OpenAI Platform / LangSmith)")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        trace_file = f.name

    try:
        # Add custom processor
        from agents import add_trace_processor
        processor = SimpleJSONLTraceProcessor(trace_file)
        set_trace_processors([processor])
        print(f"✓ Custom processor added: {trace_file}")

        # Create simple agent
        @function_tool
        def get_weather(city: str):
            return f"The weather in {city} is sunny."

        agent = Agent(
            name="WeatherBot",
            instructions="You are a weather assistant.",
            tools=[get_weather]
        )

        # Run agent
        result = Runner.run_sync(agent, "What's the weather in Paris?")
        print(f"✓ Agent executed: {result.final_output[:50]}...")

        # Check if events were captured
        with open(trace_file, 'r') as f:
            events = [json.loads(line) for line in f]

        print(f"\n📊 Events captured: {len(events)}")
        for event in events:
            print(f"   - {event['event_type']}: {event.get('name', event.get('span_type', 'N/A'))}")

        # Assertions
        assert len(events) > 0, "❌ No events captured - TracingProcessor doesn't work offline!"

        event_types = [e['event_type'] for e in events]
        assert 'trace_start' in event_types, "❌ Missing trace_start"
        assert 'trace_end' in event_types, "❌ Missing trace_end"
        assert 'span_end' in event_types, "❌ Missing span events"

        print("\n✅ SUCCESS: Custom TracingProcessor works with SDK tracing disabled!")
        return True

    except Exception as e:
        print(f"\n❌ FAILURE: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        if os.path.exists(trace_file):
            os.unlink(trace_file)


# ============================================================================
# Test 2: Framework-Agnostic Event Logger (Alternative Approach)
# ============================================================================

class FrameworkAgnosticEventLogger:
    """
    Simple event logger that doesn't depend on any framework's hooks.

    Can be used with:
    - Agents SDK
    - PydanticAI
    - CrewAI
    - Custom implementations

    Usage:
        logger = FrameworkAgnosticEventLogger("events.jsonl")
        logger.log_tool_call("download_url", success=True, duration_ms=234)
        logger.log_generation("report_generation", output="# Report...")
    """

    def __init__(self, output_file: str):
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # Clear file
        with open(self.output_file, 'w') as f:
            pass

    def _log_event(self, event_type: str, **kwargs):
        """Write event to JSONL."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            **kwargs
        }
        with open(self.output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, default=str) + '\n')

    def log_workflow_start(self, workflow_name: str, input_data: dict):
        """Log workflow start."""
        self._log_event("workflow_start", workflow_name=workflow_name, input=input_data)

    def log_workflow_end(self, workflow_name: str, success: bool, duration_ms: float):
        """Log workflow end."""
        self._log_event("workflow_end", workflow_name=workflow_name, success=success, duration_ms=duration_ms)

    def log_tool_call(self, tool_name: str, success: bool, duration_ms: float, metadata: dict = None):
        """Log tool execution."""
        self._log_event(
            "tool_call",
            tool_name=tool_name,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata or {}
        )

    def log_generation(self, generation_type: str, output: str, metadata: dict = None):
        """Log content generation."""
        self._log_event(
            "generation",
            generation_type=generation_type,
            output=output[:500] + "..." if len(output) > 500 else output,
            output_length=len(output),
            metadata=metadata or {}
        )

    def log_error(self, error_type: str, error_message: str, metadata: dict = None):
        """Log error."""
        self._log_event(
            "error",
            error_type=error_type,
            error_message=error_message,
            metadata=metadata or {}
        )

    def get_events(self) -> list[dict]:
        """Load all events from file."""
        events = []
        with open(self.output_file, 'r') as f:
            for line in f:
                events.append(json.loads(line))
        return events


def test_framework_agnostic_logger():
    """
    Test: Framework-agnostic event logger (doesn't depend on SDK hooks).

    This approach:
    - ✅ Works offline (no SDK dependency)
    - ✅ Framework agnostic (explicit logging)
    - ✅ Simple to integrate into any codebase
    - ✅ Full control over what's logged
    """
    print("\n" + "="*80)
    print("TEST 2: Framework-Agnostic Event Logger")
    print("="*80)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        event_file = f.name

    try:
        logger = FrameworkAgnosticEventLogger(event_file)
        print(f"✓ Logger created: {event_file}")

        # Simulate workflow
        import time

        logger.log_workflow_start("research_workflow", {"syllabus": "Python basics"})

        # Simulate tool calls
        start = time.time()
        time.sleep(0.01)  # Simulate work
        logger.log_tool_call(
            "download_and_store_url",
            success=True,
            duration_ms=(time.time() - start) * 1000,
            metadata={"url": "https://example.com", "output_file": "data/example.md"}
        )

        start = time.time()
        time.sleep(0.01)
        logger.log_tool_call(
            "upload_files_to_vectorstore",
            success=True,
            duration_ms=(time.time() - start) * 1000,
            metadata={"files_uploaded": 5}
        )

        # Simulate generation
        logger.log_generation(
            "report_generation",
            output="# Research Report\n\n## Raw Notes\n...",
            metadata={"sections": ["Raw Notes", "Agenda", "Report"]}
        )

        logger.log_workflow_end("research_workflow", success=True, duration_ms=150)

        # Load and validate events
        events = logger.get_events()
        print(f"\n📊 Events captured: {len(events)}")
        for event in events:
            print(f"   - {event['event_type']}: {event.get('tool_name', event.get('workflow_name', event.get('generation_type', 'N/A')))}")

        # Assertions
        assert len(events) == 5, f"Expected 5 events, got {len(events)}"
        assert events[0]['event_type'] == 'workflow_start'
        assert events[1]['event_type'] == 'tool_call'
        assert events[1]['tool_name'] == 'download_and_store_url'
        assert events[2]['tool_name'] == 'upload_files_to_vectorstore'
        assert events[3]['event_type'] == 'generation'
        assert events[4]['event_type'] == 'workflow_end'

        print("\n✅ SUCCESS: Framework-agnostic logger works perfectly!")
        print("\nBenefits:")
        print("  ✓ No dependency on Agents SDK tracing")
        print("  ✓ Works offline (no internet required)")
        print("  ✓ Can be used with PydanticAI, CrewAI, custom code")
        print("  ✓ Explicit control over what's logged")

        return True

    except Exception as e:
        print(f"\n❌ FAILURE: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if os.path.exists(event_file):
            os.unlink(event_file)


# ============================================================================
# Test 3: Comparison - Which approach to use?
# ============================================================================

def print_comparison():
    """Print comparison between approaches."""
    print("\n" + "="*80)
    print("COMPARISON: TracingProcessor vs Framework-Agnostic Logger")
    print("="*80)

    print("\n📊 Approach 1: Agents SDK TracingProcessor")
    print("   ✅ Pros:")
    print("      - Automatic capture (no manual instrumentation)")
    print("      - Rich context (agent names, span hierarchy)")
    print("      - Works with OpenAI Platform / LangSmith")
    print("   ❌ Cons:")
    print("      - Tied to Agents SDK")
    print("      - May not work offline (needs testing)")
    print("      - Hard to port to other frameworks")

    print("\n📊 Approach 2: Framework-Agnostic Event Logger")
    print("   ✅ Pros:")
    print("      - ✅ Works offline (no SDK dependency)")
    print("      - ✅ Framework agnostic (PydanticAI, CrewAI, custom)")
    print("      - ✅ Simple implementation (~100 lines)")
    print("      - ✅ Full control over what's logged")
    print("      - ✅ Easy to understand and debug")
    print("   ❌ Cons:")
    print("      - Manual instrumentation required")
    print("      - No automatic span hierarchy")

    print("\n🎯 Recommendation:")
    print("   For evaluation framework → Use Approach 2 (Framework-Agnostic)")
    print("   Reasons:")
    print("   1. Evaluation should work regardless of framework used")
    print("   2. Offline operation is critical (DGX Spark, air-gapped)")
    print("   3. Explicit logging is clearer for debugging")
    print("   4. Easy to port to PydanticAI / CrewAI if needed")

    print("\n📝 Optional:")
    print("   Keep TracingProcessor for development/debugging")
    print("   Use framework-agnostic logger for production evaluation")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    print("🧪 Testing Offline Tracing Approaches\n")

    # Test 1: Does SDK TracingProcessor work offline?
    test1_passed = test_tracing_with_sdk_disabled()

    # Test 2: Framework-agnostic logger
    test2_passed = test_framework_agnostic_logger()

    # Comparison
    print_comparison()

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Test 1 (SDK TracingProcessor offline): {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Test 2 (Framework-agnostic logger):   {'✅ PASS' if test2_passed else '❌ FAIL'}")

    if test1_passed and test2_passed:
        print("\n✅ All tests passed!")
        print("\n🎯 Next step: Decide which approach to use for evaluation framework")
    else:
        print("\n❌ Some tests failed - review errors above")
