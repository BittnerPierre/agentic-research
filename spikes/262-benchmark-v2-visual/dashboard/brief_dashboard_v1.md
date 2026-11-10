# Dashboard brief, v1 (frozen 2026-11-09)

Given verbatim to every model, with two inputs attached: the quantitative report
(Markdown, from an ai-capex-intensity run) and the six 10-K extract files
(../10k_fy2025/extracts/). Output expected: one self-contained HTML file.

---

Situation
Our firm is preparing an investment thesis on cloud and AI infrastructure. The Managing
Partner will present it at next month's partners' meeting and needs a view on the capex
wave at the six companies that drive it: Amazon, Alphabet, Meta, Microsoft, NVIDIA and
Apple. The research team has produced a quantitative data pack (XBRL figures, FY2020 to
FY2025) and a qualitative read of the six FY2025 10-Ks. Your job is to turn both into
one interactive dashboard the MP can read alone in fifteen minutes.

What the MP wants to understand
Who is spending, how sustainably, and under which definition of capex. How much of the
commitment sits outside the capex line (leases not yet commenced, purchase obligations).
Whether companies are keeping their guidance. Which signals in the 10-Ks say the cycle is
accelerating or slowing. The MP will decide from this where the firm should look next in
the value chain, so conclusions matter more than exhaustiveness.

Your role and inputs
You are a research associate. Use only the two inputs provided: the quantitative report
and the six sets of 10-K extracts. Every figure must come from them and keep the basis
its source gives it; where a company's own capex definition differs from the cash-flow
line, say so and name both. Compare on a fiscal-year basis and keep fiscal year-ends
visible. Keep initial FY2025 guidance separate from FY2025 actuals and from any 2026
indications. Say "not disclosed" rather than estimate.

How to write
As an analyst writes for a partner: investment-grade register, each view accompanied by
its reading (what it shows, why it matters, what to watch), explicit takeaways, named
risks. Visuals support the argument; prose carries it.

Constraints
One self-contained HTML file. No external resources, no network calls, interactivity
implemented in-file. Readable on a laptop screen. Layout, charts and structure are yours.
Before returning, check that the file works as delivered: every tag closed, the
JavaScript parses and runs without errors, no literal escape sequences such as "\n" left
inside the source, every chart renders from the embedded data, and nothing overflows the
viewport.

---

Revision note: the self-check paragraph above was added on 2026-11-09 evening (v1.1) after
the first Mistral Large 4 output shipped with a JavaScript syntax error. GPT-5.6-sol and
Claude Fable 5.1 were run on v1 (without that paragraph); later runs use v1.1.

---

Notes
- Not scored. Showcase of out-of-the-box dataviz and reporting; the gap between models
  is read visually.
- v0 dashboard (ai_capex_dashboard_v0.html) was produced before this brief existed, on a
  three-line brief: kept as the counter-example (dataviz-heavy, little analysis,
  journalistic headings).
- The exercise syllabus frames a junior "data pack, not an investment opinion"; the
  situation above is deliberately the next step, where an opinion is expected.
