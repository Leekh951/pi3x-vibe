#!/usr/bin/env bash
# One command after a container/PC restart: start the Pi3X server (if needed), then the Funnel.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME="${PI3X_RUNTIME:-/root/workspace/pi3x-runtime}" PORT="${PI3X_PORT:-7860}"
mkdir -p "$RUNTIME/logs"
if ! pgrep -f "[h]osting/local/app\.py" >/dev/null; then
  setsid "$HERE/start.sh" >>"$RUNTIME/logs/server.log" 2>&1 </dev/null &
  echo "Pi3X 서버 시작 중 (로그: $RUNTIME/logs/server.log)"
  for _ in $(seq 180); do
    curl -fs -o /dev/null "http://127.0.0.1:$PORT/config" && break
    pgrep -f "[h]osting/local/app\.py" >/dev/null || { tail -20 "$RUNTIME/logs/server.log"; exit 1; }
    sleep 1
  done
fi
curl -fs -o /dev/null "http://127.0.0.1:$PORT/config" && echo "Pi3X 서버 준비: http://127.0.0.1:$PORT"
exec "$HERE/tunnel.sh"
