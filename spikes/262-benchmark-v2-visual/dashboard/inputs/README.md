# Inputs for the dashboard test (frozen 2026-11-09)

Quantitative report, primary
- quant_report_gpt56sol_20261013_211653.md
  Run benchmarks/runs/20261013_211653_gpt-5.6-sol-chroma-decomposed (bench)_decomposed
  (campaign 13/10, gpt-5.6-sol, deep_manager decomposed). Deterministic grade: 100.0,
  42/42 facts, 0 wrong, 0 fabricated, 0 unverifiable, 1,326 words. Flagged "not qualified"
  by the grader on capex_trend_adequacy only; the 13/10 second reading classed that as a
  false positive (gpt-5.6-sol A on all five finance runs). NVIDIA period labelled
  "FYE Jan." (correct). Grade file copied alongside (.det_grade.json).

Quantitative report, alternate
- quant_report_glm53_20261013_222440.md
  Run benchmarks/runs/20261013_222440_glm53-mistral-decomposed_decomposed (GLM 5.3 on all
  roles). Deterministic grade: 100.0, qualified, 42/42, 0 wrong, 0 fabricated, 1,820
  words. NVIDIA period "FYE late Jan 2025" (correct).

Not retained: the two Mistral Large 4 runs at 100.0 (212918, 214757) label NVIDIA FY2025
as "ended Jan 2026" (wrong: fiscal year ended 2025-01-26), an error the grader does not
catch.

Model ranking reminder (campaign 13/10, after second reading): gpt-5.6-sol A x5,
Mistral Large 4 A x5, GLM 5.3 C A A A A. The choice above is of a file, not a model.

Qualitative inputs
- ../../10k_fy2025/extracts/*_fy2025_datacenter_extracts.md (six files, eight themes,
  verbatim quotes with locators). See ../../10k_fy2025/extracts/README.md.

Brief
- ../brief_dashboard_v1.md

Pairing rule for the test: same brief, same two inputs, one HTML output per model.
