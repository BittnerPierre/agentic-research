# Exercise B — Finance: Consumer Platform Unit-Economics Maturation

A **deterministic** benchmark exercise for the agentic research workflow. Unlike the
open RAG-triad grading (an LLM judge scoring an unknown topic), this exercise is a
*known, mastered* case: we know exactly what a correct report contains, and we score
it against a fixed answer key with mechanical checks + closed LLM-entailment.

## What it tests

The **whole workflow** end-to-end — knowledge preparation, search/retrieval, agenda,
and the final report — not just the writer. The final deliverable is a chaptered
brief with embedded data tables, so the numbers are mechanically parseable.

## The exercise

- **Task**: `syllabus.md` — write an IC brief on how Netflix, Airbnb, and Zillow
  matured from land-grab to disciplined monetization + cash generation (2019-2024),
  **using only** the provided sources.
- **KB / corpus**: `corpus/` — 7 heterogeneous source files (a prose reference doc,
  a sectioned appendix, and analyst-note batches). Loaded into the vector store; the
  workflow retrieves from it.
- **Answer key**: `answer_key.yaml` — ground truth in three tiers (must_cover /
  accuracy_universe / distractors).
- **Spec**: `spec.yaml` — required chapters, table format, only-provided-sources,
  length, and the composite scoring weights.

## Scoring model (no open "grade it 0-1" judge)

| Axis | Mechanism | Deterministic? |
| --- | --- | --- |
| **Coverage** (recall of must_cover) | numeric facts → anchor tokens (grep); qualitative claims → **closed LLM-entailment** (YES/NO + mandatory quote) | numeric: yes; qualitative: stable |
| **Accuracy** (precision) | figures appearing in the report matched to `accuracy_universe` after number normalization | **yes** |
| **Fabrication gate** | numbers/named entities in the report **not traceable to the corpus** | **yes** — the anti-hallucination lock |
| **Agenda discipline** | distractor companies pulled into the brief | **yes** |
| **Format** | required chapters + parseable tables + length + tone | **yes** |

The grade is **factual**: it reports raw counts (`14/18 must-cover, 0 fabrications,
6/6 chapters, 2/2 tables parseable`), not a subjective score. Run **N times per
model** and report mean ± std to handle retrieval variance (the only remaining
source of run-to-run noise, since the corpus and answer key are fixed).

## Number normalization (the one real engineering task)

The corpus writes numbers in mixed real-world formats: `85,002`, `$000`, `±$300m`,
`~$75B`, `+70 bps`, `13.5%`. The scorer must normalize (strip separators, resolve
scale, tolerate `~`/`±`) before comparing. This robustness is part of what the
exercise measures — so the corpus is **deliberately left "messy"**; normalization
lives in the scorer, not in the sources.

## Corpus decisions (diligence notes)

- **Duplicate removed**: Batch 1 and Batch 2 were byte-identical; Batch 2 dropped.
- **Contradictions kept** (both off-theme distractors, so they don't affect scoring
  here, but they're realistic and a bonus source-discrimination signal):
  - Oracle ETR — main appendix says ~19% / −300 bps; Batch 4 says 10.9% / +410 bps
    (correct, SEC-sourced).
  - Microsoft % employees outside US — appendix ~54%; Batch 5 says 44.7% (correct).
- **Minor discrepancy accepted**: Airbnb GBV FY2024 is 82.0 (Batch 3) vs 81.8
  (Batch 4); both accepted in `accuracy_universe`.

## Status

Draft authored by Opus 2026-07-13 — **answer key pending Pierre's review**. The
scorer (`deterministic_grade.py`) is not built yet; this is the gold pack it will
consume. A sibling conceptual exercise (the 5 AI-engineering references) will use
the same scorer with coverage driven by entailment rather than numeric anchors.
