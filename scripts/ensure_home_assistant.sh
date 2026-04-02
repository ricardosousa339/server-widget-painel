#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HA_CONTAINER_NAME="${HA_CONTAINER_NAME:-server-widget-homeassistant}"
HA_IMAGE="${HA_IMAGE:-ghcr.io/home-assistant/home-assistant:stable}"
HA_PORT="${HA_PORT:-8123}"
HA_CONFIG_DIR="${HA_CONFIG_DIR:-$ROOT_DIR/data/homeassistant}"
HA_HEALTH_URL="${HA_HEALTH_URL:-http://127.0.0.1:${HA_PORT}/}"
HA_START_TIMEOUT_SECONDS="${HA_START_TIMEOUT_SECONDS:-300}"
HA_CURL_MAX_TIME="${HA_CURL_MAX_TIME:-2}"

health_code() {
  curl --max-time "$HA_CURL_MAX_TIME" -s -o /dev/null -w "%{http_code}" "$HA_HEALTH_URL" || true
}

is_healthy() {
  local code
  code="$(health_code)"
  [[ "$code" == "200" || "$code" == "302" || "$code" == "401" ]]
}

if ! command -v docker >/dev/null 2>&1; then
  echo "[erro] Docker nao encontrado no WSL."
  echo "[erro] Instale o Docker Desktop no Windows e habilite integracao WSL."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "[erro] Docker nao esta respondendo no WSL."
  echo "[erro] Inicie o Docker Desktop no Windows e tente novamente."
  exit 1
fi

mkdir -p "$HA_CONFIG_DIR"

if [[ -z "$(docker ps -a --format '{{.Names}}' | grep -Fx "$HA_CONTAINER_NAME" || true)" ]]; then
  echo "[info] Criando container do Home Assistant..."
  docker run -d \
    --name "$HA_CONTAINER_NAME" \
    --restart unless-stopped \
    --add-host host.docker.internal:host-gateway \
    -p "${HA_PORT}:8123" \
    -v "$HA_CONFIG_DIR:/config" \
    -e "TZ=${TZ:-America/Sao_Paulo}" \
    "$HA_IMAGE" >/dev/null
else
  if [[ -z "$(docker ps --format '{{.Names}}' | grep -Fx "$HA_CONTAINER_NAME" || true)" ]]; then
    echo "[info] Iniciando container existente do Home Assistant..."
    docker start "$HA_CONTAINER_NAME" >/dev/null
  fi
fi

if is_healthy; then
  echo "[ok] Home Assistant ja ativo"
  exit 0
fi

attempts=$((HA_START_TIMEOUT_SECONDS / 2))
if [[ "$attempts" -lt 1 ]]; then
  attempts=1
fi

for _ in $(seq 1 "$attempts"); do
  sleep 2
  if is_healthy; then
    echo "[ok] Home Assistant ativo em $HA_HEALTH_URL"
    exit 0
  fi
done

echo "[erro] Home Assistant nao ficou saudavel no tempo esperado"
echo "[info] Container: $HA_CONTAINER_NAME"
docker ps --filter "name=$HA_CONTAINER_NAME"
echo "[info] Ultimos logs:"
docker logs --tail 40 "$HA_CONTAINER_NAME" 2>/dev/null || true
exit 1
