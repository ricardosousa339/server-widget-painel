#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
LOG_FILE="/tmp/server-widget.log"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[erro] Ambiente virtual não encontrado em $PYTHON_BIN"
  echo "Crie/ative o .venv antes: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# Encerra qualquer processo escutando na porta 8000
if lsof -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  lsof -tiTCP:8000 -sTCP:LISTEN | xargs -r kill -9
fi

# Sobe em background
nohup "$PYTHON_BIN" -m app.main > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

HEALTH_URL="http://127.0.0.1:8000/health"
HTTP_CODE="000"

# Aguarda o servidor ficar pronto (até ~10s)
for _ in {1..10}; do
  sleep 1
  HTTP_CODE="$(curl --max-time 1 -s -o /tmp/server-widget-health.out -w "%{http_code}" "$HEALTH_URL" || true)"
  if [[ "$HTTP_CODE" == "200" ]]; then
    break
  fi
done

if [[ "$HTTP_CODE" == "200" ]]; then
  echo "[ok] Servidor reiniciado (PID $SERVER_PID)"
  echo "[ok] Health: 200"
  echo "[ok] Preview: http://127.0.0.1:8000/preview/painel"
  exit 0
fi

echo "[erro] Servidor iniciou, mas health retornou código: ${HTTP_CODE:-sem resposta}"
echo "[erro] Veja logs: $LOG_FILE"
exit 1
