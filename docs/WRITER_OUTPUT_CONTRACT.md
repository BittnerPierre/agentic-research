# Writer Output Contract (Configurable)

The writer agent output format is configured via `agents.writer_output_format`:
- `json`: writer returns structured JSON that maps to `ReportData`.
- `markdown`: writer returns markdown only; managers parse it into `ReportData`.

## Required Headings (Markdown Mode)

- `# <Report Title>`
- `## Executive Summary`
- `## Raw Notes`
- `## Detailed Agenda`
- `## Report`

## Optional Heading

- `## Follow-up Questions`

## End Marker

The final line must be exactly `## FINAL STEP`.

## Parsing Behavior (Markdown Mode)

Managers call `coerce_report_data()` to convert the writer output into a `ReportData` object.
If the output is plain markdown, the parser:

- Extracts the Executive Summary for `short_summary`
- Extracts bullet points under Follow-up Questions (optional)
- Preserves the full markdown in `markdown_report`

The filename is generated from the research topic using the standard naming rules.

## JSON Keys (Structured Mode)

When `writer_output_format` is `json`, the writer returns:
- `file_name`
- `research_topic`
- `short_summary`
- `markdown_report`
- `follow_up_questions`
