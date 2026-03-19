#!/usr/bin/env bash
# Run llama-bench for each instruct setup and generate a Markdown/CSV comparison table.
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DEFAULT_SETUPS=("ministral" "mistralai" "glm" "qwen" "openai")
RUNS=3
OUTPUT_DIR=""
MODELS_RAW=""
INCLUDE_API=false
INCLUDE_LOCAL=false
KEEP_RAW=false
BUILD_IMAGE=false

usage() {
  echo "Usage: $0 [--setups a,b,c] [--output-dir DIR] [--runs N] [--build] [--include-api-setups] [--include-local] [--keep-raw]"
  echo ""
  echo "Examples:"
  echo "  $0"
  echo "  $0 --setups mistralai,qwen,openai --runs 5 --build"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --setups)
      MODELS_RAW="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --runs)
      RUNS="${2:-}"
      shift 2
      ;;
    --build)
      BUILD_IMAGE=true
      shift
      ;;
    --include-api-setups)
      INCLUDE_API=true
      shift
      ;;
    --include-local)
      INCLUDE_LOCAL=true
      shift
      ;;
    --keep-raw)
      KEEP_RAW=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if ! [[ "$RUNS" =~ ^[0-9]+$ ]] || [ "$RUNS" -lt 1 ]; then
  echo "Error: --runs must be a positive integer"
  exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
if [ -z "$OUTPUT_DIR" ]; then
  OUTPUT_DIR="${ROOT_DIR}/benchmarks/llama_bench_instruct_${TIMESTAMP}"
else
  OUTPUT_DIR=$(cd "$ROOT_DIR" && mkdir -p "$OUTPUT_DIR" && cd "$OUTPUT_DIR" && pwd)
fi

RAW_DIR="${OUTPUT_DIR}/raw"
mkdir -p "$RAW_DIR"

MARKDOWN_OUTPUT="${OUTPUT_DIR}/comparison_table.md"
CSV_OUTPUT="${OUTPUT_DIR}/comparison_table.csv"

SELECTED_SETUPS=()
if [ -n "$MODELS_RAW" ]; then
  IFS=',' read -r -a SELECTED_SETUPS <<< "$MODELS_RAW"
fi

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

to_lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

contains_setup() {
  local needle="$1"
  shift || true
  local item=""
  for item in "$@"; do
    if [ "$(trim "$item")" = "$needle" ]; then
      return 0
    fi
  done
  return 1
}

extract_setup_name() {
  local env_file="$1"
  local filename
  filename=$(basename "$env_file")
  filename="${filename#models.}"
  filename="${filename%.env}"
  printf '%s' "$filename"
}

extract_quantization() {
  local model_path="$1"
  local filename
  filename=$(basename "$model_path")

  if [[ "$filename" =~ -(Q[0-9]+(_[A-Z0-9]+)*) ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
    return 0
  fi

  if [[ "$filename" =~ -(mxfp[0-9]+) ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
    return 0
  fi

  if [[ "$filename" == *BF16* ]]; then
    printf 'BF16'
    return 0
  fi

  printf 'unknown'
}

extract_bench_extra_args() {
  local extra_params="$1"
  local -a tokens=()
  local -a filtered=()
  local index=0
  local token=""
  local next_value=""

  if [ -z "$extra_params" ]; then
    return 0
  fi

  # shellcheck disable=SC2206
  tokens=($extra_params)

  while [ $index -lt ${#tokens[@]} ]; do
    token="${tokens[$index]}"

    case "$token" in
      -fa)
        filtered+=("-fa")
        ;;
      --flash-attn)
        next_value="on"
        if [ $((index + 1)) -lt ${#tokens[@]} ]; then
          next_value=$(to_lower "${tokens[$((index + 1))]}")
        fi
        case "$next_value" in
          on|true|1|yes)
            filtered+=("-fa")
            index=$((index + 1))
            ;;
          off|false|0|no)
            index=$((index + 1))
            ;;
          *)
            filtered+=("-fa")
            ;;
        esac
        ;;
      --mlock|--no-mmap)
        filtered+=("$token")
        ;;
    esac

    index=$((index + 1))
  done

  if [ ${#filtered[@]} -gt 0 ]; then
    printf '%s\n' "${filtered[@]}"
  fi
}

discover_env_files() {
  local -a env_files=()
  local env_file=""
  local setup_name=""

  if [ ${#SELECTED_SETUPS[@]} -gt 0 ]; then
    local selected=""
    for selected in "${SELECTED_SETUPS[@]}"; do
      selected="$(trim "$selected")"
      [ -z "$selected" ] && continue
      env_file="${ROOT_DIR}/models/models.${selected}.env"
      if [ ! -f "$env_file" ]; then
        echo "Error: ${env_file} not found"
        exit 1
      fi
      env_files+=("$env_file")
    done
    printf '%s\n' "${env_files[@]}"
    return 0
  fi

  local default=""
  for default in "${DEFAULT_SETUPS[@]}"; do
    env_file="${ROOT_DIR}/models/models.${default}.env"
    [ -f "$env_file" ] && env_files+=("$env_file")
  done

  for env_file in "${ROOT_DIR}"/models/models.*.env; do
    [ -f "$env_file" ] || continue
    setup_name=$(extract_setup_name "$env_file")
    if contains_setup "$setup_name" "${DEFAULT_SETUPS[@]}"; then
      continue
    fi
    if [ "$setup_name" = "local" ] && [ "$INCLUDE_LOCAL" != true ]; then
      continue
    fi
    if [[ "$setup_name" == *-api ]] && [ "$INCLUDE_API" != true ]; then
      continue
    fi
    env_files+=("$env_file")
  done

  printf '%s\n' "${env_files[@]}"
}

parse_bench_value() {
  local raw="$1"
  raw="${raw## }"
  raw="${raw%% +- *}"
  printf '%s' "$raw" | tr -d ' '
}

append_csv_row() {
  local setup_name="$1"
  local model_name="$2"
  local quantization="$3"
  local ctx_size="$4"
  local batch_size="$5"
  local ubatch_size="$6"
  local backend="$7"
  local threads="$8"
  local pp512="$9"
  local ttft_ms="${10}"
  local tg128="${11}"
  local tpot_ms="${12}"

  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "$setup_name" "$model_name" "$quantization" "$ctx_size" "$batch_size" "$ubatch_size" \
    "$backend" "$threads" "$pp512" "$ttft_ms" "$tg128" "$tpot_ms" >> "$CSV_OUTPUT"
}

append_markdown_row() {
  local setup_name="$1"
  local model_name="$2"
  local quantization="$3"
  local ctx_size="$4"
  local batch_size="$5"
  local ubatch_size="$6"
  local pp512="$7"
  local ttft_ms="$8"
  local tg128="$9"
  local tpot_ms="${10}"

  printf '| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |\n' \
    "$setup_name" "$model_name" "$quantization" "$ctx_size" "$batch_size" "$ubatch_size" \
    "$pp512" "$ttft_ms" "$tg128" "$tpot_ms" >> "$MARKDOWN_OUTPUT"
}

printf '# Llama Bench Instruct Comparison\n\n' > "$MARKDOWN_OUTPUT"
printf '| Setup | Model | Quant | Ctx | Batch | UBatch | PP512 tok/s | TTFT ms | TG128 tok/s | TPOT ms/token |\n' >> "$MARKDOWN_OUTPUT"
printf '| ----- | ----- | ----- | --: | ----: | -----: | ----------: | ------: | ----------: | ------------: |\n' >> "$MARKDOWN_OUTPUT"

printf 'setup,model,quantization,ctx_size,batch_size,ubatch_size,backend,threads,pp512_tokens_per_second,ttft_ms,tg128_tokens_per_second,tpot_ms_per_token\n' > "$CSV_OUTPUT"

FAILURES=0

ENV_FILES=()
while IFS= read -r env_file; do
  [ -n "$env_file" ] && ENV_FILES+=("$env_file")
done < <(discover_env_files)

if [ ${#ENV_FILES[@]} -eq 0 ]; then
  echo "Error: no instruct setup found"
  exit 1
fi

echo "========================================"
echo "Llama Bench Instruct"
echo "========================================"
echo "Output directory: ${OUTPUT_DIR}"
echo "Runs per setup: ${RUNS}"
echo "Setups:"
for env_file in "${ENV_FILES[@]}"; do
  echo "  - $(extract_setup_name "$env_file")"
done
echo ""

for env_file in "${ENV_FILES[@]}"; do
  setup_name=$(extract_setup_name "$env_file")

  unset MODELS_DIR LLM_INSTRUCT_MODEL_PATH LLM_INSTRUCT_CTX_SIZE LLM_INSTRUCT_BATCH_SIZE \
    LLM_INSTRUCT_UBATCH_SIZE LLM_INSTRUCT_N_GPU_LAYERS LLM_INSTRUCT_EXTRA_PARAMS

  # shellcheck disable=SC1090
  source "$env_file"

  model_path="${LLM_INSTRUCT_MODEL_PATH:-}"
  if [ -z "$model_path" ]; then
    echo "Skipping ${setup_name}: LLM_INSTRUCT_MODEL_PATH not set"
    continue
  fi

  model_name=$(basename "$model_path")
  quantization=$(extract_quantization "$model_path")
  ctx_size="${LLM_INSTRUCT_CTX_SIZE:-32768}"
  batch_size="${LLM_INSTRUCT_BATCH_SIZE:-512}"
  ubatch_size="${LLM_INSTRUCT_UBATCH_SIZE:-512}"
  n_gpu_layers="${LLM_INSTRUCT_N_GPU_LAYERS:-70}"

  BENCH_EXTRA_ARGS=()
  while IFS= read -r arg; do
    [ -n "$arg" ] && BENCH_EXTRA_ARGS+=("$arg")
  done < <(extract_bench_extra_args "${LLM_INSTRUCT_EXTRA_PARAMS:-}")

  RAW_OUTPUT_FILE="${RAW_DIR}/${setup_name}.txt"
  STDERR_OUTPUT_FILE="${RAW_DIR}/${setup_name}.stderr.txt"
  ERROR_OUTPUT_FILE="${RAW_DIR}/${setup_name}.error.txt"

  echo "[llama-bench] setup=${setup_name} model=${model_name} ctx=${ctx_size} batch=${batch_size} ubatch=${ubatch_size}"

  DOCKER_CMD=(
    docker compose
    -f "${ROOT_DIR}/docker-compose.yml"
    -f "${ROOT_DIR}/docker-compose.dgx.yml"
    --env-file "$env_file"
    run --rm --no-deps
  )

  if [ "$BUILD_IMAGE" = true ]; then
    DOCKER_CMD+=(--build)
  fi

  DOCKER_CMD+=(
    --entrypoint /app/llama-bench
    llm-instruct
    -m "$model_path"
    -p 512
    -n 128
    -r "$RUNS"
    -c "$ctx_size"
    -b "$batch_size"
    -ub "$ubatch_size"
    -ngl "$n_gpu_layers"
  )

  if [ ${#BENCH_EXTRA_ARGS[@]} -gt 0 ]; then
    DOCKER_CMD+=("${BENCH_EXTRA_ARGS[@]}")
  fi

  if ! "${DOCKER_CMD[@]}" >"$RAW_OUTPUT_FILE" 2>"$STDERR_OUTPUT_FILE"; then
    echo "llama-bench failed for ${setup_name}" | tee "$ERROR_OUTPUT_FILE"
    FAILURES=$((FAILURES + 1))
    continue
  fi

  PP512_LINE=$(awk -F'|' '/^\|/ { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $6); if ($6 == "pp512") { print; exit } }' "$RAW_OUTPUT_FILE")
  TG128_LINE=$(awk -F'|' '/^\|/ { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $6); if ($6 == "tg128") { print; exit } }' "$RAW_OUTPUT_FILE")

  if [ -z "$PP512_LINE" ] || [ -z "$TG128_LINE" ]; then
    {
      echo "Missing pp512 or tg128 output for ${setup_name}"
      echo ""
      cat "$RAW_OUTPUT_FILE"
    } > "$ERROR_OUTPUT_FILE"
    FAILURES=$((FAILURES + 1))
    continue
  fi

  backend=$(printf '%s\n' "$PP512_LINE" | awk -F'|' '{ gsub(/^[[:space:]]+|[[:space:]]+$/, "", $4); print $4 }')
  threads=$(printf '%s\n' "$PP512_LINE" | awk -F'|' '{ gsub(/^[[:space:]]+|[[:space:]]+$/, "", $5); print $5 }')
  pp512_raw=$(printf '%s\n' "$PP512_LINE" | awk -F'|' '{ gsub(/^[[:space:]]+|[[:space:]]+$/, "", $7); print $7 }')
  tg128_raw=$(printf '%s\n' "$TG128_LINE" | awk -F'|' '{ gsub(/^[[:space:]]+|[[:space:]]+$/, "", $7); print $7 }')

  pp512=$(parse_bench_value "$pp512_raw")
  tg128=$(parse_bench_value "$tg128_raw")

  ttft_ms=$(awk -v value="$pp512" 'BEGIN { printf "%.2f", (512 / value) * 1000 }')
  tpot_ms=$(awk -v value="$tg128" 'BEGIN { printf "%.2f", 1000 / value }')

  append_markdown_row "$setup_name" "$model_name" "$quantization" "$ctx_size" "$batch_size" "$ubatch_size" "$pp512" "$ttft_ms" "$tg128" "$tpot_ms"
  append_csv_row "$setup_name" "$model_name" "$quantization" "$ctx_size" "$batch_size" "$ubatch_size" "$backend" "$threads" "$pp512" "$ttft_ms" "$tg128" "$tpot_ms"

  if [ "$KEEP_RAW" != true ]; then
    rm -f "$RAW_OUTPUT_FILE"
  fi
done

{
  echo ""
  echo "TTFT is derived from pp512 as 512 / tok_s * 1000."
  echo "TPOT is derived from tg128 as 1000 / tok_s."
} >> "$MARKDOWN_OUTPUT"

echo ""
echo "Markdown: ${MARKDOWN_OUTPUT}"
echo "CSV: ${CSV_OUTPUT}"

if [ "$FAILURES" -gt 0 ]; then
  echo "Failures: ${FAILURES}"
  exit 1
fi
