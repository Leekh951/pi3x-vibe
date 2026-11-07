#!/usr/bin/env bash
# Stop public access first, then the GPU server. Tailscale login is kept for the next up.sh.
RUNTIME="${PI3X_RUNTIME:-/root/workspace/pi3x-runtime}"
"$RUNTIME/bin/tailscale" --socket="$RUNTIME/tailscale/tailscaled.sock" funnel reset 2>/dev/null || true
pkill -f "[t]ailscaled .*--statedir=$RUNTIME/tailscale" || true
pkill -f "[h]osting/local/app\.py" || true
echo "공개 주소와 Pi3X 서버를 중지했습니다."
