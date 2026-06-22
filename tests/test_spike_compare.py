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


def test_build_table_renders_quality_columns_from_grade():
    stats = _stats("decomposed", 90.0, 25.0, 2.4, 0.8)
    stats["grade"] = {
        "rag_triad": {"average": 0.83},
        "quality": {"quality_100": 88.0},
        "spec": {"score_100": 76.0},
        "overall_quality_100": 84.0,
    }
    row = build_table([stats]).splitlines()[2]
    assert "| config | strategy |" not in row
    assert "0.83" in row  # grounded (rag avg)
    assert "88" in row  # quality
    assert "76" in row  # spec
    assert "84" in row  # q_overall


def test_find_stats_files_scans_directories(tmp_path):
    run_a = tmp_path / "runs" / "a"
    run_a.mkdir(parents=True)
    (run_a / "stats.json").write_text(json.dumps(_stats("decomposed", 1.0, 1.0)), encoding="utf-8")

    found = _find_stats_files([str(tmp_path)])
    assert len(found) == 1
    assert found[0].name == "stats.json"
