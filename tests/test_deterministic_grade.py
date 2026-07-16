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


def test_grade_treats_uncited_unsupported_heading_as_unverifiable(tmp_path: Path) -> None:
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

    assert result["fabrication"]["count"] == 0
    assert result["unverifiable"]["items"][0]["value"] == 999.9
    assert result["unverifiable"]["items"][0]["reason"] == "unsupported_uncited"


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


def test_combined_table_assists_coverage_but_never_accuses() -> None:
    # Arbitrage Pierre (2026-07-15) — « les en-têtes peuvent aider, jamais
    # accuser » : cette lecture par en-têtes fournit des claims d'ASSISTANCE
    # (crédit de couverture sur match) ; un écart via ces claims ne produit
    # jamais d'accusation (voir test_assisted_mismatch_is_not_accused).
    report_md = (
        "| Company | Period | Operating income (margin) |\n"
        "| --- | --- | --- |\n"
        "| Amazon | FY2025 | $80.0B (11.2%) |\n"
    )

    assert table_cells(parse_tables(report_md), ["Amazon"]) == [
        ("Amazon", "Operating income", "FY2025", 80.0),
        ("Amazon", "Operating margin", "FY2025", 11.2),
    ]


def test_assisted_mismatch_is_not_accused_but_content_mismatch_is(tmp_path: Path) -> None:
    # Arbitrage Pierre (2026-07-15) : un écart lu via en-têtes peut être NOTRE
    # erreur de lecture -> silence (existence seulement). Un écart dans une
    # ligne canonique auto-identifiée (contenu) reste une accusation.
    exercise = _write_exercise(tmp_path)
    header_mismatch = "| Company | Earliest revenue |\n| --- | --- |\n| Apple | 999.0 |\n"
    result = grade(tmp_path / "run", exercise, header_mismatch, [])
    assert result["accuracy"]["wrong"] == 0  # pas d'accusation via en-têtes

    canonical_mismatch = (
        "| Company | Metric | Period | Value |\n"
        "| --- | --- | --- | --- |\n"
        "| Apple | Revenue | FY2025 | 999.0 |\n"
    )
    result = grade(tmp_path / "run", exercise, canonical_mismatch, [])
    assert result["accuracy"]["wrong"] == 1  # la ligne canonique accuse


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

    assert result["fabrication"]["count"] == 0
    assert result["unverifiable"]["items"][0]["value"] == 999.9


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

    assert result["fabrication"]["count"] == 0
    assert [item["value"] for item in result["unverifiable"]["items"]] == [3.3]
    assert result["unverifiable"]["items"][0]["reason"] == "invalid_derivation"


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


def test_prose_number_existing_in_corpus_is_not_accused(tmp_path: Path) -> None:
    # Arbitrage Pierre (2026-07-15): prose numbers are checked for EXISTENCE in
    # the corpus only — mechanical company/metric/period attribution of free
    # text is gone (it produced false accusations on the reference model).
    # A corpus value reused for the wrong company in prose is an ANALYSIS error,
    # which belongs to the adequacy judge, not the number checker.
    exercise = _write_exercise(tmp_path)
    (exercise / "corpus" / "other_company.md").write_text(
        "Alphabet revenue was 402.8B.\n",
        encoding="utf-8",
    )
    report_md = "Apple FY2025 revenue was 402.8B.\n"

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["prose_contradictions"]["items"] == []
    assert result["fabrication"]["count"] == 0


def test_correct_prose_fact_remains_grounded(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    report_md = "Apple FY2025 revenue was 416.2B.\n"

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["fabrication"]["count"] == 0


def test_comparative_prose_binds_each_value_to_its_following_period(tmp_path: Path) -> None:
    exercise = _finance_exercise()
    report = (
        "Pour Alphabet, les Capex sont passes de $52.5B en FY2024 a $91.4B en FY2025, "
        "tandis que l'OCF est passe de $125.3B en FY2024 a $164.7B en FY2025 [S1].\n"
    )

    result = grade(tmp_path / "run", exercise, report, [{"source_id": "S1", "content": report}])

    assert result["prose_contradictions"]["count"] == 0
    assert result["fabrication"]["count"] == 0


def test_respective_ratios_do_not_inherit_the_last_prior_period(tmp_path: Path) -> None:
    exercise = _finance_exercise()
    report = (
        "Apple spending was $9.4B in FY2024 and $12.7B in FY2025 [S1], "
        "with capex/OCF ratios of 8% and 11% respectively [S1].\n"
    )

    result = grade(tmp_path / "run", exercise, report, [{"source_id": "S1", "content": report}])

    assert result["prose_contradictions"]["count"] == 0


def test_correct_value_with_ambiguous_metric_is_not_called_a_contradiction(tmp_path: Path) -> None:
    exercise = _finance_exercise()
    report = (
        "Alphabet grew from $182.5B in FY2020 to $402.8B in FY2025, with an operating "
        "margin near 32% and operating income of $129.0B [S1].\n"
    )

    result = grade(tmp_path / "run", exercise, report, [{"source_id": "S1", "content": report}])

    assert result["prose_contradictions"]["count"] == 0


def test_prose_metric_reuse_is_judge_territory_not_mechanical(tmp_path: Path) -> None:
    # Arbitrage Pierre (2026-07-15): 416.2 exists in the corpus (Apple revenue),
    # so the existence check passes; calling it "capex" in prose is an analysis
    # error for the adequacy judge. No mechanical accusation.
    exercise = _finance_exercise()
    report = "Apple FY2025 capex was $416.2B [S1].\n"

    result = grade(tmp_path / "run", exercise, report, [{"source_id": "S1", "content": report}])

    assert result["prose_contradictions"]["items"] == []
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


def test_finance_contract_has_a_reachable_deterministic_reference(tmp_path: Path) -> None:
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
            "Amazon guidance was about $100B on 2025-02-06; Alphabet guidance was "
            "about $75B on 2025-02-04; Meta guidance was $60B-$65B on 2025-01-29. "
            "Meta includes finance-lease principal, so its basis is explicitly not "
            "like-for-like. Initial guidance for Microsoft, NVIDIA, and Apple is "
            "unavailable and is not estimated.",
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
    assert result["qualified"] is False
    assert result["qualification"]["blockers"] == ["finance adequacy judge not run"]


def test_number_that_looks_like_year_but_has_unit_is_checked(tmp_path: Path) -> None:
    # Arbitrage Pierre (2026-07-15) — documented limitation: "$2025B" collides
    # with the year tokens present in the corpus text, so the existence check
    # passes and no mechanical accusation is raised. Prose attribution is gone;
    # this rare shape is left to the adequacy judge / human read.
    exercise = _write_exercise(tmp_path)

    result = grade(tmp_path / "run", exercise, "Apple FY2025 revenue was $2025B.\n", [])

    assert result["prose_contradictions"]["items"] == []


def test_stale_period_value_in_prose_is_judge_territory(tmp_path: Path) -> None:
    # Arbitrage Pierre (2026-07-15): 391.0 exists in the corpus (FY2024), so
    # existence passes; claiming it for FY2025 in prose is an analysis error
    # for the adequacy judge. The canonical table keeps full period authority.
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

    assert result["prose_contradictions"]["items"] == []
    assert result["fabrication"]["count"] == 0


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
    report = (
        "Agent memory preserves persistent conversation history and prior tool state so an "
        "agent can resume later tasks without losing the context needed for decisions [S1].\n"
    )

    result = grade(
        tmp_path / "run",
        exercise,
        report,
        [{"source_id": "S1", "content": report, "doc_ids": []}],
    )

    assert result["coverage"]["hit"] == 0


def test_concept_does_not_borrow_an_unrelated_citation_from_same_paragraph(
    tmp_path: Path,
) -> None:
    exercise = _write_exercise(tmp_path, mode="conceptual")
    answer_key = yaml.safe_load((exercise / "answer_key.yaml").read_text(encoding="utf-8"))
    answer_key["require_source_provenance"] = True
    answer_key["must_cover"][0]["source_files"] = ["Agents"]
    answer_key["must_cover"][0]["semantic_groups"] = [["persistent"], ["history"]]
    (exercise / "answer_key.yaml").write_text(yaml.safe_dump(answer_key), encoding="utf-8")
    report = (
        "- Agent memory preserves persistent conversation history for later tasks.\n"
        "- A separate implementation note discusses generic tools and schemas [S1].\n"
    )
    sources = [
        {
            "source_id": "S1",
            "content": "Generic tools use schemas and arguments.",
            "doc_ids": ["Agents_1.md:4"],
        }
    ]

    result = grade(tmp_path / "run", exercise, report, sources)

    assert result["coverage"]["hit"] == 0


def test_concept_provenance_resolves_short_and_prefixed_document_ids(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path, mode="conceptual")
    answer_key = yaml.safe_load((exercise / "answer_key.yaml").read_text(encoding="utf-8"))
    answer_key["require_source_provenance"] = True
    answer_key["must_cover"][0]["source_files"] = ["Agents"]
    answer_key["must_cover"][0]["semantic_groups"] = [["persistent"], ["history"]]
    (exercise / "answer_key.yaml").write_text(yaml.safe_dump(answer_key), encoding="utf-8")
    run = tmp_path / "run"
    run.mkdir()
    (run / "knowledge_db.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "vector_doc_id": "abcdef12-3456-7890-abcd-ef1234567890",
                        "filename": "Agents_1.md",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report = (
        "Agent memory preserves persistent conversation history and prior tool state so an "
        "agent can resume later tasks without losing the context needed for decisions [S1].\n"
    )
    sources = [
        {
            "source_id": "S1",
            "content": report,
            "doc_ids": ["document_id:abcdef12:4"],
        }
    ]

    result = grade(run, exercise, report, sources)

    assert result["coverage"]["hit"] == 1
    assert result["source_resolution"]["sources"] == {"S1": ["Agents_1.md"]}

    (run / "det_grade.json").write_text(json.dumps(result), encoding="utf-8")
    (run / "knowledge_db.json").unlink()
    portable_result = grade(
        run,
        exercise,
        report,
        [{"source_id": "S1", "content": report, "doc_ids": ["abcdef12:4"]}],
    )
    assert portable_result["coverage"]["hit"] == 1


def test_fixed_concept_contract_accepts_plural_embeddings_and_french_messages(
    tmp_path: Path,
) -> None:
    exercise = Path(__file__).parents[1] / "evaluations" / "exercises" / "ai-engineering-syllabus"
    report = (
        "Les messages developer définissent les règles et le comportement, tandis que les "
        "messages user fournissent les entrées et la demande utilisateur [S1].\n\n"
        "Les embeddings représentent le texte par des vecteurs numériques dans un espace "
        "sémantique où la similarité rapproche les contenus de sens voisin [S2].\n"
    )
    sources = [
        {"source_id": "S1", "content": report, "doc_ids": ["Text_generation.md:1"]},
        {
            "source_id": "S2",
            "content": report,
            "doc_ids": ["Advanced_Retrieval_for_Retrieval-Augmented_Generat_1.md:2"],
        },
    ]

    result = grade(tmp_path / "run", exercise, report, sources)
    statuses = {item["id"]: item["status"] for item in result["requirements"]}

    assert statuses["system_user_prompts"] == "pass"
    assert statuses["embeddings"] == "pass"


def test_fixed_concept_contract_accepts_explicit_known_zero_shot_gap(tmp_path: Path) -> None:
    exercise = Path(__file__).parents[1] / "evaluations" / "exercises" / "ai-engineering-syllabus"
    report = (
        "Le zero-shot n'est pas documenté dans les sources du corpus fourni; cette lacune "
        "doit être signalée plutôt que complétée depuis la mémoire du modèle [S1].\n"
    )
    sources = [{"source_id": "S1", "content": report, "doc_ids": ["Text_generation.md:1"]}]

    result = grade(tmp_path / "run", exercise, report, sources)
    statuses = {item["id"]: item["status"] for item in result["requirements"]}

    assert statuses["zero_shot"] == "pass"


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


def test_cited_unsupported_range_is_blocking_citation_laundering(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    report = (
        "| Company | Metric | Period | Value |\n"
        "| --- | --- | --- | --- |\n"
        "| Apple | Revenue | FY2025 | 416.2 |\n\n"
        "A new process reduces errors by 30-40% according to the supplied evidence [S1].\n"
    )
    sources = [{"source_id": "S1", "content": "The source discusses process quality."}]

    result = grade(tmp_path / "run", exercise, report, sources)

    assert [item["value"] for item in result["fabrication"]["items"]] == [30.0, 40.0]
    assert {item["reason"] for item in result["fabrication"]["items"]} == {"citation_laundering"}
    assert result["qualified"] is False


def test_cited_growth_language_cannot_bypass_citation_laundering(tmp_path: Path) -> None:
    exercise = _finance_exercise()
    report = "Amazon capex grew by an impressive 73% year-over-year [S3].\n"
    sources = [{"source_id": "S3", "content": "Amazon invested heavily in infrastructure."}]

    result = grade(tmp_path / "run", exercise, report, sources)

    assert [item["value"] for item in result["fabrication"]["items"]] == [73.0]
    assert result["fabrication"]["items"][0]["reason"] == "citation_laundering"
    assert result["qualified"] is False


def test_off_whitelist_prose_number_is_unverifiable_diagnostic(tmp_path: Path) -> None:
    # Arbitrage Pierre (2026-07-15): 45% exists nowhere in the corpus and is not
    # a derivation of shown operands — it fails the EXISTENCE check and lands in
    # the unverifiable diagnostic (per-item penalty, volume-capped), without a
    # mechanical company/metric attribution.
    exercise = _finance_exercise()
    report = "Apple's operating margin reached 45% in FY2025.\n"

    result = grade(tmp_path / "run", exercise, report, [])

    assert result["prose_contradictions"]["items"] == []
    assert 45.0 in [item["value"] for item in result["unverifiable"]["items"]]


def test_uncited_unsupported_range_is_diagnostic(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    report = (
        "| Company | Metric | Period | Value |\n"
        "| --- | --- | --- | --- |\n"
        "| Apple | Revenue | FY2025 | 416.2 |\n\n"
        "A new process reduces errors by 30-40% according to general commentary.\n"
    )

    result = grade(tmp_path / "run", exercise, report, [])

    assert result["fabrication"]["count"] == 0
    assert [item["value"] for item in result["unverifiable"]["items"]] == [30.0, 40.0]
    assert result["qualified"] is True


def test_unverifiable_volume_cap_blocks_gaming(tmp_path: Path) -> None:
    exercise = _write_exercise(tmp_path)
    spec = yaml.safe_load((exercise / "spec.yaml").read_text(encoding="utf-8"))
    spec["unverifiable_claims"] = {"per_item_penalty": 1, "max_for_qualification": 1}
    (exercise / "spec.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    report = (
        "| Company | Metric | Period | Value |\n"
        "| --- | --- | --- | --- |\n"
        "| Apple | Revenue | FY2025 | 416.2 |\n\n"
        "A new process reduces errors by 30-40% according to general commentary.\n"
    )

    result = grade(tmp_path / "run", exercise, report, [])

    assert result["unverifiable"]["count"] == 2
    assert "too many unverifiable numeric claims" in result["qualification"]["blockers"]
    assert result["qualified"] is False


def test_six_uncited_growth_rates_exceed_finance_volume_cap(tmp_path: Path) -> None:
    exercise = _finance_exercise()
    report = (
        "Across the sector, separate investment categories rose roughly 13.37%, 24.27%, "
        "38.53%, 49.73%, 58.37%, and 67.63% year-over-year.\n"
    )

    result = grade(tmp_path / "run", exercise, report, [])

    assert result["unverifiable"]["count"] == 6
    assert "too many unverifiable numeric claims" in result["qualification"]["blockers"]
    assert result["qualified"] is False


def test_wrong_operand_is_flagged_once_but_consistent_derivation_is_not(tmp_path: Path) -> None:
    # Arbitrage Pierre (2026-07-15): 22.0 exists nowhere in the corpus (truth is
    # 22.3) — it fails the EXISTENCE check (unverifiable diagnostic). The 4.2x
    # consistent with the SHOWN operands is not charged a second time.
    exercise = _finance_exercise()
    report = (
        "Alphabet spending rose from $22.0B in FY2020 to $91.4B in FY2025 [S1]. "
        "The FY2025 figure represents a 4.2x increase over FY2020 [S1].\n"
    )

    result = grade(tmp_path / "run", exercise, report, [{"source_id": "S1", "content": report}])

    assert result["prose_contradictions"]["items"] == []
    # 22.0 exists nowhere in the corpus and carries a citation: laundering, blocking.
    assert 22.0 in [item["value"] for item in result["fabrication"]["items"]]
    assert all(item["value"] != 4.2 for item in result["unverifiable"]["items"])


def test_wrong_derivation_from_correct_operands_is_diagnostic(tmp_path: Path) -> None:
    exercise = _finance_exercise()
    report = (
        "Alphabet spending rose from $22.3B in FY2020 to $91.4B in FY2025 [S1]. "
        "The FY2025 figure represents a 4.2x increase over FY2020 [S1].\n"
    )

    result = grade(tmp_path / "run", exercise, report, [{"source_id": "S1", "content": report}])

    assert result["fabrication"]["count"] == 0
    assert any(
        item["value"] == 4.2 and item["reason"] == "invalid_derivation"
        for item in result["unverifiable"]["items"]
    )


def test_deterministic_scoring_is_invariant_across_rescores(tmp_path: Path) -> None:
    # Exigence Pierre (2026-07-15): même rapport => même résultat, à chaque
    # re-scoring. Couvre la partie déterministe (le juge LLM, non appelé ici,
    # est mesuré séparément — il ne peut pas être exactement invariant).
    exercise = _finance_exercise()
    report = "\n".join(
        [
            "# FY2025 Capex and Cash Generation",
            _fy2025_table(),
            "",
            "Amazon capex rose from $40.1B in FY2020 to $131.8B in FY2025.",
        ]
    )
    sources = [{"source_id": "S1", "content": report}]

    results = [grade(tmp_path / "run", exercise, report, sources) for _ in range(3)]

    baseline = json.dumps(results[0], sort_keys=True)
    assert all(json.dumps(r, sort_keys=True) == baseline for r in results[1:])


def _amazon_exercise(tmp_path: Path) -> Path:
    """Corpus with a multi-year capex series for one company (Amazon)."""
    exercise = tmp_path / "exercise"
    corpus = exercise / "corpus"
    corpus.mkdir(parents=True)
    (corpus / "capex_reference_data.md").write_text(
        "Amazon capex was 40.1B in FY2020 and 131.8B in FY2025.\n", encoding="utf-8"
    )
    (corpus / "key_metrics.csv").write_text(
        "Company,FYE_basis,Metric,FiscalYear,Value,Unit\n"
        "Amazon,Dec,Capex,FY2020,40.1,USD_billions\n"
        "Amazon,Dec,Capex,FY2025,131.8,USD_billions\n",
        encoding="utf-8",
    )
    (exercise / "answer_key.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "numeric",
                "theme": "test",
                "companies_in_scope": ["Amazon"],
                "must_cover": [],
                "distractors": {},
            }
        ),
        encoding="utf-8",
    )
    (exercise / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "required_chapters": [],
                "embedded_tables": {"required": False, "min_tables": 0},
                "length": {"min_words": 5, "max_words": 400},
                "scoring": {"axes": {"coverage": {"weight": 0.8}, "format": {"weight": 0.2}}},
            }
        ),
        encoding="utf-8",
    )
    return exercise


def test_company_scoped_delta_far_from_operands_is_not_fabrication(tmp_path: Path) -> None:
    """Arbitrage Pierre (2026-07-16): a synthesis sentence lists deltas FAR from
    their operands ("Amazon (+91.7B), ahead of Alphabet (+69.1B)...") — the
    ±160-char window cannot see the source table. When the clause names a
    company, the derivation is checked against THAT company's corpus values
    (same-metric pairs), not the surrounding text. Observed live: all 5
    gpt-5.6-sol finance runs falsely accused on exact corpus deltas."""
    exercise = _amazon_exercise(tmp_path)
    filler = "The detailed table appears earlier in the report. " * 6
    report_md = f"# Trends\n{filler}\nAmazon shows the largest increase (+91.7B) [S1].\n"
    sources = [{"source_id": "S1", "content": "Trend summary without the operand numbers."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 0


def test_company_scoped_growth_percent_is_not_fabrication(tmp_path: Path) -> None:
    exercise = _amazon_exercise(tmp_path)
    filler = "The detailed table appears earlier in the report. " * 6
    report_md = f"# Trends\n{filler}\nAmazon grew by +228.7% over the period [S1].\n"
    sources = [{"source_id": "S1", "content": "Trend summary without the operand numbers."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 0


def test_invented_number_next_to_company_name_is_still_fabricated(tmp_path: Path) -> None:
    """The company-scoped check must not become a laundering hole: an invented
    figure near a company name stays fabricated when no same-metric pair of
    that company derives it."""
    exercise = _amazon_exercise(tmp_path)
    filler = "The detailed table appears earlier in the report. " * 6
    report_md = f"# Trends\n{filler}\nAmazon shows the largest increase (+80.3B) [S1].\n"
    sources = [{"source_id": "S1", "content": "Trend summary without the operand numbers."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 1


def test_rounding_precision_convention_is_not_fabrication(tmp_path: Path) -> None:
    """Codex review #201 (2026-07-16): 'les montants sont arrondis à 0,1 Md$'
    is a presentation convention, not a data claim — 8 such flags capped a
    clean gpt-5.6-sol run at 40."""
    exercise = _amazon_exercise(tmp_path)
    report_md = (
        "# Method\nAmazon capex reached 131.8B [S1].\n"
        "Les montants sont arrondis à 0,1 Md$ et les marges à 0,1 point [S1].\n"
        "Amounts are rounded to 0.1B for presentation [S1].\n"
    )
    sources = [{"source_id": "S1", "content": "Summary without numbers."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 0


def test_binary_minus_between_operands_is_not_a_negative_number(tmp_path: Path) -> None:
    """Codex review #201 (2026-07-16): the minus in '131,8 - 40,1' is a binary
    operator; parsing it as negative -40.1 pushed a shown operand off the
    whitelist."""
    exercise = _amazon_exercise(tmp_path)
    # \u2212 = vrai signe moins Unicode des rapports (un tiret serait parse comme une plage)
    report_md = "# Calc\nAmazon FCF check: 131,8 \u2212 40,1 = 91,7 Md$ [S1].\n"
    sources = [{"source_id": "S1", "content": "Summary without numbers."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 0


def _amazon_ratio_exercise(tmp_path: Path) -> Path:
    exercise = tmp_path / "exercise"
    corpus = exercise / "corpus"
    corpus.mkdir(parents=True)
    (corpus / "capex_reference_data.md").write_text(
        "Amazon FY2025: capex 131.8B, operating cash flow 139.4B, ratio 94 percent.\n",
        encoding="utf-8",
    )
    (corpus / "key_metrics.csv").write_text(
        "Company,FYE_basis,Metric,FiscalYear,Value,Unit\n"
        "Amazon,Dec,Capex,FY2025,131.8,USD_billions\n"
        "Amazon,Dec,Operating cash flow,FY2025,139.4,USD_billions\n"
        "Amazon,Dec,Operating income,FY2025,70.0,USD_billions\n"
        "Amazon,Dec,Capex/OCF,FY2025,94,percent\n",
        encoding="utf-8",
    )
    (exercise / "answer_key.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "numeric",
                "theme": "test",
                "companies_in_scope": ["Amazon"],
                "must_cover": [],
                "distractors": {},
            }
        ),
        encoding="utf-8",
    )
    (exercise / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "required_chapters": [],
                "embedded_tables": {"required": False, "min_tables": 0},
                "length": {"min_words": 5, "max_words": 400},
                "scoring": {"axes": {"coverage": {"weight": 0.8}, "format": {"weight": 0.2}}},
            }
        ),
        encoding="utf-8",
    )
    return exercise


def test_recomputed_cross_metric_ratio_is_not_fabrication(tmp_path: Path) -> None:
    """gpt-5.6-sol recomputed the requested Capex/OCF ratios at higher precision
    than the corpus rounding (94.5% vs corpus 94) — the exercise explicitly
    asks for this division. Same-company same-period cross-metric ratios are a
    legitimate derivation class."""
    exercise = _amazon_ratio_exercise(tmp_path)
    filler = "The detailed table appears earlier in the report. " * 6
    report_md = f"# Ratios\n{filler}\nAmazon Capex/OCF recalcule est de 94,5 % [S1].\n"
    sources = [{"source_id": "S1", "content": "Trend summary without numbers."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 0


def test_extraction_meta_statement_is_not_a_false_unavailability(tmp_path: Path) -> None:
    """'One corpus extraction states that Apple operating income is unavailable'
    reports what a retrieval extraction said — meta-discourse, not a claim
    about the fact (same family as the evidence-chunk guard)."""
    exercise = _amazon_ratio_exercise(tmp_path)
    report_md = (
        "# Gaps\nAmazon capex reached 131.8B [S1].\n"
        "One corpus extraction states that Amazon operating income is unavailable [S1].\n"
    )
    sources = [{"source_id": "S1", "content": "Summary."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["accuracy"]["wrong"] == 0


def test_presentation_precision_wording_is_not_fabrication(tmp_path: Path) -> None:
    exercise = _amazon_ratio_exercise(tmp_path)
    report_md = (
        "# Method\nAmazon capex reached 131.8B [S1].\n"
        "Les montants sont présentés à 0,1 Md$ dans les tableaux [S1].\n"
    )
    sources = [{"source_id": "S1", "content": "Summary."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 0


def test_margin_ratio_cannot_launder_invented_figure(tmp_path: Path) -> None:
    """Falsified control regression (2026-07-16): a planted 137 was laundered
    by the ratio of two operating margins (37.3/27.2*100 = 137.13) — a
    dimensional nonsense. Percent-typed metrics only support DELTAS
    (percentage points) in the corpus fallback."""
    exercise = tmp_path / "exercise"
    corpus = exercise / "corpus"
    corpus.mkdir(parents=True)
    (corpus / "capex_reference_data.md").write_text(
        "NVIDIA operating margin was 27.2 percent in FY2021 and 37.3 percent in FY2022.\n",
        encoding="utf-8",
    )
    (corpus / "key_metrics.csv").write_text(
        "Company,FYE_basis,Metric,FiscalYear,Value,Unit\n"
        "NVIDIA,Jan,Operating margin,FY2021,27.2,percent\n"
        "NVIDIA,Jan,Operating margin,FY2022,37.3,percent\n",
        encoding="utf-8",
    )
    (exercise / "answer_key.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "numeric",
                "theme": "test",
                "companies_in_scope": ["NVIDIA"],
                "must_cover": [],
                "distractors": {},
            }
        ),
        encoding="utf-8",
    )
    (exercise / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "required_chapters": [],
                "embedded_tables": {"required": False, "min_tables": 0},
                "length": {"min_words": 5, "max_words": 400},
                "scoring": {"axes": {"coverage": {"weight": 0.8}, "format": {"weight": 0.2}}},
            }
        ),
        encoding="utf-8",
    )
    report_md = "# Analysis\nNVIDIA revenue grew by an impressive 137% [S1].\n"
    sources = [{"source_id": "S1", "content": "Summary without numbers."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 1


def test_respectivement_enumeration_of_recomputed_ratios_is_not_fabrication(tmp_path: Path) -> None:
    """'Les ratios capex/OCF recalculés sont respectivement de 94,5 %, ...' —
    an ordered enumeration names no company in the paragraph; the values are
    exact recomputations of per-company corpus amounts. Without a named
    company the fallback tries every company in scope (still near-exact)."""
    exercise = _amazon_ratio_exercise(tmp_path)
    filler = "Definitions and reconciliation notes appear here. " * 5
    report_md = f"# Method\n{filler}\nLes ratios recalcules sont respectivement de 94,5 % [S1].\n"
    sources = [{"source_id": "S1", "content": "Summary without numbers."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 0


def test_guidance_table_rows_never_accuse_actuals(tmp_path: Path) -> None:
    """gpt-5.6-sol run: the guidance table row '| Alphabet | Environ 75 |
    4 fev. 2025 |' (a frozen-pack guidance FACT, correctly reported in the
    guidance section) was attributed as Alphabet Capex FY2025 actual and
    accused vs 91.4. A table whose header matches guidance markers carries no
    accusation authority."""
    exercise = tmp_path / "exercise"
    corpus = exercise / "corpus"
    corpus.mkdir(parents=True)
    (corpus / "capex_reference_data.md").write_text(
        "Alphabet capex was 91.4B in FY2025. Initial FY2025 guidance: approximately 75B.\n",
        encoding="utf-8",
    )
    (corpus / "key_metrics.csv").write_text(
        "Company,FYE_basis,Metric,FiscalYear,Value,Unit\n"
        "Alphabet,Dec,Capex,FY2025,91.4,USD_billions\n",
        encoding="utf-8",
    )
    (exercise / "answer_key.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "numeric",
                "theme": "test",
                "companies_in_scope": ["Alphabet"],
                "must_cover": [],
                "distractors": {},
            }
        ),
        encoding="utf-8",
    )
    (exercise / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "required_chapters": [],
                "embedded_tables": {"required": False, "min_tables": 0},
                "length": {"min_words": 5, "max_words": 400},
                "scoring": {"axes": {"coverage": {"weight": 0.8}, "format": {"weight": 0.2}}},
            }
        ),
        encoding="utf-8",
    )
    report_md = (
        "# Guidance\n\n"
        "| Societe | Guidance capex initiale FY2025 | Date de publication | Base indiquee |\n"
        "|---|---:|---|---|\n"
        "| Alphabet | Environ 75 | 4 fev. 2025 | Capex publie; variabilite possible [S2] |\n"
    )

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["accuracy"]["wrong"] == 0


def test_source_discrepancy_note_with_value_is_not_false_unavailability(tmp_path: Path) -> None:
    """gpt-5.6-sol flagged a documentary inconsistency — '[S3] indique
    l'operating income d'Apple comme indisponible, tandis que les données
    structurées donnent 133,1 Md$' — exemplary analyst behavior: the clause
    SHOWS the corpus value, so it cannot be claiming unavailability."""
    exercise = _write_exercise(tmp_path)
    report_md = (
        "# Gaps\n"
        "Une incoherence documentaire doit etre signalee : [S3] indique le revenue "
        "d'Apple comme indisponible, tandis que les donnees structurees donnent "
        "416.2 Md$ pour FY2025 [S4].\n"
    )

    result = grade(tmp_path / "run", exercise, report_md, [])

    assert result["accuracy"]["wrong"] == 0


def test_unit_scale_variant_of_corpus_number_is_not_fabrication(tmp_path: Path) -> None:
    """Arbitrage Pierre (2026-07-16, qwen run 15) : le rapport définit sa propre
    abréviation « milliards de dollars (M$) » puis écrit « de 40,1 M$ à
    131,8 M$ ». Le scorer lisait M$ = millions -> 0.1318 Md$ hors corpus ->
    fabrication. L'esprit du test d'existence : le NOMBRE écrit existe dans le
    corpus ; l'ambiguïté d'échelle d'unité n'est pas une invention."""
    exercise = _amazon_exercise(tmp_path)
    report_md = "# Trends\nAmazon capex rose from 40,1 M$ in FY2020 to 131,8 M$ in FY2025 [S1].\n"
    sources = [{"source_id": "S1", "content": "Summary without numbers."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 0


def test_french_guidance_wording_guides_initiaux_is_not_false_unavailability(tmp_path: Path) -> None:
    """qwen run 15 : « Microsoft, NVIDIA et Apple n'ont pas fourni de guides
    initiaux de Capex pour le FY2025 » — statement TRUE about guidance, but
    the guidance vocabulary lacked the French word « guide »."""
    exercise = _amazon_ratio_exercise(tmp_path)
    report_md = (
        "# Guidance\nAmazon capex reached 131.8B [S1].\n"
        "Amazon n'a pas fourni de guides initiaux de Capex pour le FY2025, "
        "ces donnees etant indisponibles [S1].\n"
    )
    sources = [{"source_id": "S1", "content": "Summary."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["accuracy"]["wrong"] == 0


def test_source_attributed_unavailability_is_meta_discourse(tmp_path: Path) -> None:
    """gpt-5.6-sol capex-3 (le 60.0 qui creusait sa variance) : « [S7] marks
    all Apple metrics as unavailable, while the cross-source reconciliation
    reports Apple's revenue... retained » — une indisponibilité ATTRIBUÉE à
    une source ([Sx] marks/labels/indique) décrit ce que dit la source, pas le
    fait ; le modèle décrit un conflit et garde les bonnes valeurs."""
    exercise = _amazon_ratio_exercise(tmp_path)
    report_md = (
        "# Gaps\nAmazon capex reached 131.8B [S1].\n"
        "However, [S7] marks all Amazon metrics as unavailable, while the "
        "cross-source reconciliation reports Amazon's revenue and operating income; "
        "these are therefore retained [S1].\n"
    )
    sources = [{"source_id": "S1", "content": "Summary."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["accuracy"]["wrong"] == 0


def test_binary_minus_after_unit_letter_is_not_negative(tmp_path: Path) -> None:
    """MiniMax capex-1 : « $139.5B − $131.8B = $7.7B » — le moins suit la
    lettre d'unité B, pas un chiffre ; lu comme -131.8 -> hors whitelist."""
    exercise = _amazon_exercise(tmp_path)
    report_md = "# Calc\nAmazon FCF: $139.5B − $131.8B = $7.7B [S1].\n"
    sources = [{"source_id": "S1", "content": "Summary without numbers."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert all(it["value"] != -131.8 for it in result["fabrication"]["items"])


def test_hedged_round_threshold_in_english_is_not_fabrication(tmp_path: Path) -> None:
    """MiniMax : « Capex/OCF exceeding 50% », « capex 20-50% of OCF » — des
    seuils de classement d'analyste ; le vocabulaire hedge était francophone."""
    exercise = _amazon_ratio_exercise(tmp_path)
    report_md = (
        "# Buckets\nAmazon capex reached 131.8B [S1].\n"
        "Capital-extreme reinvestors show Capex/OCF exceeding 50% of OCF [S1].\n"
    )
    sources = [{"source_id": "S1", "content": "Summary."}]

    result = grade(tmp_path / "run", exercise, report_md, sources)

    assert result["fabrication"]["count"] == 0
