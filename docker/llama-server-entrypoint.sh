#!/usr/bin/env sh
set -e

if [ -n "${EXTRA_PARAMS-}" ]; then
  # Allow space-separated extra params from env.
  # shellcheck disable=SC2086
  set -- "$@" $EXTRA_PARAMS
fi

exec /app/llama-server "$@"
