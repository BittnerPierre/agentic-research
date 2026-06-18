"""RED tests for knowledge-base identity contracts."""

from src.dataprep.models import KnowledgeDatabase, KnowledgeEntry


def test_knowledge_entry_requires_stable_kb_id_distinct_from_display_name():
    assert "kb_id" in KnowledgeEntry.model_fields


def test_same_display_name_from_web_and_local_require_distinct_kb_ids():
    db = KnowledgeDatabase()

    db.add_entry(
        KnowledgeEntry(
            url="https://arxiv.org/pdf/2306.02171.pdf",
            filename="2306.02171.pdf",
            source_type="url",
            source_path="https://arxiv.org/pdf/2306.02171.pdf",
            title="Paper from web",
        )
    )
    db.add_entry(
        KnowledgeEntry(
            url="file:///Users/pierre/Documents/papers/2306.02171.pdf",
            filename="2306.02171.pdf",
            source_type="local_file",
            source_path="/Users/pierre/Documents/papers/2306.02171.pdf",
            title="Paper from local disk",
        )
    )

    kb_ids = {entry.kb_id for entry in db.entries}

    assert len(db.entries) == 2
    assert len(kb_ids) == 2
