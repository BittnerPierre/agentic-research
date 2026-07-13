# Analyst Data Prep — AI-Era Capital-Expenditure Intensity

## Role & scope

You are a **junior analyst** preparing a **factual data pack** for a senior analyst.
Your job is **data gathering and first-level analysis** — assemble the reported
figures, compute simple ratios, and describe the trends **neutrally**. This is
**not** a market study, an investment recommendation, or a broker note. Do not take
a position, do not forecast, do not editorialize.

Cover these six companies from the provided sources:
**Amazon, Alphabet, Meta, Microsoft, NVIDIA, Apple.**

## What to produce (per company, then a comparison)

For each company, from its most recent fiscal year available in the sources, gather:
- **Revenue**
- **Operating income** and **operating margin** (= operating income / revenue)
- **Operating cash flow**
- **Capital expenditures (capex)**
- **Free cash flow** (= operating cash flow − capex)
- **Capex intensity** (= capex / operating cash flow, as a %)

Then compute/describe **first-level** observations only:
- the direction and magnitude of the **capex trend** over the years available
  (e.g. "rose from ~$X B to ~$Y B");
- how capex compares to cash generation (the capex/OCF ratio);
- where a figure is **not available** in the sources, say so explicitly.

## External References

Use exclusively the following provided files — no web search, no other companies or
figures:

- https://gist.githubusercontent.com/BittnerPierre/555a92f661d3113bee781ba0f793c26a/raw/67170ebcc17d941290bef6947b64f559d3586297/capex_reference_data.md
- https://gist.githubusercontent.com/BittnerPierre/555a92f661d3113bee781ba0f793c26a/raw/8a7374c91cfe666134d600738f32be349c41ee4c/analyst_prep_notes.md
- https://gist.githubusercontent.com/BittnerPierre/555a92f661d3113bee781ba0f793c26a/raw/52ac99a5970bab03242aa6e796b45221dd966b75/key_metrics.csv
- https://gist.githubusercontent.com/BittnerPierre/555a92f661d3113bee781ba0f793c26a/raw/6765f4127b59f5c717b2ff7b4aa8154ed954bc12/capex_guidance_2025.md
- https://gist.githubusercontent.com/BittnerPierre/555a92f661d3113bee781ba0f793c26a/raw/fa8a6f75a922b36d3db71c396d229616e365f914/misc_disclosures.md

## Constraints (important)

- Use **only** the provided sources. Do not add outside companies, numbers, or facts.
- **Every figure must be traceable to the sources.** Do not invent or estimate
  numbers; do not compute figures the sources do not support.
- **Neutral, factual tone.** Describe what the numbers show. Do **not** write things
  like "spends from strength", "most disciplined", "best positioned", "should",
  "we expect", "the market will" — no judgments, ratings, or predictions.
- **Fiscal years differ** (Amazon/Alphabet/Meta = December; Microsoft = June;
  NVIDIA = late January; Apple = late September). Label each figure with its fiscal
  year; do not conflate different companies' years as if calendar-aligned.
- Keep **guidance** (management's 2025 capex plans) clearly separate from **reported
  actuals** (10-K figures).

## Deliverable format — a structured brief with data tables

Markdown report. Each analytical chapter combines a short **factual** description
with an embedded **data table**. Use this schema for figure tables:

| Company | Metric | Period | Value |
| ------- | ------ | ------ | ----- |

Required chapters:

1. **Overview & Scope** — the six companies, the metrics, the fiscal-year-end
   differences, and the metric definitions.
2. **Revenue & Operating Margin** — table + neutral description.
3. **Capex & Capex Intensity** — table (capex and capex/OCF) + factual trend notes.
4. **Cash Generation** — table (operating cash flow and free cash flow).
5. **Cross-Company Comparison** — one consolidated table of the latest-year headline
   figures for all six companies.
6. **Data Gaps** — figures requested but not available in the sources.
