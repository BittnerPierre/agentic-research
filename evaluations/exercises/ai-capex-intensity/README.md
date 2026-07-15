# FY2025 AI Capex Intensity Exercise

This deterministic exercise tests a junior-analyst report across Amazon, Alphabet,
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

`deterministic_grade.py` emits both a diagnostic score and `qualified`. Qualification
requires every critical report requirement, no wrong or fabricated factual claim,
the requested report structure, and the frozen source policy. Tone, exact table layout,
and ambiguous but non-contradictory prose remain diagnostic to avoid penalizing medium
models for stylistic variance.

## Interface versions

- **v1** (runs of 2026-07-13/15): ambiguous tool interface — the stored-filename vs
  URL-basename duality was undocumented (see issue #202). Historical runs kept as-is.
- **v2** (issue #202, 2026-07-15): documentation-only fix — download tool states it
  returns the stored filename; upload tool documents the two accepted input forms
  (exact URLs, or exact stored names); vector_search documents the `filenames`
  filter; knowledge_preparation prompt gets an explicit parameter-passing rule.
  No logic, signature, or storage change. Campaign runs must be compared within
  the same interface version; the v1→v2 delta measures robustness to ambiguity.
