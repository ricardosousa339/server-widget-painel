#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
LOG_FILE="${SERVER_WIDGET_LOG_FILE:-/tmp/server-widget.log}"
HEALTH_URL="${SERVER_WIDGET_HEALTH_URL:-http://127.0.0.1:8000/health}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[erro] Ambiente virtual nao encontrado em $PYTHON_BIN"
  echo "[erro] Rode: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

health_code() {
  curl --max-time 1 -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || true
}

# Se o servidor estiver saudavel, nao faz nada.
if [[ "$(health_code)" == "200" ]]; then
  echo "[ok] Servidor ja ativo"
  exit 0
fi

# Se houver processo na porta 8000 mas sem health, reinicia.
if lsof -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  lsof -tiTCP:8000 -sTCP:LISTEN | xargs -r kill -9
  sleep 1
fi

nohup "$PYTHON_BIN" -m app.main > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

for _ in {1..10}; do
  sleep 1
  if [[ "$(health_code)" == "200" ]]; then
    echo "[ok] Servidor iniciado (PID $SERVER_PID)"
    exit 0
  fi
done

echo "[erro] Nao foi possivel subir servidor"
echo "[erro] Logs: $LOG_FILE"
exit 1
