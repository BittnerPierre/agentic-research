# Exercise — Finance: AI-Era Capex Intensity (junior-analyst data prep)

A **deterministic** benchmark exercise for the agentic research workflow, built on
authoritative SEC EDGAR data. It replaces open LLM-judge grading with mechanical
checks + closed entailment against a fixed answer key.

## What it tests, and for whom

The **whole workflow** end-to-end — knowledge preparation, retrieval, agenda, and
the final report. It is calibrated for **medium-size, new-generation models**
(e.g. Mistral Small 4, Qwen 3.6) hosted on **DGX Spark (GB10)**, solo or cluster —
**not** frontier models. Accordingly the task is a **junior-analyst data prep**:
gather reported figures, compute first-level ratios, describe trends **neutrally**.
It deliberately does **not** ask for a market thesis, positioning, or forecast —
that would be a senior-analyst task and hard to score deterministically.

## The exercise

- **Task**: `syllabus.md` — assemble a factual capex-intensity data pack for six
  large-cap tech companies (Amazon, Alphabet, Meta, Microsoft, NVIDIA, Apple),
  using only the provided sources, in a chaptered brief with data tables.
- **KB / corpus**: `corpus/` — multi-format, so retrieval must handle heterogeneity:
  - `capex_reference_data.md` — clean markdown data tables (the actuals grid).
  - `analyst_prep_notes.md` — the same figures as factual prose notes.
  - `key_metrics.csv` — compact structured extract (the accuracy universe).
  - `capex_guidance_2025.md` — forward guidance (kept separate from actuals).
  - `misc_disclosures.md` — off-theme facts (R&D, dividends, headcount) = distractors.
- **Answer key**: `answer_key.yaml` — must_cover / accuracy_universe / distractors.
- **Spec**: `spec.yaml` — chapters, tables, only-provided, **tone neutrality**, weights.

## Scoring model (no open "grade it 0-1" judge)

| Axis | Mechanism | Deterministic? |
| --- | --- | --- |
| **Coverage** (must_cover) | headline figures → anchor tokens (grep); factual trend claims → closed LLM-entailment (YES/NO + quote) | numeric: yes |
| **Accuracy** | figures in the report matched to `key_metrics.csv` after number normalization | **yes** |
| **Fabrication gate** | numbers/entities not traceable to the corpus | **yes** — the lock |
| **Agenda discipline** | distractor facts pulled in | **yes** |
| **Tone neutrality** | forbidden opinion/forecast language (this exercise is factual-only) | **yes** |
| **Format** | required chapters + parseable tables + length | **yes** |

Grade is **factual**: raw counts (`23/25 must-cover, 0 fabrications, 1 tone
violation, 6/6 chapters`). Run **N times per model**, report mean ± std (retrieval
variance is the only remaining run-to-run noise; corpus + answer key are fixed).

## Provenance — authoritative ground truth

Corpus and answer key are **both generated from the same EDGAR XBRL extraction**
(`scratchpad/gen_capex_exercise.py`), so they cannot drift. Annual values are taken
from 10-K filings, keyed by the fact's **period end date** (not the filing's `fy`
label — a common XBRL trap that mis-dates comparative-year figures). Each company
uses its most recent fiscal year with a complete metric set; fiscal-year-ends differ
(Dec / June / late-Jan / late-Sep) and are labeled throughout.

## Status

Draft authored by Opus 2026-07-13 — **answer key pending Pierre's review**. Scorer
(`deterministic_grade.py`) not built yet. Sibling exercises using the same scorer:
`finance-consumer-platforms` (ready) and a conceptual AI-engineering exercise (todo).
