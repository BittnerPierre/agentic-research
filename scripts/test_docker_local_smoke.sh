#!/usr/bin/env bash
set -euo pipefail

MODE=smoke
STACK=local
source scripts/_docker_test_common.sh
run_docker_test
