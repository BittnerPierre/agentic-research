#!/usr/bin/env bash
set -euo pipefail

MODE=smoke
STACK=dgx
source scripts/_docker_test_common.sh
run_docker_test
