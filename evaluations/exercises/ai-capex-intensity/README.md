# FY2025 AI Capex Intensity Exercise

This evidence-bound exercise tests a junior-analyst report across Amazon, Alphabet,
Meta, Microsoft, NVIDIA, and Apple. It is calibrated for medium 24B-250B models:
the task asks for factual extraction, simple ratios, source gaps, and neutral trends,
not an investment thesis.

## Frozen contract

- `syllabus.md` requests seven FY2025 metrics for each company: 42 required facts.
- `answer_key.yaml` declares companies, metrics, and periods without duplicating values.
- `corpus/key_metrics.csv` is the numeric truth generated from SEC Company Facts.
- `corpus/manifest.json` records the six input snapshot hashes and generated-file hashes.
- `generate.py` regenerates the corpus and fails if the answer-key dimensions are absent.
- `capex_guidance_2025.md` freezes initial guidance as of February 7, 2025 and records
  the basis mismatch that makes Meta's guidance variance not like-for-like.

Regenerate with:

```bash
uv run python evaluations/exercises/ai-capex-intensity/generate.py \
  --companyfacts-dir /path/to/companyfacts
```

## Qualification

`deterministic_grade.py` remains the sole authority for the score and every numeric
verdict. Qualification additionally requires a pinned semantic adequacy check to pass
the six closed requirements declared in `answer_key.yaml`. That check is a veto only:
it can block a report whose requested analysis is missing or misleading, but can never
change numeric coverage, accuracy, fabrication, contradictions, or score, and can never
rehabilitate a deterministic failure.

Each official run therefore needs `report.md`, `stats.json`, `sources.json`,
`chunks.json`, and the retrieved files under `raw_sources/` in its run directory. The
grader verifies raw chunks and archived sources against the hashes in
`corpus/manifest.json`, stores full judge I/O in `semantic_judge.json`, and fails closed
on missing evidence, judge disagreement, or invalid structured output. Use
`--skip-semantic-judge` only for local deterministic diagnostics; that result is always
non-qualifying.

## Interface versions

- **v1** (runs of 2026-07-13/15): ambiguous tool interface — the stored-filename vs
  URL-basename duality was undocumented (see issue #202). Historical runs kept as-is.
- **v2** (issue #202, 2026-07-15): documentation-only fix — download tool states it
  returns the stored filename; upload tool documents the two accepted input forms
  (exact URLs, or exact stored names); vector_search documents the `filenames`
  filter; knowledge_preparation prompt gets an explicit parameter-passing rule.
  No logic, signature, or storage change. Campaign runs must be compared within
  the same interface version; the v1→v2 delta measures robustness to ambiguity.
