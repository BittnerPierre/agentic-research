# Junior Analyst Data Pack - FY2025 AI Capex Intensity

## Role and objective

Prepare a concise, factual data pack for a senior analyst. This is a data collection
and first-level analysis task, not an investment opinion. Cover Amazon, Alphabet,
Meta, Microsoft, NVIDIA, and Apple using only the five provided sources.

## Required facts

For every company, report all seven FY2025 metrics below. FY2025 is the latest fiscal
year with a complete set in this frozen corpus for all six companies.

1. Revenue
2. Operating income
3. Operating margin
4. Operating cash flow
5. Capital expenditures (capex)
6. Free cash flow (FCF)
7. Capex/operating-cash-flow ratio

Use the values supplied in the sources. FCF equals operating cash flow minus capex;
capex intensity equals capex divided by operating cash flow. Do not introduce other
companies, estimates, or empirical figures.

## Required analysis

- State that fiscal-year ends differ: December for Amazon, Alphabet, and Meta; June
  for Microsoft; late January for NVIDIA; and late September for Apple.
- For each company, describe the direction and magnitude of its capex trend from the
  earliest available capex year to FY2025. Use the endpoints in the corpus.
- In a separate guidance section, report the frozen initial FY2025 guidance, release
  date, and basis for Amazon, Alphabet, and Meta. Report Microsoft, NVIDIA, and Apple
  guidance as unavailable in this source pack.
- Keep guidance separate from FY2025 actuals. Do not calculate a Meta guidance variance
  because guidance includes finance-lease principal while the XBRL cash-capex actual
  does not use the same basis.
- State whether any required actual metric is missing. Do not infer a missing value.

## Report contract

Write a Markdown brief with these sections: Overview and Definitions; FY2025
Profitability; FY2025 Capex and Cash Generation; Capex Trends; Guidance vs Actuals;
Cross-Company Comparison; Data Gaps.

Put every required FY2025 fact in a parseable table using these columns:

| Company | Metric | Period | Value |
| --- | --- | --- | --- |

Period must be explicit. Cite the supplied source ID next to each table or factual
paragraph. Use a neutral, descriptive tone. Keep the report between 500 and 1,800
words, excluding the automatically generated Sources section.

## External References

Use exclusively these provided files. Do not browse the web.

- https://gist.githubusercontent.com/BittnerPierre/555a92f661d3113bee781ba0f793c26a/raw/67170ebcc17d941290bef6947b64f559d3586297/capex_reference_data.md
- https://gist.githubusercontent.com/BittnerPierre/555a92f661d3113bee781ba0f793c26a/raw/8a7374c91cfe666134d600738f32be349c41ee4c/analyst_prep_notes.md
- https://gist.githubusercontent.com/BittnerPierre/555a92f661d3113bee781ba0f793c26a/raw/52ac99a5970bab03242aa6e796b45221dd966b75/key_metrics.csv
- https://gist.githubusercontent.com/BittnerPierre/555a92f661d3113bee781ba0f793c26a/raw/6765f4127b59f5c717b2ff7b4aa8154ed954bc12/capex_guidance_2025.md
- https://gist.githubusercontent.com/BittnerPierre/555a92f661d3113bee781ba0f793c26a/raw/fa8a6f75a922b36d3db71c396d229616e365f914/misc_disclosures.md
