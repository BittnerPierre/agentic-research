import re

from src.agents.utils import parse_writer_markdown


def test_parse_writer_markdown_extracts_fields():
    markdown = """# AI in Education

## Executive Summary
This report analyzes the impact of AI on teaching practices and student outcomes. It highlights
benefits, risks, and open questions for further study.

## Raw Notes
- Source A: AI improves feedback cycles.

## Detailed Agenda
1. Context
2. Impacts

## Report
Longer body content here.

## Follow-up Questions
- How should institutions adapt curricula?
- What safeguards reduce bias?

## FINAL STEP
"""

    report = parse_writer_markdown(markdown, "AI in Education")

    assert report.research_topic == "AI in Education"
    assert report.short_summary.startswith("This report analyzes the impact of AI")
    assert report.follow_up_questions == [
        "How should institutions adapt curricula?",
        "What safeguards reduce bias?",
    ]
    assert report.markdown_report == markdown
    assert re.match(r"^ai_in_education_final_report_\d{8}_\d{6}\.md$", report.file_name)
