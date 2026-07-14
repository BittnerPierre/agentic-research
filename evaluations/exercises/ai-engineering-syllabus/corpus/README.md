# Conceptual Exercise Corpus

The corpus is the downloaded content of the five fixed URLs in `test_files/syllabus.md`.
Third-party article bodies are not committed. `../source_manifest.yaml` freezes the
expected filenames and SHA-256 hashes so a URL changing in place cannot silently change
the benchmark.

At grading time, the five raw files must be present either here or in the run repository's
`data/` directory. `sources.json` citations must contain chunk document IDs that resolve
through `data/knowledge_db.json` to those raw files. A generated search summary with no
document IDs is not accepted as evidence.

To refresh the frozen corpus deliberately, download all five URLs, review source support
for every answer-key item, update all five hashes together, and treat the result as a new
benchmark version.
