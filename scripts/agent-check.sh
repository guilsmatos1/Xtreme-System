#!/usr/bin/env bash
set -euo pipefail

run_quiet() {
  local label="$1"
  shift
  local output
  output="$(mktemp)"
  if "$@" >"${output}" 2>&1; then
    rm -f "${output}"
    return 0
  fi

  printf '%s\n\n' "agent-check: ${label} failed" >&2
  tail -c 12000 "${output}" >&2
  rm -f "${output}"
  return 1
}

run_quiet "ruff check" uv run ruff check .
run_quiet "ruff format" uv run ruff format . --check
run_quiet "mypy" uv run mypy
run_quiet "pytest" uv run pytest -q --disable-warnings

printf '%s\n' "agent-check: ok"
