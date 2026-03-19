#!/usr/bin/env python3
"""Run llama-bench across the project's instruct GGUF setups and build a comparison table."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT_DIR / "models"
COMPOSE_FILES = (ROOT_DIR / "docker-compose.yml", ROOT_DIR / "docker-compose.dgx.yml")
DEFAULT_SETUP_ORDER = ("ministral", "mistralai", "glm", "qwen", "openai")


@dataclasses.dataclass(frozen=True)
class SetupConfig:
    name: str
    env_file: Path
    model_path: str
    model_name: str
    quantization: str
    ctx_size: int
    batch_size: int
    ubatch_size: int
    n_gpu_layers: int
    bench_extra_args: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class BenchRow:
    model: str
    size: str
    params: str
    backend: str
    threads: str
    test: str
    tokens_per_second: float
    raw_tokens_per_second: str


@dataclasses.dataclass(frozen=True)
class BenchResult:
    setup: SetupConfig
    pp512: BenchRow
    tg128: BenchRow

    @property
    def ttft_ms(self) -> float:
        return 512.0 / self.pp512.tokens_per_second * 1000.0

    @property
    def tpot_ms(self) -> float:
        return 1000.0 / self.tg128.tokens_per_second


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run llama-bench in the project's llama.cpp Docker image for each instruct setup and "
            "generate a Markdown/CSV comparison table based on pp512 (TTFT proxy) and tg128 "
            "(TPOT proxy)."
        )
    )
    parser.add_argument(
        "--setups",
        help="Comma-separated setup names to benchmark. Default: all instruct setups in models/.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory where raw outputs and comparison tables will be written.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of repetitions passed to llama-bench via -r. Default: 3.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Pass --build to docker compose run so the llama.cpp image is rebuilt if needed.",
    )
    parser.add_argument(
        "--include-api-setups",
        action="store_true",
        help="Include duplicated *-api env files. They are skipped by default.",
    )
    parser.add_argument(
        "--include-local",
        action="store_true",
        help="Include the local CPU-only setup. It is skipped by default.",
    )
    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="Keep successful raw benchmark stdout files. Failures are always kept.",
    )
    return parser.parse_args()


def extract_setup_name(env_path: Path) -> str:
    match = re.fullmatch(r"models\.(.+)\.env", env_path.name)
    if not match:
        raise ValueError(f"Unsupported env filename: {env_path.name}")
    return match.group(1)


def load_env_file(env_path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = parse_env_value(raw_value.strip())
        env_vars[key] = value

    return env_vars


def parse_env_value(raw_value: str) -> str:
    if not raw_value:
        return ""

    if raw_value[0] in {'"', "'"}:
        quote = raw_value[0]
        escaped = False
        chars: list[str] = []
        for char in raw_value[1:]:
            if escaped:
                chars.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                return "".join(chars)
            chars.append(char)
        return "".join(chars)

    return re.split(r"\s+#", raw_value, maxsplit=1)[0].strip()


def extract_quantization(model_path: str) -> str:
    filename = os.path.basename(model_path)

    quant_match = re.search(r"-(Q\d+(?:_[A-Z0-9]+)*)", filename)
    if quant_match:
        return quant_match.group(1)

    quant_match = re.search(r"-(mxfp\d+)", filename)
    if quant_match:
        return quant_match.group(1)

    if "BF16" in filename:
        return "BF16"

    return "unknown"


def build_setup_config(env_path: Path) -> SetupConfig:
    env_vars = load_env_file(env_path)

    model_path = env_vars["LLM_INSTRUCT_MODEL_PATH"]
    extra_args = tuple(filter_bench_extra_args(env_vars.get("LLM_INSTRUCT_EXTRA_PARAMS", "")))

    return SetupConfig(
        name=extract_setup_name(env_path),
        env_file=env_path,
        model_path=model_path,
        model_name=os.path.basename(model_path),
        quantization=extract_quantization(model_path),
        ctx_size=int(env_vars.get("LLM_INSTRUCT_CTX_SIZE", "32768")),
        batch_size=int(env_vars.get("LLM_INSTRUCT_BATCH_SIZE", "512")),
        ubatch_size=int(env_vars.get("LLM_INSTRUCT_UBATCH_SIZE", "512")),
        n_gpu_layers=int(env_vars.get("LLM_INSTRUCT_N_GPU_LAYERS", "70")),
        bench_extra_args=extra_args,
    )


def filter_bench_extra_args(extra_params: str) -> list[str]:
    tokens = shlex.split(extra_params)
    bench_args: list[str] = []
    index = 0

    while index < len(tokens):
        token = tokens[index]

        if token in {"-fa", "--flash-attn"}:
            next_value = tokens[index + 1].lower() if index + 1 < len(tokens) else "on"
            if token == "-fa":
                bench_args.append("-fa")
            elif next_value in {"1", "true", "on", "yes"}:
                bench_args.append("-fa")
                index += 1
            elif next_value in {"0", "false", "off", "no"}:
                index += 1
            else:
                bench_args.append("-fa")
            index += 1
            continue

        if token in {"--no-mmap", "--mlock"}:
            bench_args.append(token)
            index += 1
            continue

        index += 1

    return bench_args


def discover_setups(
    models_dir: Path,
    selected: set[str] | None = None,
    include_api: bool = False,
    include_local: bool = False,
) -> list[SetupConfig]:
    setups: list[SetupConfig] = []

    for env_path in sorted(models_dir.glob("models.*.env")):
        name = extract_setup_name(env_path)
        if not include_local and name == "local":
            continue
        if not include_api and name.endswith("-api"):
            continue
        if selected and name not in selected:
            continue

        env_vars = load_env_file(env_path)
        if "LLM_INSTRUCT_MODEL_PATH" not in env_vars:
            continue

        setups.append(build_setup_config(env_path))

    if selected:
        found = {setup.name for setup in setups}
        missing = sorted(selected - found)
        if missing:
            raise ValueError(f"Unknown or filtered setup(s): {', '.join(missing)}")

    order_index = {name: index for index, name in enumerate(DEFAULT_SETUP_ORDER)}
    return sorted(
        setups,
        key=lambda setup: (order_index.get(setup.name, len(order_index)), setup.name),
    )


def build_output_dir(user_value: str | None) -> Path:
    if user_value:
        return Path(user_value).expanduser().resolve()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (ROOT_DIR / "benchmarks" / f"llama_bench_instruct_{timestamp}").resolve()


def run_benchmark(setup: SetupConfig, runs: int, should_build: bool) -> tuple[str, str]:
    compose_args = [
        "docker",
        "compose",
        "-f",
        str(COMPOSE_FILES[0]),
        "-f",
        str(COMPOSE_FILES[1]),
        "--env-file",
        str(setup.env_file),
        "run",
        "--rm",
        "--no-deps",
    ]
    if should_build:
        compose_args.append("--build")
    compose_args.extend(
        [
            "--entrypoint",
            "/app/llama-bench",
            "llm-instruct",
            "-m",
            setup.model_path,
            "-p",
            "512",
            "-n",
            "128",
            "-r",
            str(runs),
            "-c",
            str(setup.ctx_size),
            "-b",
            str(setup.batch_size),
            "-ub",
            str(setup.ubatch_size),
            "-ngl",
            str(setup.n_gpu_layers),
            *setup.bench_extra_args,
        ]
    )

    completed = subprocess.run(
        compose_args,
        cwd=ROOT_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"llama-bench failed for {setup.name} with exit code {completed.returncode}.\n"
            f"Command: {' '.join(shlex.quote(arg) for arg in compose_args)}\n"
            f"stderr:\n{completed.stderr.strip()}"
        )
    return completed.stdout, completed.stderr


def parse_bench_output(text: str) -> dict[str, BenchRow]:
    rows: dict[str, BenchRow] = {}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 7:
            continue
        if cells[0] == "model" or cells[5] == "test":
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if not re.fullmatch(r"(pp|tg)\d+", cells[5]):
            continue

        rows[cells[5]] = BenchRow(
            model=cells[0],
            size=cells[1],
            params=cells[2],
            backend=cells[3],
            threads=cells[4],
            test=cells[5],
            tokens_per_second=parse_tokens_per_second(cells[6]),
            raw_tokens_per_second=cells[6],
        )

    return rows


def parse_tokens_per_second(value: str) -> float:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", value.replace(",", ""))
    if not match:
        raise ValueError(f"Unable to parse tokens/s value: {value}")
    return float(match.group(1))


def build_result(setup: SetupConfig, text: str) -> BenchResult:
    rows = parse_bench_output(text)
    if "pp512" not in rows or "tg128" not in rows:
        raise ValueError(
            f"Expected pp512 and tg128 rows for {setup.name}, got: {', '.join(sorted(rows)) or 'none'}"
        )
    return BenchResult(setup=setup, pp512=rows["pp512"], tg128=rows["tg128"])


def write_markdown(results: list[BenchResult], output_path: Path) -> None:
    lines = [
        "# Llama Bench Instruct Comparison",
        "",
        "| Setup | Model | Quant | Ctx | Batch | UBatch | PP512 tok/s | TTFT ms | TG128 tok/s | TPOT ms/token |",
        "| ----- | ----- | ----- | --: | ----: | -----: | ----------: | ------: | ----------: | ------------: |",
    ]

    for result in results:
        lines.append(
            "| "
            f"{result.setup.name} | "
            f"{result.setup.model_name} | "
            f"{result.setup.quantization} | "
            f"{result.setup.ctx_size} | "
            f"{result.setup.batch_size} | "
            f"{result.setup.ubatch_size} | "
            f"{result.pp512.tokens_per_second:.2f} | "
            f"{result.ttft_ms:.2f} | "
            f"{result.tg128.tokens_per_second:.2f} | "
            f"{result.tpot_ms:.2f} |"
        )

    lines.extend(
        [
            "",
            "TTFT is derived from pp512 as 512 / tok_s * 1000.",
            "TPOT is derived from tg128 as 1000 / tok_s.",
            "",
        ]
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_csv(results: list[BenchResult], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "setup",
                "model",
                "quantization",
                "ctx_size",
                "batch_size",
                "ubatch_size",
                "backend",
                "threads",
                "pp512_tokens_per_second",
                "ttft_ms",
                "tg128_tokens_per_second",
                "tpot_ms_per_token",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "setup": result.setup.name,
                    "model": result.setup.model_name,
                    "quantization": result.setup.quantization,
                    "ctx_size": result.setup.ctx_size,
                    "batch_size": result.setup.batch_size,
                    "ubatch_size": result.setup.ubatch_size,
                    "backend": result.pp512.backend,
                    "threads": result.pp512.threads,
                    "pp512_tokens_per_second": f"{result.pp512.tokens_per_second:.6f}",
                    "ttft_ms": f"{result.ttft_ms:.6f}",
                    "tg128_tokens_per_second": f"{result.tg128.tokens_per_second:.6f}",
                    "tpot_ms_per_token": f"{result.tpot_ms:.6f}",
                }
            )


def main() -> int:
    args = parse_args()

    selected = None
    if args.setups:
        selected = {item.strip() for item in args.setups.split(",") if item.strip()}

    setups = discover_setups(
        MODELS_DIR,
        selected=selected,
        include_api=args.include_api_setups,
        include_local=args.include_local,
    )
    if not setups:
        raise SystemExit("No instruct setups found to benchmark.")

    output_dir = build_output_dir(args.output_dir)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    successes: list[BenchResult] = []
    failures: list[tuple[str, str]] = []

    for setup in setups:
        print(
            f"[llama-bench] setup={setup.name} model={setup.model_name} "
            f"ctx={setup.ctx_size} batch={setup.batch_size} ubatch={setup.ubatch_size}",
            file=sys.stderr,
        )
        try:
            stdout, stderr = run_benchmark(setup, runs=args.runs, should_build=args.build)
            raw_file = raw_dir / f"{setup.name}.txt"
            raw_file.write_text(stdout, encoding="utf-8")
            if stderr.strip():
                (raw_dir / f"{setup.name}.stderr.txt").write_text(stderr, encoding="utf-8")

            successes.append(build_result(setup, stdout))
            if not args.keep_raw:
                raw_file.unlink(missing_ok=True)
        except Exception as exc:
            failure_text = str(exc)
            failures.append((setup.name, failure_text))
            (raw_dir / f"{setup.name}.error.txt").write_text(failure_text, encoding="utf-8")
            print(f"[llama-bench] failed for {setup.name}: {failure_text}", file=sys.stderr)

    successes.sort(key=lambda result: result.ttft_ms)

    markdown_output = output_dir / "comparison_table.md"
    csv_output = output_dir / "comparison_table.csv"
    write_markdown(successes, markdown_output)
    write_csv(successes, csv_output)

    print(markdown_output.read_text(encoding="utf-8"))
    print(f"Markdown: {markdown_output}", file=sys.stderr)
    print(f"CSV: {csv_output}", file=sys.stderr)

    if failures:
        print("", file=sys.stderr)
        print("Failures:", file=sys.stderr)
        for setup_name, failure_text in failures:
            print(f"- {setup_name}: {failure_text}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
