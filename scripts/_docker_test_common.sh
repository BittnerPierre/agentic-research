#!/usr/bin/env bash
set -euo pipefail

run_docker_test() {
  local mode="${MODE:-e2e}"
  local stack="${STACK:-local}"
  local env_file="models.env"
  local -a compose_files
  local config_path
  local query
  local manager_args=""

  if [ ! -f "${env_file}" ]; then
    echo "Error: ${env_file} not found. Copy models.env.example and configure it."
    exit 1
  fi

  case "${stack}" in
    local)
      compose_files=(-f docker-compose.yml -f docker-compose.local.yml)
      config_path="/app/configs/config-docker-local.yaml"
      if [ "${SKIP_LLAMA_CPP_BUILD:-0}" != "1" ]; then
        bash scripts/build_llama_cpp_arm64.sh
      else
        echo "Skipping llama.cpp build (SKIP_LLAMA_CPP_BUILD=1)."
      fi
      ;;
    dgx)
      compose_files=(-f docker-compose.yml -f docker-compose.dgx.yml)
      config_path="/app/configs/config-docker-dgx.yaml"
      ;;
    *)
      echo "Error: unknown STACK '${stack}'. Use STACK=local or STACK=dgx."
      exit 1
      ;;
  esac

  case "${mode}" in
    smoke)
      manager_args="--manager qa_manager"
      query="What is the key fact mentioned in the smoke test document?"
      ;;
    e2e)
      manager_args=""
      query="Smoke test: ${stack} docker stack"
      ;;
    *)
      echo "Error: unknown MODE '${mode}'. Use MODE=smoke or MODE=e2e."
      exit 1
      ;;
  esac

  local app_version
  app_version=$(git rev-parse --short HEAD 2>/dev/null || echo dev)

  docker compose "${compose_files[@]}" --env-file "${env_file}" build \
    --build-arg APP_VERSION="${app_version}" \
    dataprep agentic-research

  if [ "${stack}" = "local" ]; then
    docker compose "${compose_files[@]}" --env-file "${env_file}" up -d \
      chromadb dataprep llama-cpp-cpu
  else
    docker compose "${compose_files[@]}" --env-file "${env_file}" up -d \
      chromadb dataprep embeddings-gpu llm-instruct llm-reasoning
  fi

  # Avoid bash array compatibility issues on macOS (bash 3.x).
  docker compose "${compose_files[@]}" --env-file "${env_file}" run --rm agentic-research \
    agentic-research ${manager_args:+${manager_args}} --config "${config_path}" \
    --query "${query}"

  if ! docker compose "${compose_files[@]}" --env-file "${env_file}" logs agentic-research \
    | grep -q "chroma_query_documents"; then
    echo "Warning: chroma_query_documents not found in agentic-research logs."
  fi
}
