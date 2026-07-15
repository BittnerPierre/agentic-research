# AI Engineering Syllabus Exercise

This fixed exercise validates a factual onboarding brief for a junior AI engineer.
It is designed for varied medium and open-weight models, not for one expected wording
and not as a generic report benchmark.

## Authority

- `test_files/syllabus.md` is the exact report request.
- `answer_key.yaml` is a closed natural-language rubric with 14 concepts and two
  whole-report requirements.
- `source_manifest.yaml` freezes the five public references by filename pattern and
  SHA-256.
- Lexical anchors remain a cheap diagnostic only. They never qualify a report.
- The authoritative semantic judge is the dated snapshot
  `gpt-5.4-2026-03-05`, followed by an adversarial pass that tries to refute every
  primary pass.
- A disagreement, invalid judge output, missing evidence, or contract mismatch fails
  closed and requires review.

The deterministic Finance scorer remains the sole authority for numbers, periods,
guidance values, calculations, and fabrication. The same semantic protocol can only
veto Finance qualification when the requested analysis is missing or misleading; it
cannot award numeric credit or rehabilitate a deterministic failure.

## Evidence Pack

Every new run must persist these files under `benchmarks/runs/<run>/`:

- `report.md`: exact report evaluated.
- `stats.json`: exact request, candidate models, timing, usage, and workflow status.
- `sources.json`: generated research summaries and their source IDs.
- `chunks.json`: exact raw chunks returned to search agents, with stable IDs and hashes.
- `raw_sources/`: exact source files behind those chunks, copied into the run pack.

Conceptual grading adds:

- `semantic_judge.json`: full primary and adversarial prompts, raw structured responses,
  categorical verdicts, and protocol errors.
- `adjudication_contract.json`: frozen input and judge hashes.
- `det_grade.json`: final qualification plus the non-authoritative lexical diagnostic.

The grader verifies that every chunk hash is valid, its archived filename belongs to the
frozen manifest, the archived source file has the expected hash, and the chunk text
occurs in that raw source or its deterministic RAG-cleaned representation. A generated
summary without a resolved raw chunk cannot support a pass. Missing archived sources
fail closed so the run pack remains independently re-adjudicable.

## Grading

Run the authoritative grader with:

```bash
uv run deterministic-grade benchmarks/runs/<run> \
  --exercise evaluations/exercises/ai-engineering-syllabus
```

For local parser diagnostics without an API call:

```bash
uv run deterministic-grade benchmarks/runs/<run> \
  --exercise evaluations/exercises/ai-engineering-syllabus \
  --skip-semantic-judge
```

The second command is always non-qualifying.

The judge uses high reasoning effort. Temperature and top-p are intentionally omitted:
the GPT-5.4 API supports those sampling parameters only with reasoning effort set to
none. Confidence is stored only for human triage and never affects a verdict.

## Campaign Gate

Official comparisons require the same commit, interface v2, request hash, rubric hash,
source manifest, judge snapshot, and judge prompts for every candidate. Historical
reports from July 13, 2026 received an earlier syllabus and lack the portable chunk
pack. They are regression fixtures only and must return contract mismatch rather than
an official score.
