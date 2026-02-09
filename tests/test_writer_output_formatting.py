from src.agents.schemas import ReportData
from src.agents.utils import (
    get_writer_output_formatting,
    get_writer_output_type,
)


def test_writer_output_formatting_json():
    formatting = get_writer_output_formatting("json")
    assert '"file_name"' in formatting
    assert '"research_topic"' in formatting
    assert '"short_summary"' in formatting
    assert '"markdown_report"' in formatting
    assert '"follow_up_questions"' in formatting


def test_writer_output_formatting_markdown():
    formatting = get_writer_output_formatting("markdown")
    assert "## Executive Summary" in formatting
    assert "## Raw Notes" in formatting
    assert "## Detailed Agenda" in formatting
    assert "## Report" in formatting
    assert "## FINAL STEP" in formatting


def test_writer_output_type_selection():
    assert get_writer_output_type("json") is ReportData
    assert get_writer_output_type("markdown") is str
