from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from evaluations.deterministic_grade import (
    extract_numbers,
    grade,
    parse_tables,
    table_cells,
    to_float,
)


def _write_exercise(tmp_path: Path, *, mode: str = "numeric") -> Path:
    exercise = tmp_path / "exercise"
    corpus = exercise / "corpus"
    corpus.mkdir(parents=True)
    (corpus / "capex_reference_data.md").write_text("Apple revenue was 416.2B.\n", encoding="utf-8")
    (corpus / "key_metrics.csv").write_text(
        "Company,FYE_basis,Metric,FiscalYear,Value,Unit\n"
        "Apple,Sep,Revenue,FY2025,416.2,USD_billions\n",
        encoding="utf-8",
    )
    answer_key = {
        "mode": mode,
        "theme": "test",
        "companies_in_scope": ["Apple"] if mode == "numeric" else [],
        "must_cover": (
            []
            if mode == "numeric"
            else [
                {"id": "agent_memory", "concept": "agent memory", "anchors_any": ["agent memory"]}
            ]
        ),
        "distractors": {},
    }
    if mode == "conceptual":
        answer_key["mode"] = "conceptual"
    (exercise / "answer_key.yaml").write_text(yaml.safe_dump(answer_key), encoding="utf-8")
    (exercise / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "required_chapters": [],
                "embedded_tables": {"required": False, "min_tables": 0},
                "length": {"min_words": 20, "max_words": 200},
                "scoring": {"axes": {"coverage": {"weight": 0.8}, "format": {"weight": 0.2}}},
            }
        ),
        encoding="utf-8",
    )
    return exercise


def test_grade_root_cause_requires_company_and_metric_context(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    report_md = "# Overview\nNo Apple revenue figure is provided here.\n"
    sources = [
        {
            "source_id": "S1",
            "file_name": "alphabet_summary.txt",
            "topic": "Alphabet revenue summary",
            "content": "Alphabet revenue reached 416.2B in FY2025.",
        }
    ]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["root_cause"]["missing_not_retrieved"] == ["Apple Revenue"]
    assert result["root_cause"]["missing_retrieved_but_absent_from_report"] == []
    assert result["root_cause"]["verdict"] == (
        "search/retrieval: required items were not retrieved into the corpus"
    )


def test_grade_root_cause_marks_retrieved_but_omitted_items(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    report_md = "# Overview\nNo table yet.\n"
    sources = [
        {
            "source_id": "S1",
            "file_name": "apple_summary.txt",
            "topic": "Apple revenue summary",
            "content": "Apple revenue reached 416.2B in FY2025.",
        }
    ]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["root_cause"]["missing_not_retrieved"] == []
    assert result["root_cause"]["missing_retrieved_but_absent_from_report"] == ["Apple Revenue"]
    assert (
        result["root_cause"]["verdict"]
        == "writer/agenda: items were retrieved but omitted from the report"
    )


def test_grade_flags_fabricated_number_inside_heading(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    report_md = (
        "# Overview\n"
        "## Apple Revenue 999.9B\n"
        "| Company | Metric | Period | Value |\n"
        "| --- | --- | --- | --- |\n"
        "| Apple | Revenue | FY2025 | 416.2 |\n"
    )
    sources = [
        {
            "source_id": "S1",
            "file_name": "apple_summary.txt",
            "topic": "Apple revenue summary",
            "content": "Apple revenue reached 416.2B in FY2025.",
        }
    ]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 1
    assert result["fabrication"]["items"][0]["value"] == 999.9


def test_number_parser_preserves_signs_and_locale() -> None:
    assert to_float("1,234.5") == 1234.5
    assert to_float("1.234,5") == 1234.5
    assert to_float("1\u202f234,5") == 1234.5
    assert [value for value, _unit, _pos in extract_numbers("-$14.7B and -$16.9B")] == [
        -14.7,
        -16.9,
    ]


def test_number_parser_propagates_range_units_and_normalizes_bps() -> None:
    assert [(value, unit) for value, unit, _pos in extract_numbers("$72\u201375B")] == [
        (72.0, "b"),
        (75.0, "b"),
    ]
    assert [(value, unit) for value, unit, _pos in extract_numbers("56\u201394%")] == [
        (56.0, "%"),
        (94.0, "%"),
    ]
    assert [(value, unit) for value, unit, _pos in extract_numbers("100 basis points")] == [
        (1.0, "%")
    ]
    assert [value for value, _unit, _pos in extract_numbers("\u2212$14.7B")] == [-14.7]


def test_table_cells_parse_canonical_long_format_and_small_integer() -> None:
    report_md = (
        "| Company | Metric | Period | Value |\n"
        "| --- | --- | --- | --- |\n"
        "| Apple | Revenue | FY2025 | 416.2 |\n"
        "| Apple | Capex/OCF | FY2025 | 11 |\n"
        "| Apple | FCF | FY2025 | (16.9) [S2] |\n"
    )

    assert table_cells(parse_tables(report_md), ["Apple"]) == [
        ("Apple", "Revenue", "FY2025", 416.2),
        ("Apple", "Capex/OCF", "FY2025", 11.0),
        ("Apple", "FCF", "FY2025", -16.9),
    ]


def test_table_cells_parse_combined_operating_income_and_margin() -> None:
    report_md = (
        "| Company | Period | Operating income (margin) |\n"
        "| --- | --- | --- |\n"
        "| Amazon | FY2025 | $80.0B (11.2%) |\n"
    )

    assert table_cells(parse_tables(report_md), ["Amazon"]) == [
        ("Amazon", "Operating income", "FY2025", 80.0),
        ("Amazon", "Operating margin", "FY2025", 11.2),
    ]


def test_grade_uses_period_for_table_accuracy(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    corpus = exercise / "corpus" / "key_metrics.csv"
    corpus.write_text(
        corpus.read_text(encoding="utf-8") + "Apple,Sep,Revenue,FY2024,391.0,USD_billions\n",
        encoding="utf-8",
    )
    report_md = (
        "| Company | Metric | Period | Value |\n"
        "| --- | --- | --- | --- |\n"
        "| Apple | Revenue | FY2025 | 391.0 |\n"
    )

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["accuracy"]["wrong"] == 1
    assert result["accuracy"]["wrong_details"] == ["Apple Revenue: report=391.0 vs corpus=416.2"]


def test_grade_ignores_styled_section_number_but_not_heading_claim(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    report_md = "### **3.1. Overview**\n### **3.2. Apple Revenue 999.9B**\n"

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["fabrication"]["count"] == 1
    assert result["fabrication"]["items"][0]["value"] == 999.9


def test_grade_scores_declared_length_constraint(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path, mode="conceptual")
    report_md = "Agent memory [S1] " + "word " * 205
    sources = [{"source_id": "S1", "content": "Agent memory retains prior context."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["coverage"]["pct"] == 1.0
    assert result["format"]["word_count"] == 208
    assert result["score"] == 80.0


def test_conceptual_number_must_exist_in_cited_source(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path, mode="conceptual")
    (exercise / "corpus" / "article.md").write_text(
        "Another section mentions 500 tokens and a 20% rate.\n",
        encoding="utf-8",
    )
    report_md = "Agent memory uses chunks of 200-500 tokens with 20% overlap [S1].\n"
    sources = [
        {
            "source_id": "S1",
            "file_name": "memory.md",
            "topic": "Agent memory",
            "content": "Agent memory stores prior interactions without fixed chunk sizes.",
        }
    ]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert [item["value"] for item in result["fabrication"]["items"]] == [200.0, 500.0, 20.0]


def test_derivation_uses_claimed_company_metric_and_periods(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    (exercise / "answer_key.yaml").write_text(
        yaml.safe_dump(
            {
                "theme": "test",
                "companies_in_scope": ["Amazon"],
                "must_cover": [],
                "distractors": {},
            }
        ),
        encoding="utf-8",
    )
    (exercise / "corpus" / "key_metrics.csv").write_text(
        "Company,FYE_basis,Metric,FiscalYear,Value,Unit\n"
        "Amazon,Dec,Capex,FY2020,40.1,USD_billions\n"
        "Amazon,Dec,Capex,FY2023,52.7,USD_billions\n"
        "Amazon,Dec,Capex,FY2025,131.8,USD_billions\n"
        "NVIDIA,Jan,Capex,FY2025,3.2,USD_billions\n",
        encoding="utf-8",
    )
    report_md = (
        "Amazon capex grew from $40.1B in FY2020 to $52.7B in FY2023 and $131.8B in FY2025. "
        "This is a 3.3\u00d7 increase from FY2023 to FY2025 and a 228% rise from FY2020 to FY2025.\n"
    )

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert [item["value"] for item in result["fabrication"]["items"]] == [3.3]


def test_false_latest_year_unavailability_is_accuracy_error(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    report_md = "Apple FY2025 revenue is unavailable in the sources.\n"

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["accuracy"]["wrong"] == 1
    assert result["accuracy"]["wrong_details"] == [
        "Apple Revenue: report says unavailable for FY2025"
    ]
    assert result["score"] <= 60.0


def test_historical_unavailability_does_not_contradict_latest_fact(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    report_md = "Apple FY2024 revenue is unavailable in the sources.\n"

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["accuracy"]["wrong"] == 0


def test_sources_section_does_not_satisfy_concept_coverage(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path, mode="conceptual")
    report_md = "# Empty report\n\n## Sources\n- agent memory — memory.md\n"

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["coverage"]["hit"] == 0


def test_keyword_list_does_not_satisfy_concept_coverage(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path, mode="conceptual")
    report_md = "# Terms\n\nagent memory\n"

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["coverage"]["hit"] == 0


def test_explanation_with_unknown_citation_does_not_cover_concept(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path, mode="conceptual")
    report_md = "Agent memory [S99] " + "word " * 30

    result = grade(
        tmp_path / "run", exercise, report_md, [{"source_id": "S1", "content": "memory"}]
    )

    assert result["coverage"]["hit"] == 0


def test_conceptual_citations_support_chunk_and_multi_source_formats(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path, mode="conceptual")
    report_md = (
        "Agent memory keeps relevant context with a documented 20% overlap [S1:4].\n"
        "Agent memory can also use a documented 90.2% result [S1, S2].\n"
    )
    sources = [
        {"source_id": "S1", "content": "The documented overlap is 20%."},
        {"source_id": "S2", "content": "The measured result was 90.2%."},
    ]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 0


def test_unavailability_company_context_resets_at_new_heading(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    report_md = "**Apple**\n\n## General limitations\nRevenue is unavailable.\n"

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["accuracy"]["wrong"] == 0


def test_unavailability_clause_is_attributed_to_named_company_only(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    report_md = "Amazon is complete; Apple FY2025 revenue is unavailable.\n"

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["accuracy"]["wrong_details"] == [
        "Apple Revenue: report says unavailable for FY2025"
    ]


def test_prose_fact_cannot_reuse_another_company_value(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    (exercise / "corpus" / "other_company.md").write_text(
        "Alphabet revenue was 402.8B.\n",
        encoding="utf-8",
    )
    report_md = "Apple FY2025 revenue was 402.8B.\n"

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert [item["value"] for item in result["fabrication"]["items"]] == [402.8]


def test_correct_prose_fact_remains_grounded(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    report_md = "Apple FY2025 revenue was 416.2B.\n"

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["fabrication"]["count"] == 0


def _finance_exercise() -> Path:
    return Path(__file__).parents[1] / "evaluations" / "exercises" / "ai-capex-intensity"


def _fy2025_table(metrics: set[str] | None = None) -> str:
    csv_path = _finance_exercise() / "corpus" / "key_metrics.csv"
    rows = [
        row
        for row in csv.DictReader(csv_path.open(encoding="utf-8"))
        if row["FiscalYear"] == "FY2025" and (metrics is None or row["Metric"] in metrics)
    ]
    lines = [
        "| Company | Metric | Period | Value |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {row['Company']} | {row['Metric']} | {row['FiscalYear']} | {row['Value']} |"
        for row in rows
    )
    return "\n".join(lines)


def test_finance_contract_requires_all_42_latest_facts(tmp_path: Path) -> None:
    report = _fy2025_table({"Revenue", "Operating margin", "Capex", "Capex/OCF"})

    result = grade(tmp_path / "run", _finance_exercise(), report, [])

    assert result["coverage"] == {"hit": 24, "total": 42, "pct": 0.571}
    assert result["qualified"] is False
    assert (
        "Amazon Operating income FY2025" in result["qualification"]["critical_requirement_failures"]
    )


def test_finance_contract_has_a_reachable_qualified_reference(tmp_path: Path) -> None:
    report = "\n\n".join(
        [
            "# Overview and Definitions\n"
            "Free cash flow (FCF) is operating cash flow minus capex; capex intensity "
            "is the capex/OCF ratio expressed as a percentage. Fiscal-year ends differ "
            "for Amazon, Alphabet, Meta, Microsoft, NVIDIA, and Apple.",
            "# FY2025 Profitability\nThe requested reported profitability facts follow.",
            "# FY2025 Capex and Cash Generation\n" + _fy2025_table(),
            "# Capex Trends\nEach capex trend is described from FY2020 to FY2025 as "
            "rising, declining, or stable using the supplied endpoints.",
            "# Guidance vs Actuals\nGuidance is kept separate from each reported actual. "
            "Its basis must be comparable; Meta is explicitly not like-for-like.",
            "# Cross-Company Comparison\nThe table provides the factual comparison.",
            "# Data Gaps\nNo required actual is missing from the provided source corpus. "
            "Unavailable guidance remains a source data gap and is not estimated.",
            "# Notes\n" + "Factual context remains limited to the supplied corpus. " * 55,
        ]
    )

    result = grade(tmp_path / "run", _finance_exercise(), report, [])

    assert result["coverage"]["hit"] == 42
    assert result["accuracy"]["wrong"] == 0
    assert result["fabrication"]["count"] == 0
    assert result["qualified"] is True


def test_number_that_looks_like_year_but_has_unit_is_checked(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)

    result = grade(tmp_path / "run", exercise, "Apple FY2025 revenue was $2025B.\n", [])

    assert [item["value"] for item in result["fabrication"]["items"]] == [2025.0]


def test_wrong_direct_fact_cannot_be_rescued_as_derivation(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    corpus = exercise / "corpus" / "key_metrics.csv"
    corpus.write_text(
        corpus.read_text(encoding="utf-8") + "Apple,Sep,Revenue,FY2024,391.0,USD_billions\n",
        encoding="utf-8",
    )
    report = (
        "Apple FY2025 revenue was $391.0B. Other supplied values were $416.2B and $25.2B, "
        "whose difference is $391.0B.\n"
    )

    result = grade(tmp_path / "run", exercise, report, [])

    assert any(item["value"] == 391.0 for item in result["fabrication"]["items"])


def test_correct_derivation_can_use_operands_in_previous_sentence(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    (exercise / "answer_key.yaml").write_text(
        yaml.safe_dump({"theme": "test", "companies_in_scope": ["Amazon"], "distractors": {}}),
        encoding="utf-8",
    )
    (exercise / "corpus" / "key_metrics.csv").write_text(
        "Company,FYE_basis,Metric,FiscalYear,Value,Unit\n"
        "Amazon,Dec,Capex,FY2020,40.1,USD_billions\n"
        "Amazon,Dec,Capex,FY2025,131.8,USD_billions\n",
        encoding="utf-8",
    )
    report = (
        "Amazon capex was $40.1B in FY2020 and $131.8B in FY2025. "
        "That is a 228.7% increase over the period.\n"
    )

    result = grade(tmp_path / "run", exercise, report, [])

    assert result["fabrication"]["count"] == 0


def test_concept_keywords_and_unrelated_citation_do_not_pass(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path, mode="conceptual")
    answer_key = yaml.safe_load((exercise / "answer_key.yaml").read_text(encoding="utf-8"))
    answer_key["must_cover"][0]["semantic_groups"] = [["persistent"], ["history"]]
    (exercise / "answer_key.yaml").write_text(yaml.safe_dump(answer_key), encoding="utf-8")
    report = "Agent memory " + "unrelated keyword " * 15 + "[S1]\n"

    result = grade(
        tmp_path / "run", exercise, report, [{"source_id": "S1", "content": "unrelated"}]
    )

    assert result["coverage"]["hit"] == 0
    assert result["qualified"] is False


def test_concept_source_provenance_rejects_summary_without_doc_ids(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path, mode="conceptual")
    answer_key = yaml.safe_load((exercise / "answer_key.yaml").read_text(encoding="utf-8"))
    answer_key["require_source_provenance"] = True
    answer_key["must_cover"][0]["source_files"] = ["Agents"]
    (exercise / "answer_key.yaml").write_text(yaml.safe_dump(answer_key), encoding="utf-8")
    report = "Agent memory preserves persistent conversation history for later tasks [S1].\n"

    result = grade(
        tmp_path / "run",
        exercise,
        report,
        [{"source_id": "S1", "content": report, "doc_ids": []}],
    )

    assert result["coverage"]["hit"] == 0


def test_numeric_contract_fails_loudly_when_period_is_stale(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    answer_key = yaml.safe_load((exercise / "answer_key.yaml").read_text(encoding="utf-8"))
    answer_key["numeric_requirements"] = {
        "require_latest": True,
        "metrics": ["Revenue"],
        "periods": {"Apple": "FY2024"},
    }
    (exercise / "answer_key.yaml").write_text(yaml.safe_dump(answer_key), encoding="utf-8")

    with pytest.raises(ValueError, match="contract period 'FY2024' differs"):
        grade(tmp_path / "run", exercise, "", [])


def test_grade_records_reproducibility_hashes(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)

    result = grade(tmp_path / "run", exercise, "", [])

    assert set(result["provenance"]) >= {
        "scorer_sha256",
        "answer_key_sha256",
        "spec_sha256",
        "corpus_sha256",
        "report_sha256",
        "sources_sha256",
    }
    assert all(len(value) == 64 for value in result["provenance"].values())


def test_finance_manifest_matches_committed_corpus() -> None:
    corpus = _finance_exercise() / "corpus"
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))

    for file_name, expected_hash in manifest["generated_files"].items():
        assert hashlib.sha256((corpus / file_name).read_bytes()).hexdigest() == expected_hash
