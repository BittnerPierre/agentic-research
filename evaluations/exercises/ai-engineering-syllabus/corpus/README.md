# Conceptual exercise corpus (not committed)

The ground-truth corpus for this exercise is the **5 External References** listed in
`test_files/syllabus.md` (huyenchip agents, Anthropic multi-agent, OpenAI text-gen
docs, two Medium articles). Their full text is **not committed** (third-party
content) — the deterministic grader needs them locally to build the fabrication
whitelist and to check retrieval-vs-writer root cause.

To populate this folder:

1. Run the exercise once (the workflow downloads the 5 URLs):
   `uv run agentic-research --config configs/tests/config-gpt54mini-chroma-decomposed.yaml \
      --syllabus test_files/syllabus.md --vector-store bench-aieng --output-dir output/bench-aieng/`
2. Copy the downloaded articles from `data/` into this folder:
   `cp data/Agents_1.md data/Text_generation.md data/Advanced_Retrieval_*.md \
      data/Building_Systems_with_the_ChatGPT_API_*.md data/How_we_built_our_multi_*.md \
      evaluations/exercises/ai-engineering-syllabus/corpus/`

The grader (`deterministic_grade.py`) then uses these as the corpus whitelist.
