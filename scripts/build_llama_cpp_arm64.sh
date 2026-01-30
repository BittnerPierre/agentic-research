#!/usr/bin/env bash
set -euo pipefail

LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-/tmp/llama.cpp}"
FORCE_LLAMA_CPP_BUILD="${FORCE_LLAMA_CPP_BUILD:-0}"

if [ "${FORCE_LLAMA_CPP_BUILD}" = "0" ]; then
  if docker image inspect local/llama.cpp:server >/dev/null 2>&1; then
    echo "local/llama.cpp:server already exists. Set FORCE_LLAMA_CPP_BUILD=1 to rebuild."
    exit 0
  fi
fi

if [ -z "${LLAMA_CPP_PLATFORM:-}" ]; then
  case "$(uname -m)" in
    arm64|aarch64)
      LLAMA_CPP_PLATFORM="linux/arm64"
      ;;
    x86_64|amd64)
      LLAMA_CPP_PLATFORM="linux/amd64"
      ;;
    *)
      echo "Unsupported architecture: $(uname -m). Set LLAMA_CPP_PLATFORM manually." >&2
      exit 1
      ;;
  esac
fi

if [ ! -d "${LLAMA_CPP_DIR}/.git" ]; then
  git clone https://github.com/ggml-org/llama.cpp "${LLAMA_CPP_DIR}"
else
  git -C "${LLAMA_CPP_DIR}" fetch --all --prune
fi

DOCKERFILE_PATH="${LLAMA_CPP_DIR}/.devops/cpu.Dockerfile"
if [ ! -f "${DOCKERFILE_PATH}" ]; then
  echo "Missing ${DOCKERFILE_PATH}. Contents of .devops:" >&2
  ls -la "${LLAMA_CPP_DIR}/.devops" >&2 || true
  exit 1
fi

BUILD_DOCKERFILE="${DOCKERFILE_PATH}"
TEMP_DOCKERFILE=""
if [ "${LLAMA_CPP_PLATFORM}" = "linux/arm64" ]; then
  TEMP_DOCKERFILE="$(mktemp -t llama.cpp.cpu.Dockerfile.XXXXXX)"
  sed 's/-DGGML_CPU_ALL_VARIANTS=ON/-DGGML_CPU_ALL_VARIANTS=OFF/' \
    "${DOCKERFILE_PATH}" > "${TEMP_DOCKERFILE}"
  BUILD_DOCKERFILE="${TEMP_DOCKERFILE}"
fi

docker buildx create --use --name llama-builder 2>/dev/null || true

docker buildx build \
  --platform "${LLAMA_CPP_PLATFORM}" \
  -t local/llama.cpp:server \
  --target server \
  -f "${BUILD_DOCKERFILE}" \
  --load \
  "${LLAMA_CPP_DIR}"

if [ -n "${TEMP_DOCKERFILE}" ]; then
  rm -f "${TEMP_DOCKERFILE}"
fi
