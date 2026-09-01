"""extract_model_name must keep multi-segment vLLM/HF model ids intact (issue #196).

`openai/` here is a TRANSPORT prefix (OpenAI-compatible API), not a vendor. A
model served by vLLM is named by its HF repo id, which itself contains a slash
(`org/repo`), so `openai/mistralai/Mistral-Small-4` must resolve to the full
`mistralai/Mistral-Small-4`, not the truncated `mistralai`.
"""

from src.agents.utils import extract_model_name


def test_openai_single_segment_unchanged():
    assert extract_model_name("openai/gpt-4.1-mini") == "gpt-4.1-mini"


def test_openai_vllm_repo_id_keeps_all_segments():
    assert (
        extract_model_name("openai/mistralai/Mistral-Small-4-119B-2603-NVFP4")
        == "mistralai/Mistral-Small-4-119B-2603-NVFP4"
    )
    assert extract_model_name("openai/Qwen/Qwen3.6-35B-A3B-FP8") == "Qwen/Qwen3.6-35B-A3B-FP8"
    assert (
        extract_model_name("openai/cyankiwi/MiniMax-M2.7-AWQ-4bit")
        == "cyankiwi/MiniMax-M2.7-AWQ-4bit"
    )


def test_litellm_provider_stripped_model_kept():
    assert (
        extract_model_name("litellm/anthropic/claude-3-7-sonnet-20250219")
        == "claude-3-7-sonnet-20250219"
    )
    # A provider whose model id itself has a slash keeps the remainder.
    assert extract_model_name("litellm/openrouter/anthropic/claude-3") == "anthropic/claude-3"


def test_bare_model_name_unchanged():
    assert extract_model_name("gpt-5-mini") == "gpt-5-mini"
