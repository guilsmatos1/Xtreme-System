#!/usr/bin/env bash
set -uo pipefail

PORT=8000
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cleanup() {
  if [[ -n "${UVICORN_PID:-}" ]]; then
    kill "$UVICORN_PID" 2>/dev/null || true
    wait "$UVICORN_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# ── check if port is already in use ───────────────────────────────────

if lsof -i ":$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[test-ui] Port $PORT already in use — assuming app is running"
  RUNNING_SERVER=true
else
  RUNNING_SERVER=false
  echo "[test-ui] Starting app server..."
  cd "$PROJECT_DIR"
  uv run uvicorn xtreme_system.api.core:app \
    --host 0.0.0.0 --port "$PORT" --proxy-headers &
  UVICORN_PID=$!

  for _ in $(seq 1 30); do
    if curl -s -o /dev/null "http://localhost:$PORT/ui/login" 2>/dev/null; then
      echo "[test-ui] Server ready"
      break
    fi
    sleep 1
  done
fi

# ── ensure admin password is correct ──────────────────────────────────

echo "[test-ui] Ensuring admin credentials..."
cd "$PROJECT_DIR"
uv run python -c "
from xtreme_system.usuario.core import Usuario
from xtreme_system.auth.core import hash_password
from xtreme_system.database.core import get_session
from sqlalchemy import update as sql_update
with next(get_session()) as s:
    s.execute(sql_update(Usuario).where(Usuario.username == 'admin').values(senha_hash=hash_password('Admin123!')))
    s.commit()
" 2>/dev/null || echo "[test-ui] Warning: could not reset admin password"

# ── run tests ─────────────────────────────────────────────────────────

echo "[test-ui] Running tests..."
cd "$PROJECT_DIR"
bash development/test-ui-flow.sh
EXIT_CODE=$?

if [[ "$RUNNING_SERVER" == false ]]; then
  cleanup
fi

exit $EXIT_CODE
