from pathlib import Path

import pytest

from scripts.llama_bench_instruct import (
    BenchResult,
    SetupConfig,
    build_result,
    discover_setups,
    filter_bench_extra_args,
    parse_bench_output,
    parse_env_value,
)


def test_parse_env_value_strips_inline_comments():
    assert parse_env_value("256 # 512") == "256"
    assert parse_env_value('"--parallel 2 --flash-attn on" # comment') == "--parallel 2 --flash-attn on"


def test_filter_bench_extra_args_keeps_only_bench_relevant_flags():
    extra_args = filter_bench_extra_args(
        '--parallel 2 --flash-attn on --temp 0.15 --top-k -1 --top-p 1.0 --mlock'
    )

    assert extra_args == ["-fa", "--mlock"]


def test_discover_setups_filters_api_and_local_by_default(tmp_path: Path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()

    (models_dir / "models.ministral.env").write_text(
        "LLM_INSTRUCT_MODEL_PATH=/mnt/models/Ministral-3-14B-Instruct-Q4_K_M.gguf\n",
        encoding="utf-8",
    )
    (models_dir / "models.openai-api.env").write_text(
        "LLM_INSTRUCT_MODEL_PATH=/mnt/models/gpt-oss-20b-mxfp4.gguf\n",
        encoding="utf-8",
    )
    (models_dir / "models.local.env").write_text(
        "LLM_INSTRUCT_MODEL_PATH=/models/local.gguf\n",
        encoding="utf-8",
    )

    setups = discover_setups(models_dir)

    assert [setup.name for setup in setups] == ["ministral"]


def test_parse_bench_output_extracts_pp_and_tg_rows():
    output = """
| model |       size |     params | backend | threads | test  |               t/s |
| ----- | ---------: | ---------: | ------- | ------: | ----- | ----------------: |
| foo.gguf |   8.00 GiB |    14.02 B | CUDA0 |       1 | pp512 |    1850.25 +- 8.11 |
| foo.gguf |   8.00 GiB |    14.02 B | CUDA0 |       1 | tg128 |      95.50 +- 0.70 |
"""

    rows = parse_bench_output(output)

    assert rows["pp512"].tokens_per_second == pytest.approx(1850.25)
    assert rows["tg128"].tokens_per_second == pytest.approx(95.50)


def test_build_result_computes_ttft_and_tpot():
    setup = SetupConfig(
        name="qwen",
        env_file=Path("models/models.qwen.env"),
        model_path="/mnt/models/Qwen3-14B-Q5_K_M.gguf",
        model_name="Qwen3-14B-Q5_K_M.gguf",
        quantization="Q5_K_M",
        ctx_size=32768,
        batch_size=256,
        ubatch_size=256,
        n_gpu_layers=70,
        bench_extra_args=("-fa",),
    )

    output = """
| model | size | params | backend | threads | test | t/s |
| ----- | ---: | -----: | ------- | ------: | ---- | --: |
| Qwen3-14B-Q5_K_M.gguf | 8.00 GiB | 14.02 B | CUDA0 | 1 | pp512 | 2048.00 +- 1.00 |
| Qwen3-14B-Q5_K_M.gguf | 8.00 GiB | 14.02 B | CUDA0 | 1 | tg128 | 128.00 +- 0.50 |
"""

    result = build_result(setup, output)

    assert isinstance(result, BenchResult)
    assert result.ttft_ms == pytest.approx(250.0)
    assert result.tpot_ms == pytest.approx(7.8125)


def test_build_result_requires_pp512_and_tg128():
    setup = SetupConfig(
        name="openai",
        env_file=Path("models/models.openai.env"),
        model_path="/mnt/models/gpt-oss-20b-mxfp4.gguf",
        model_name="gpt-oss-20b-mxfp4.gguf",
        quantization="mxfp4",
        ctx_size=32768,
        batch_size=256,
        ubatch_size=256,
        n_gpu_layers=70,
        bench_extra_args=(),
    )

    with pytest.raises(ValueError, match="Expected pp512 and tg128 rows"):
        build_result(
            setup,
            """
| model | size | params | backend | threads | test | t/s |
| ----- | ---: | -----: | ------- | ------: | ---- | --: |
| gpt-oss-20b-mxfp4.gguf | 12.00 GiB | 20.00 B | CUDA0 | 1 | pp512 | 1024.00 +- 1.00 |
""",
        )
