"""
Unit tests for benchmark framework components

Run with: pytest tests/test_benchmark_components.py -v
"""

import os
import tempfile
from pathlib import Path

import pytest


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
            "LLM_INSTRUCT_MODEL_PATH=/path/to/model-Q4_K_M.gguf\n"
            "LLM_INSTRUCT_CTX_SIZE=32768\n"
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


class TestTraceAnalyzer:
    """Test trace analysis logic."""

    def test_parse_empty_trace(self, tmp_path):
        """Test parsing empty trace file."""
        from evaluations.trace_analyzer import TraceAnalyzer

        trace_file = tmp_path / "trace.json"
        trace_file.write_text('{"version": "1.0", "traces": []}')

        analyzer = TraceAnalyzer(str(trace_file))
        timing = analyzer.extract_timing()

        assert timing.total_duration == 0.0
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
        import json

        trace_file.write_text(json.dumps(trace_data))

        analyzer = TraceAnalyzer(str(trace_file))
        timing = analyzer.extract_timing()

        assert timing.total_duration == 300.0  # 5 minutes
        assert timing.phases["knowledge_preparation"] > 0


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
            total_duration=300.0,
            phases={
                "knowledge_preparation": 60.0,
                "planning": 30.0,
                "search": 120.0,
                "writing": 90.0,
            },
        )
        assert result.total_duration == 300.0
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
