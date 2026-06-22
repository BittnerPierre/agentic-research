"""Tests for the spike comparison table (issue #196)."""

import json

from evaluations.spike_compare import _find_stats_files, build_table


def _stats(strategy, total, writing, concurrency=None, coverage=None):
    return {
        "config_name": "spark1-decomposed",
        "writer_strategy": strategy,
        "success": True,
        "models": {"writer": "Mistral-Small-4@spark1"},
        "timings": {"total": total, "writing": writing},
        "agent_calls": {"total": 7, "failures": 0},
        "n_sources": 5,
        "derived": {"writing_throughput_tok_s": 42.0},
        "writer_metrics": {
            "concurrency_ratio": concurrency,
            "grounding": {"source_coverage": coverage},
        },
    }


def test_build_table_has_header_and_one_row_per_run():
    table = build_table(
        [_stats("monolithic", 120.0, 60.0), _stats("decomposed", 90.0, 25.0, 2.4, 0.8)]
    )
    lines = table.splitlines()

    assert lines[0].startswith("| config | strategy |")
    assert set(lines[1].replace(" ", "")) <= set("|-")  # separator row
    assert len(lines) == 4  # header + separator + 2 rows
    assert "monolithic" in lines[2]
    assert "decomposed" in lines[3]
    assert "2.40" in lines[3]  # concurrency ratio formatted
    assert "80%" in lines[3]  # source coverage formatted


def test_build_table_handles_missing_fields_gracefully():
    table = build_table([{"config_name": "x", "writer_strategy": "decomposed"}])
    # Missing metrics render as em dashes, never raise.
    assert "—" in table
    assert "decomposed" in table


def test_find_stats_files_scans_directories(tmp_path):
    run_a = tmp_path / "runs" / "a"
    run_a.mkdir(parents=True)
    (run_a / "stats.json").write_text(json.dumps(_stats("decomposed", 1.0, 1.0)), encoding="utf-8")

    found = _find_stats_files([str(tmp_path)])
    assert len(found) == 1
    assert found[0].name == "stats.json"
