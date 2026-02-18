"""
Unit tests for benchmark framework components

Run with: pytest tests/test_benchmark_components.py -v
"""

import inspect
import json
import os
import sys
from http.client import HTTPConnection
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from agents.mcp import MCPServerStdio


class TestSetupDetector:
    """Test setup detection logic."""

    def test_extract_setup_name(self):
        """Test extracting setup name from filename."""
        from evaluations.setup_detector import extract_setup_name

        assert extract_setup_name("models/models.openai.env") == "openai"
        assert extract_setup_name("models.ministral.env") == "ministral"
        assert extract_setup_name("/path/to/models.qwen.env") == "qwen"

    def test_extract_setup_name_invalid(self):
        """Test invalid filename raises ValueError."""
        from evaluations.setup_detector import extract_setup_name

        with pytest.raises(ValueError):
            extract_setup_name("invalid.env")

        with pytest.raises(ValueError):
            extract_setup_name("models.env")

    def test_extract_quantization(self):
        """Test quantization extraction from GGUF filenames."""
        from evaluations.setup_detector import extract_quantization

        assert extract_quantization("Ministral-3-14B-Instruct-Q4_K_M.gguf") == "Q4_K_M"
        assert extract_quantization("gpt-oss-20b-mxfp4.gguf") == "mxfp4"
        assert extract_quantization("Qwen3-Embedding-4B-Q8_0.gguf") == "Q8_0"
        assert extract_quantization("model-BF16.gguf") == "BF16"
        assert extract_quantization("unknown-model.gguf") == "unknown"

    def test_detect_with_env_var(self, monkeypatch, tmp_path):
        """Test setup detection via BENCHMARK_SETUP_NAME env var."""
        from evaluations.setup_detector import detect_active_setup

        # Create a test models config file
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        test_file = models_dir / "models.test.env"
        test_file.write_text(
            "LLM_INSTRUCT_MODEL_PATH=/path/to/model-Q4_K_M.gguf\n" "LLM_INSTRUCT_CTX_SIZE=32768\n"
        )

        # Set env var and working directory
        monkeypatch.setenv("BENCHMARK_SETUP_NAME", "test")
        monkeypatch.chdir(tmp_path)

        result = detect_active_setup()
        assert result["setup_name"] == "test"
        assert result["models"]["instruct"]["quantization"] == "Q4_K_M"


class TestBenchmarkTraceProcessor:
    """Test trace processor functionality."""

    def test_instantiation(self, tmp_path):
        """Test that BenchmarkTraceProcessor can be instantiated."""
        from evaluations.benchmark_trace_processor import BenchmarkTraceProcessor

        trace_file = tmp_path / "trace.json"
        processor = BenchmarkTraceProcessor(str(trace_file))

        assert processor.output_file == trace_file
        assert hasattr(processor, "force_flush")
        assert hasattr(processor, "shutdown")

    def test_save_empty_traces(self, tmp_path):
        """Test saving empty traces."""
        from evaluations.benchmark_trace_processor import BenchmarkTraceProcessor

        trace_file = tmp_path / "trace.json"
        processor = BenchmarkTraceProcessor(str(trace_file))

        output_path = processor.save()
        assert Path(output_path).exists()

        import json

        with open(output_path) as f:
            data = json.load(f)

        assert data["version"] == "1.0"
        assert data["traces"] == []

    def test_handles_string_timestamps_and_missing_trace_started_at(self, tmp_path):
        """Trace processor should tolerate SDK objects with string timestamps."""
        from evaluations.benchmark_trace_processor import BenchmarkTraceProcessor

        class _FakeTrace:
            def __init__(self):
                self.trace_id = "trace-1"
                self.name = "deep-research"
                # started_at intentionally missing
                self.ended_at = "2026-02-12T11:37:40"
                self.metadata = {"k": "v"}

            def export(self):
                return {
                    "id": "trace-1",
                    "workflow_name": "deep-research",
                    "started_at": "2026-02-12T11:37:30",
                    "ended_at": "2026-02-12T11:37:40",
                    "metadata": {"k": "v"},
                }

        class _FakeSpan:
            def __init__(self):
                self.span_id = "span-1"
                self.trace_id = "trace-1"
                self.parent_id = None
                self.name = "knowledge_preparation"
                self.started_at = "2026-02-12T11:37:35"
                self.ended_at = "2026-02-12T11:37:36"

            def export(self):
                return {
                    "id": "span-1",
                    "trace_id": "trace-1",
                    "parent_id": None,
                    "started_at": "2026-02-12T11:37:35",
                    "ended_at": "2026-02-12T11:37:36",
                    "span_data": {"type": "custom", "name": "knowledge_preparation"},
                    "metadata": {"agent_name": "knowledge_preparation_agent"},
                }

        trace_file = tmp_path / "trace.json"
        processor = BenchmarkTraceProcessor(str(trace_file))

        processor.on_trace_start(_FakeTrace())
        processor.on_span_start(_FakeSpan())
        processor.on_span_end(_FakeSpan())
        processor.on_trace_end(_FakeTrace())
        output_path = processor.save()

        data = json.loads(Path(output_path).read_text(encoding="utf-8"))
        assert data["traces"][0]["started_at"] == "2026-02-12T11:37:30"
        assert data["traces"][0]["ended_at"] == "2026-02-12T11:37:40"
        assert data["traces"][0]["spans"][0]["started_at"] == "2026-02-12T11:37:35"
        assert data["traces"][0]["spans"][0]["name"] == "knowledge_preparation"

    def test_span_end_updates_late_exported_metadata(self, tmp_path):
        """Processor should merge metadata that arrives only at span end."""
        from evaluations.benchmark_trace_processor import BenchmarkTraceProcessor

        class _FakeTrace:
            def __init__(self):
                self.trace_id = "trace-late"
                self.name = "deep-research"

            def export(self):
                return {
                    "id": "trace-late",
                    "workflow_name": "deep-research",
                    "started_at": "2026-02-12T12:00:00",
                    "ended_at": "2026-02-12T12:00:30",
                    "metadata": {"config_name": "dgx-remote"},
                }

        class _FakeSpanStart:
            span_id = "span-late"
            trace_id = "trace-late"
            parent_id = None

            def export(self):
                return {
                    "id": "span-late",
                    "trace_id": "trace-late",
                    "parent_id": None,
                    "started_at": "2026-02-12T12:00:10",
                    "ended_at": None,
                    "span_data": {"type": "custom", "name": "search"},
                    "metadata": {},
                    "error": None,
                }

        class _FakeSpanEnd:
            span_id = "span-late"
            trace_id = "trace-late"
            parent_id = None

            def export(self):
                return {
                    "id": "span-late",
                    "trace_id": "trace-late",
                    "parent_id": None,
                    "started_at": "2026-02-12T12:00:10",
                    "ended_at": "2026-02-12T12:00:20",
                    "span_data": {"type": "custom", "name": "search"},
                    "metadata": {"agent_name": "file_search_agent"},
                    "error": "timeout while querying source",
                }

        trace_file = tmp_path / "trace.json"
        processor = BenchmarkTraceProcessor(str(trace_file))

        processor.on_trace_start(_FakeTrace())
        processor.on_span_start(_FakeSpanStart())
        processor.on_span_end(_FakeSpanEnd())
        processor.on_trace_end(_FakeTrace())
        output_path = processor.save()

        data = json.loads(Path(output_path).read_text(encoding="utf-8"))
        span = data["traces"][0]["spans"][0]
        assert span["ended_at"] == "2026-02-12T12:00:20"
        assert span["metadata"]["agent_name"] == "file_search_agent"
        assert span["metadata"]["error"] == "timeout while querying source"


class TestTraceAnalyzer:
    """Test trace analysis logic."""

    def test_parse_empty_trace(self, tmp_path):
        """Test parsing empty trace file."""
        from evaluations.trace_analyzer import TraceAnalyzer

        trace_file = tmp_path / "trace.json"
        trace_file.write_text('{"version": "1.0", "traces": []}')

        analyzer = TraceAnalyzer(str(trace_file))
        timing = analyzer.extract_timing()

        assert timing.total_seconds == 0.0
        assert timing.phases["knowledge_preparation"] == 0.0

    def test_extract_timing_from_sample(self, tmp_path):
        """Test timing extraction from sample trace data."""
        from evaluations.trace_analyzer import TraceAnalyzer

        # Create a minimal trace with timing data
        trace_data = {
            "version": "1.0",
            "traces": [
                {
                    "trace_id": "test-trace",
                    "started_at": "2026-01-01T10:00:00",
                    "ended_at": "2026-01-01T10:05:00",
                    "spans": [
                        {
                            "span_id": "span-1",
                            "name": "knowledge_preparation",
                            "started_at": "2026-01-01T10:00:00",
                            "ended_at": "2026-01-01T10:01:00",
                        }
                    ],
                }
            ],
        }

        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))

        analyzer = TraceAnalyzer(str(trace_file))
        timing = analyzer.extract_timing()

        assert timing.total_seconds == 300.0  # 5 minutes
        assert timing.phases["knowledge_preparation"] > 0

    def test_extract_agent_calls_and_failures(self, tmp_path):
        """Test agent call counting and failure detection."""
        from evaluations.trace_analyzer import TraceAnalyzer

        trace_data = {
            "version": "1.0",
            "traces": [
                {
                    "trace_id": "t1",
                    "started_at": "2026-01-01T10:00:00",
                    "ended_at": "2026-01-01T10:01:00",
                    "spans": [
                        {
                            "span_id": "s1",
                            "name": "planner step",
                            "started_at": "2026-01-01T10:00:00",
                            "ended_at": "2026-01-01T10:00:01",
                            "metadata": {"agent_name": "file_planner_agent"},
                        },
                        {
                            "span_id": "s2",
                            "name": "writer",
                            "started_at": "2026-01-01T10:00:02",
                            "ended_at": None,
                            "metadata": {},
                        },
                        {
                            "span_id": "s3",
                            "name": "search phase",
                            "started_at": "2026-01-01T10:00:03",
                            "ended_at": "2026-01-01T10:00:04",
                            "metadata": {"error": "boom"},
                        },
                        {
                            "span_id": "s4",
                            "name": "Call MCP tool",
                            "started_at": "2026-01-01T10:00:05",
                            "ended_at": "2026-01-01T10:00:06",
                            "metadata": {"span_type": "function"},
                        },
                    ],
                }
            ],
        }

        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data))

        analyzer = TraceAnalyzer(str(trace_file))
        calls = analyzer.extract_agent_calls()

        assert calls.file_planner_agent == 1
        assert calls.file_search_agent == 1
        assert calls.writer_agent == 1
        assert calls.total == 3
        assert calls.tool_calls_total == 1
        assert calls.failures == 2

    def test_extract_timing_tolerates_non_string_span_name(self, tmp_path):
        """Analyzer should not crash when span name is null/non-string."""
        from evaluations.trace_analyzer import TraceAnalyzer

        trace_data = {
            "version": "1.0",
            "traces": [
                {
                    "trace_id": "t1",
                    "started_at": "2026-01-01T10:00:00",
                    "ended_at": "2026-01-01T10:00:10",
                    "spans": [
                        {
                            "span_id": "s1",
                            "name": None,
                            "started_at": "2026-01-01T10:00:00",
                            "ended_at": "2026-01-01T10:00:05",
                            "metadata": None,
                        }
                    ],
                }
            ],
        }

        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data), encoding="utf-8")

        analyzer = TraceAnalyzer(str(trace_file))
        timing = analyzer.extract_timing()
        calls = analyzer.extract_agent_calls()

        assert timing.total_seconds == 10.0
        assert timing.phases["knowledge_preparation"] == 0.0
        assert calls.total == 0

    def test_extract_timing_uses_span_range_when_trace_bounds_missing(self, tmp_path):
        """Total timing should fallback to min/max span timestamps."""
        from evaluations.trace_analyzer import TraceAnalyzer

        trace_data = {
            "version": "1.0",
            "traces": [
                {
                    "trace_id": "t1",
                    "started_at": None,
                    "ended_at": None,
                    "spans": [
                        {
                            "span_id": "s1",
                            "name": "knowledge_preparation",
                            "started_at": "2026-01-01T10:00:00",
                            "ended_at": "2026-01-01T10:00:10",
                            "metadata": {},
                        },
                        {
                            "span_id": "s2",
                            "name": "writing report",
                            "started_at": "2026-01-01T10:00:20",
                            "ended_at": "2026-01-01T10:00:30",
                            "metadata": {},
                        },
                    ],
                }
            ],
        }

        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(trace_data), encoding="utf-8")
        analyzer = TraceAnalyzer(str(trace_file))
        timing = analyzer.extract_timing()

        assert timing.total_seconds == 30.0


class TestBenchmarkSchemas:
    """Test Pydantic schema validation."""

    def test_rag_triad_result_validation(self):
        """Test RAGTriadResult schema validation."""
        from evaluations.schemas import RAGTriadResult

        # Valid data
        result = RAGTriadResult(
            groundedness=0.9,
            context_relevance=0.8,
            answer_relevance=0.85,
            average=0.85,
            reasoning={
                "groundedness": "Good",
                "context_relevance": "Good",
                "answer_relevance": "Good",
            },
        )
        assert result.groundedness == 0.9

        # Invalid: score > 1.0
        with pytest.raises(ValueError):
            RAGTriadResult(
                groundedness=1.5,
                context_relevance=0.8,
                answer_relevance=0.8,
                average=1.03,
            )

    def test_timing_result_validation(self):
        """Test TimingResult schema validation."""
        from evaluations.schemas import TimingResult

        result = TimingResult(
            total_seconds=300.0,
            phases={
                "knowledge_preparation": 60.0,
                "planning": 30.0,
                "search": 120.0,
                "writing": 90.0,
            },
        )
        assert result.total_seconds == 300.0
        assert len(result.phases) == 4


@pytest.mark.integration
class TestBenchmarkRunnerIntegration:
    """Integration tests for benchmark runner (requires dependencies)."""

    def test_setup_detection_in_runner(self, monkeypatch, tmp_path):
        """Test that benchmark runner can detect setup."""
        from evaluations.benchmark_runner import BenchmarkRunner

        # Create mock environment
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        test_file = models_dir / "models.test.env"
        test_file.write_text("LLM_INSTRUCT_MODEL_PATH=/path/to/model-Q4_K_M.gguf\n")

        monkeypatch.setenv("BENCHMARK_SETUP_NAME", "test")
        monkeypatch.chdir(tmp_path)

        runner = BenchmarkRunner()
        # Just test that it doesn't crash on instantiation
        assert runner is not None

    @pytest.mark.asyncio
    async def test_run_single_evaluation_wires_fs_and_dataprep_mcp(self, monkeypatch, tmp_path):
        """Integration-style test for MCP wiring in run_single_evaluation."""
        import evaluations.benchmark_runner as benchmark_runner

        created_servers = []
        add_trace_calls = []

        class _FakeServer:
            def __init__(self, name, params, client_session_timeout_seconds=None):
                self.name = name
                self.params = params
                self.client_session_timeout_seconds = client_session_timeout_seconds
                created_servers.append(self)

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class _Dumpable:
            def __init__(self, payload):
                self._payload = payload

            def model_dump(self):
                return self._payload

        class _FakeTraceAnalyzer:
            def __init__(self, _trace_file):
                pass

            def extract_timing(self):
                return _Dumpable(
                    {
                        "total_seconds": 3.0,
                        "phases": {
                            "knowledge_preparation": 1.0,
                            "planning": 1.0,
                            "search": 0.5,
                            "writing": 0.5,
                        },
                    }
                )

            def extract_agent_calls(self):
                return _Dumpable(
                    {
                        "knowledge_preparation_agent": 1,
                        "file_planner_agent": 1,
                        "file_search_agent": 1,
                        "writer_agent": 1,
                        "total": 4,
                        "failures": 0,
                    }
                )

        class _FakeManager:
            async def run(self, **kwargs):
                output_dir = Path(kwargs["research_info"].output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "report.md").write_text(
                    "## Raw Notes\nsource notes\n\n## Analysis\ncontent", encoding="utf-8"
                )

        fake_manager_module = ModuleType("agentic_research.deep_research_manager")
        fake_manager_module.DeepResearchManager = _FakeManager
        monkeypatch.setitem(
            sys.modules, "agentic_research.deep_research_manager", fake_manager_module
        )

        monkeypatch.setattr(benchmark_runner, "MCPServerStdio", _FakeServer)
        monkeypatch.setattr(benchmark_runner, "MCPServerSse", _FakeServer)
        monkeypatch.setattr(benchmark_runner, "TraceAnalyzer", _FakeTraceAnalyzer)
        monkeypatch.setattr("agents.add_trace_processor", lambda p: add_trace_calls.append(p))

        async def _fake_eval_rag_triad(*_args, **_kwargs):
            return _Dumpable(
                {
                    "groundedness": 0.8,
                    "context_relevance": 0.7,
                    "answer_relevance": 0.9,
                    "average": 0.8,
                }
            )

        monkeypatch.setattr(benchmark_runner, "evaluate_rag_triad", _fake_eval_rag_triad)

        async def _fake_spec_compliance(*_args, **_kwargs):
            return _Dumpable(
                {
                    "score_100": 90.0,
                    "checks": {},
                    "violations": [],
                    "allowed_sources": [],
                    "used_sources": [],
                    "unauthorized_sources": [],
                    "reasoning": "ok",
                }
            )

        monkeypatch.setattr(benchmark_runner, "evaluate_spec_compliance", _fake_spec_compliance)
        monkeypatch.setattr(
            benchmark_runner,
            "compute_score_breakdown",
            lambda **_kwargs: _Dumpable(
                {
                    "spec_compliance_100": 90.0,
                    "content_quality_100": 85.0,
                    "rag_compliance_100": 80.0,
                    "efficiency_100": 75.0,
                    "overall_100": 84.0,
                    "analysis": "Good",
                }
            ),
        )
        monkeypatch.setattr(
            benchmark_runner, "extract_raw_notes_from_report", lambda *_args: "notes"
        )
        monkeypatch.delenv("MCP_DATAPREP_URL", raising=False)

        async def _fake_eval_quality(self, _report_markdown):
            return _Dumpable(
                {
                    "judgment": "PASS",
                    "grades": {"format": "A", "grounding": "A", "agenda": "B", "usability": "A"},
                }
            )

        monkeypatch.setattr(
            benchmark_runner.BenchmarkRunner, "_evaluate_quality", _fake_eval_quality
        )

        config = SimpleNamespace(
            vector_store=SimpleNamespace(name="vs"),
            mcp=SimpleNamespace(
                server_host="100.107.87.123",
                server_port=8001,
                http_timeout_seconds=5.0,
                client_timeout_seconds=60.0,
            ),
            vector_search=SimpleNamespace(provider="openai"),
            vector_mcp=SimpleNamespace(command="uvx", args=[], client_timeout_seconds=60.0),
        )
        monkeypatch.setattr(benchmark_runner, "get_config", lambda _path: config)

        runner = benchmark_runner.BenchmarkRunner(output_dir=str(tmp_path / "bench"))
        result = await runner._run_single_evaluation(
            config_file="unused.yaml",
            syllabus="test query",
            run_dir=tmp_path / "run_1",
            vector_store_name="custom-vs",
        )

        assert len(created_servers) == 2
        assert created_servers[0].name == "FS_MCP_SERVER"
        assert created_servers[1].name == "DATAPREP_MCP_SERVER"
        assert created_servers[1].params["url"] == "http://100.107.87.123:8001/sse"
        assert created_servers[1].params["timeout"] == 5.0
        assert created_servers[0].client_session_timeout_seconds == 60.0
        assert len(add_trace_calls) == 1
        assert result["quality_result"]["judgment"] == "PASS"
        assert result["rag_triad"]["average"] == 0.8
        assert result["scores"]["overall_100"] == 84.0
        assert Path(result["report_file"]).exists()

    @pytest.mark.asyncio
    async def test_run_single_evaluation_does_not_use_vector_mcp_for_chroma(
        self, monkeypatch, tmp_path
    ):
        """Integration-style test that chroma provider stays on dataprep/vector_search path."""
        import evaluations.benchmark_runner as benchmark_runner

        created_servers = []
        entered = []

        class _FakeServer:
            def __init__(self, name, params, client_session_timeout_seconds=None):
                self.name = name
                self.params = params
                self.client_session_timeout_seconds = client_session_timeout_seconds
                created_servers.append(self)

            async def __aenter__(self):
                entered.append(self.name)
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class _Dumpable:
            def __init__(self, payload):
                self._payload = payload

            def model_dump(self):
                return self._payload

        class _FakeTraceAnalyzer:
            def __init__(self, _trace_file):
                pass

            def extract_timing(self):
                return _Dumpable(
                    {
                        "total_seconds": 1.0,
                        "phases": {
                            "knowledge_preparation": 0.2,
                            "planning": 0.2,
                            "search": 0.3,
                            "writing": 0.3,
                        },
                    }
                )

            def extract_agent_calls(self):
                return _Dumpable(
                    {
                        "knowledge_preparation_agent": 1,
                        "file_planner_agent": 1,
                        "file_search_agent": 1,
                        "writer_agent": 1,
                        "total": 4,
                        "failures": 0,
                    }
                )

        class _FakeManager:
            async def run(self, **kwargs):
                output_dir = Path(kwargs["research_info"].output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "report.md").write_text(
                    "## Raw Notes\nnotes\n\n## Report\nok", encoding="utf-8"
                )

        fake_manager_module = ModuleType("agentic_research.deep_research_manager")
        fake_manager_module.DeepResearchManager = _FakeManager
        monkeypatch.setitem(
            sys.modules, "agentic_research.deep_research_manager", fake_manager_module
        )

        monkeypatch.setattr(benchmark_runner, "MCPServerStdio", _FakeServer)
        monkeypatch.setattr(benchmark_runner, "MCPServerSse", _FakeServer)
        monkeypatch.setattr(benchmark_runner, "TraceAnalyzer", _FakeTraceAnalyzer)
        monkeypatch.setattr("agents.add_trace_processor", lambda *_args, **_kwargs: None)

        async def _fake_eval_rag_triad(*_args, **_kwargs):
            return _Dumpable(
                {
                    "groundedness": 0.7,
                    "context_relevance": 0.7,
                    "answer_relevance": 0.7,
                    "average": 0.7,
                }
            )

        monkeypatch.setattr(benchmark_runner, "evaluate_rag_triad", _fake_eval_rag_triad)

        async def _fake_spec_compliance(*_args, **_kwargs):
            return _Dumpable(
                {
                    "score_100": 80.0,
                    "checks": {},
                    "violations": [],
                    "allowed_sources": [],
                    "used_sources": [],
                    "unauthorized_sources": [],
                    "reasoning": "ok",
                }
            )

        monkeypatch.setattr(benchmark_runner, "evaluate_spec_compliance", _fake_spec_compliance)
        monkeypatch.setattr(
            benchmark_runner,
            "compute_score_breakdown",
            lambda **_kwargs: _Dumpable(
                {
                    "spec_compliance_100": 80.0,
                    "content_quality_100": 82.0,
                    "rag_compliance_100": 70.0,
                    "efficiency_100": 90.0,
                    "overall_100": 79.6,
                    "analysis": "Mixed",
                }
            ),
        )
        monkeypatch.setattr(
            benchmark_runner, "extract_raw_notes_from_report", lambda *_args: "notes"
        )
        monkeypatch.setenv("MCP_DATAPREP_URL", "http://override:9001/sse")

        async def _fake_eval_quality(self, _report_markdown):
            return _Dumpable(
                {
                    "judgment": "PASS",
                    "grades": {"format": "A", "grounding": "B", "agenda": "A", "usability": "A"},
                }
            )

        monkeypatch.setattr(
            benchmark_runner.BenchmarkRunner, "_evaluate_quality", _fake_eval_quality
        )

        config = SimpleNamespace(
            vector_store=SimpleNamespace(name="vs"),
            mcp=SimpleNamespace(
                server_host="100.107.87.123",
                server_port=8001,
                http_timeout_seconds=5.0,
                client_timeout_seconds=60.0,
            ),
            vector_search=SimpleNamespace(provider="chroma"),
            vector_mcp=SimpleNamespace(
                command="uvx", args=["chroma-mcp"], client_timeout_seconds=60.0
            ),
        )
        monkeypatch.setattr(benchmark_runner, "get_config", lambda _path: config)

        runner = benchmark_runner.BenchmarkRunner(output_dir=str(tmp_path / "bench"))
        result = await runner._run_single_evaluation(
            config_file="unused.yaml",
            syllabus="test query",
            run_dir=tmp_path / "run_2",
            vector_store_name="custom-vs",
        )

        assert len(created_servers) == 2
        assert created_servers[1].params["url"] == "http://override:9001/sse"
        assert "VECTOR_MCP_SERVER" not in entered
        assert result["rag_triad"]["average"] == 0.7
        assert result["scores"]["overall_100"] == pytest.approx(79.6)

    @pytest.mark.integration
    def test_remote_services_healthcheck(self):
        """
        Optional remote integration healthcheck.

        Enable with:
        RUN_REMOTE_BENCHMARK_INTEGRATION=1
        """
        if os.getenv("RUN_REMOTE_BENCHMARK_INTEGRATION") != "1":
            pytest.skip("Set RUN_REMOTE_BENCHMARK_INTEGRATION=1 to run remote checks")

        host = os.getenv("BENCHMARK_REMOTE_HOST", "gx10-957b")

        # DataPrep MCP SSE endpoint must be reachable and speak event-stream.
        conn = HTTPConnection(host, 8001, timeout=5)
        conn.request("GET", "/sse")
        resp = conn.getresponse()
        assert resp.status == 200
        assert "text/event-stream" in (resp.getheader("content-type") or "")
        resp.close()
        conn.close()

        # Chroma heartbeat endpoint should return 200 and include heartbeat payload.
        conn = HTTPConnection(host, 8000, timeout=5)
        conn.request("GET", "/api/v2/heartbeat")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", errors="replace")
        assert resp.status == 200
        assert "heartbeat" in body.lower()
        conn.close()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_remote_chroma_mcp_query_documents(self):
        """
        Optional remote integration check for Chroma MCP query.

        Enable with:
        RUN_REMOTE_BENCHMARK_INTEGRATION=1
        """
        if os.getenv("RUN_REMOTE_BENCHMARK_INTEGRATION") != "1":
            pytest.skip("Set RUN_REMOTE_BENCHMARK_INTEGRATION=1 to run remote checks")

        host = os.getenv("BENCHMARK_REMOTE_HOST", "gx10-957b")
        query_text = os.getenv("BENCHMARK_REMOTE_QUERY", "Maximum Inner Product Search")
        collection_name = os.getenv("BENCHMARK_REMOTE_COLLECTION", "agentic-research-dgx")

        args = [
            "--python",
            "3.12",
            "chroma-mcp",
            "--client-type",
            "http",
            "--host",
            host,
            "--port",
            "8000",
            "--ssl",
            "false",
        ]
        if os.getenv("BENCHMARK_USE_UVX_QUIET", "1") == "1":
            args.insert(0, "--quiet")

        mcp_server = MCPServerStdio(
            name="CHROMA_MCP_SERVER",
            params={
                "command": "uvx",
                "args": args,
                "env": dict(os.environ),
            },
            client_session_timeout_seconds=60.0,
            cache_tools_list=True,
        )

        async with mcp_server:
            tools = await mcp_server.list_tools()
            tool_names = {tool.name for tool in tools}
            assert "chroma_query_documents" in tool_names

            result = await mcp_server.call_tool(
                "chroma_query_documents",
                {
                    "collection_name": collection_name,
                    "query_texts": [query_text],
                    "n_results": 3,
                    "include": ["documents", "metadatas", "distances"],
                },
            )

            assert not result.isError
            assert result.content, "Expected non-empty MCP response content"

            text_parts = [getattr(item, "text", "") for item in result.content]
            output_text = "\n".join(part for part in text_parts if part)
            assert "Error executing tool" not in output_text


class TestBenchmarkRunnerHelpers:
    """Test pure helper methods from benchmark runner."""

    def test_detect_outliers(self):
        from evaluations.benchmark_runner import BenchmarkRunner

        runner = BenchmarkRunner()
        outliers = runner._detect_outliers(
            [
                {"timing": {"total_seconds": 100.0}},
                {"timing": {"total_seconds": 110.0}},
                {"timing": {"total_seconds": 300.0}},
            ],
            threshold=1.5,
        )
        assert outliers == [2]

    def test_compute_average(self):
        from evaluations.benchmark_runner import BenchmarkRunner

        runner = BenchmarkRunner()
        avg = runner._compute_average(
            [
                {
                    "timing": {
                        "total_seconds": 10.0,
                        "phases": {
                            "knowledge_preparation": 1.0,
                            "planning": 2.0,
                            "search": 3.0,
                            "writing": 4.0,
                        },
                    },
                    "agent_calls": {
                        "knowledge_preparation_agent": 1,
                        "file_planner_agent": 1,
                        "file_search_agent": 2,
                        "writer_agent": 1,
                        "total": 5,
                        "failures": 0,
                    },
                    "rag_triad": {
                        "groundedness": 0.9,
                        "context_relevance": 0.8,
                        "answer_relevance": 0.7,
                        "average": 0.8,
                    },
                    "scores": {
                        "spec_compliance_100": 90.0,
                        "content_quality_100": 88.0,
                        "rag_compliance_100": 80.0,
                        "efficiency_100": 85.0,
                        "overall_100": 86.0,
                        "analysis": "Good",
                    },
                },
                {
                    "timing": {
                        "total_seconds": 20.0,
                        "phases": {
                            "knowledge_preparation": 2.0,
                            "planning": 4.0,
                            "search": 6.0,
                            "writing": 8.0,
                        },
                    },
                    "agent_calls": {
                        "knowledge_preparation_agent": 2,
                        "file_planner_agent": 1,
                        "file_search_agent": 3,
                        "writer_agent": 1,
                        "total": 7,
                        "failures": 1,
                    },
                    "rag_triad": {
                        "groundedness": 0.6,
                        "context_relevance": 0.7,
                        "answer_relevance": 0.8,
                        "average": 0.7,
                    },
                    "scores": {
                        "spec_compliance_100": 70.0,
                        "content_quality_100": 72.0,
                        "rag_compliance_100": 70.0,
                        "efficiency_100": 75.0,
                        "overall_100": 71.6,
                        "analysis": "Mixed",
                    },
                },
            ]
        )

        assert avg["timing"]["total_seconds"] == pytest.approx(15.0)
        assert avg["timing"]["phases"]["search"] == pytest.approx(4.5)
        assert avg["agent_calls"]["total"] == pytest.approx(6.0)
        assert avg["rag_triad"]["average"] == pytest.approx(0.75)
        assert avg["scores"]["overall_100"] == pytest.approx(78.8)

    def test_select_runs_for_average_drop_worst(self):
        from evaluations.benchmark_runner import BenchmarkRunner

        runner = BenchmarkRunner()
        runs = [
            {"timing": {"total_seconds": 30.0}},
            {"timing": {"total_seconds": 10.0}},
            {"timing": {"total_seconds": 20.0}},
        ]

        selected, dropped = runner._select_runs_for_average(
            runs, report_warmup=False, drop_worst_run=True
        )

        assert selected == [1, 2]
        assert dropped == 0

    def test_select_runs_for_average_warmup_and_drop_worst(self):
        from evaluations.benchmark_runner import BenchmarkRunner

        runner = BenchmarkRunner()
        runs = [
            {"timing": {"total_seconds": 50.0}},
            {"timing": {"total_seconds": 12.0}},
            {"timing": {"total_seconds": 18.0}},
        ]

        selected, dropped = runner._select_runs_for_average(
            runs, report_warmup=True, drop_worst_run=True
        )

        assert selected == [1]
        assert dropped == 2

    def test_select_runs_for_average_warmup_single_run(self):
        from evaluations.benchmark_runner import BenchmarkRunner

        runner = BenchmarkRunner()
        runs = [{"timing": {"total_seconds": 50.0}}]

        selected, dropped = runner._select_runs_for_average(
            runs, report_warmup=True, drop_worst_run=False
        )

        assert selected == [0]
        assert dropped is None

    def test_runner_uses_supported_trace_processor_api(self):
        import evaluations.benchmark_runner as benchmark_runner

        source = inspect.getsource(benchmark_runner.BenchmarkRunner._run_single_evaluation)
        assert "install_trace_processor" not in source
        assert "add_trace_processor" in source

    def test_runner_does_not_create_vector_mcp_server(self):
        import evaluations.benchmark_runner as benchmark_runner

        source = inspect.getsource(benchmark_runner.BenchmarkRunner._run_single_evaluation)
        assert "_build_vector_mcp_server" not in source

    def test_fs_server_params_restrict_to_runtime_dirs(self, tmp_path):
        import evaluations.benchmark_runner as benchmark_runner

        runner = benchmark_runner.BenchmarkRunner(output_dir=str(tmp_path / "bench"))
        config = SimpleNamespace(data=SimpleNamespace(local_storage_dir="data"))
        params = runner._build_fs_server_params(
            temp_dir=str(tmp_path / "tmp"),
            output_dir=str(tmp_path / "out"),
            config=config,
        )

        args = params["args"]
        assert params["command"] == "npx"
        assert str(tmp_path / "tmp") in args
        assert str(tmp_path / "out") in args
        assert str(Path.cwd()) not in args
        assert str(Path.cwd() / "data") not in args

    def test_normalize_runtime_paths_returns_realpaths(self, tmp_path):
        import os

        from evaluations.benchmark_runner import BenchmarkRunner

        runner = BenchmarkRunner()

        temp_input = tmp_path / "tmp"
        out_input = tmp_path / "out"
        temp_input.mkdir()
        out_input.mkdir()

        temp_dir, output_dir = runner._normalize_runtime_paths(str(temp_input), str(out_input))

        assert temp_dir == os.path.realpath(str(temp_input))
        assert output_dir == os.path.realpath(str(out_input))


class TestBenchmarkComparator:
    """Test benchmark comparison generation."""

    def test_compare_writes_markdown(self, tmp_path):
        from evaluations.benchmark_comparator import BenchmarkComparator

        run_dir = tmp_path / "run_20260211_143022"
        setup_a = run_dir / "setup-a"
        setup_b = run_dir / "setup-b"
        setup_a.mkdir(parents=True)
        setup_b.mkdir(parents=True)

        benchmark_a = {
            "timestamp": "2026-02-11T14:30:22",
            "setup_metadata": {"setup_name": "setup-a"},
            "runs": [
                {
                    "quality_result": {
                        "judgment": "PASS",
                        "grades": {
                            "format": "A",
                            "grounding": "B",
                            "agenda": "A",
                            "usability": "B",
                        },
                    }
                }
            ],
            "average": {
                "timing": {
                    "total_seconds": 12.0,
                    "phases": {
                        "knowledge_preparation": 2.0,
                        "planning": 2.0,
                        "search": 4.0,
                        "writing": 4.0,
                    },
                },
                "agent_calls": {"total": 10},
                "rag_triad": {
                    "groundedness": 0.8,
                    "context_relevance": 0.7,
                    "answer_relevance": 0.9,
                    "average": 0.8,
                },
            },
        }
        benchmark_b = {
            "timestamp": "2026-02-11T14:30:22",
            "setup_metadata": {"setup_name": "setup-b"},
            "runs": [
                {
                    "quality_result": {
                        "judgment": "FAIL",
                        "grades": {
                            "format": "C",
                            "grounding": "D",
                            "agenda": "C",
                            "usability": "C",
                        },
                    }
                }
            ],
            "average": {
                "timing": {
                    "total_seconds": 20.0,
                    "phases": {
                        "knowledge_preparation": 4.0,
                        "planning": 4.0,
                        "search": 6.0,
                        "writing": 6.0,
                    },
                },
                "agent_calls": {"total": 14},
                "rag_triad": {
                    "groundedness": 0.5,
                    "context_relevance": 0.5,
                    "answer_relevance": 0.6,
                    "average": 0.533,
                },
            },
        }

        (setup_a / "benchmark_result.json").write_text(json.dumps(benchmark_a), encoding="utf-8")
        (setup_b / "benchmark_result.json").write_text(json.dumps(benchmark_b), encoding="utf-8")

        comparator = BenchmarkComparator(str(run_dir))
        markdown = comparator.compare()

        assert "# Benchmark Comparison Report" in markdown
        assert "setup-a" in markdown
        assert "setup-b" in markdown
        assert (run_dir / "comparison_table.md").exists()


class TestBenchmarkConfig:
    """Test benchmark config parsing and defaults."""

    def test_load_benchmark_config(self, tmp_path):
        from evaluations.benchmark_config import load_benchmark_config

        config_path = tmp_path / "benchmark.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "benchmark:",
                    "  runs: 4",
                    "  output_dir: benchmarks",
                    "  syllabus_file: test_files/query_advanced_1.md",
                    "  config_file: configs/config-docker-dgx.yaml",
                    "  vector_store_name: agentic-research-dgx",
                    "  timeout_seconds: 120",
                    "  report_warmup: true",
                    "  drop_worst_run: true",
                    "  keep_services: true",
                    "  models:",
                    "    - mistralai",
                    "    - qwen",
                ]
            ),
            encoding="utf-8",
        )

        config = load_benchmark_config(str(config_path))

        assert config.runs == 4
        assert config.output_dir == "benchmarks"
        assert config.syllabus_file == "test_files/query_advanced_1.md"
        assert config.config_file == "configs/config-docker-dgx.yaml"
        assert config.vector_store_name == "agentic-research-dgx"
        assert config.timeout_seconds == 120
        assert config.report_warmup is True
        assert config.drop_worst_run is True
        assert config.keep_services is True
        assert config.models == ["mistralai", "qwen"]
