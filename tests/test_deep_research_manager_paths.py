from pathlib import Path

from src.agents.schemas import ResearchInfo
from src.deep_research_manager import DeepResearchManager


def _build_manager(tmp_path: Path) -> DeepResearchManager:
    manager = DeepResearchManager()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    manager.research_info = ResearchInfo(
        temp_dir=str(tmp_path),
        output_dir=str(output_dir),
        search_results=[],
    )
    return manager


def test_normalize_search_result_path_accepts_existing_temp_file(tmp_path: Path):
    summary_file = tmp_path / "mips_summary.txt"
    summary_file.write_text("content", encoding="utf-8")
    manager = _build_manager(tmp_path)

    resolved = manager._normalize_search_result_path("mips_summary.txt")

    assert resolved == str(summary_file.resolve())


def test_normalize_search_result_path_rejects_absolute_outside_temp(tmp_path: Path):
    outside_file = tmp_path.parent / "doc__2205.11916__Large_Language_Models_are_Zero.md"
    outside_file.write_text("outside", encoding="utf-8")
    manager = _build_manager(tmp_path)

    resolved = manager._normalize_search_result_path(str(outside_file))

    assert resolved is None


def test_normalize_search_result_path_rejects_unknown_file(tmp_path: Path):
    manager = _build_manager(tmp_path)

    resolved = manager._normalize_search_result_path("missing_file.txt")

    assert resolved is None


def test_normalize_search_result_path_adds_txt_extension_when_missing(tmp_path: Path):
    summary_file = tmp_path / "rewoo_vs_mips.txt"
    summary_file.write_text("content", encoding="utf-8")
    manager = _build_manager(tmp_path)

    resolved = manager._normalize_search_result_path("rewoo_vs_mips")

    assert resolved == str(summary_file.resolve())
