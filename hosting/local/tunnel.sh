#!/usr/bin/env bash
# Publish the localhost Pi3X server at https://<hostname>.<tailnet>.ts.net via Tailscale Funnel.
# Userspace networking: this container shares the host network, so no TUN device,
# routes or DNS changes are made on the host. The first run prints login/approval URLs.
set -euo pipefail
RUNTIME="${PI3X_RUNTIME:-/root/workspace/pi3x-runtime}"
STATE="$RUNTIME/tailscale" PORT="${PI3X_PORT:-7860}" NAME="${PI3X_TS_HOSTNAME:-pi3x}"
SOCK="$STATE/tailscaled.sock"
ts() { "$RUNTIME/bin/tailscale" --socket="$SOCK" "$@"; }
mkdir -p "$STATE"

if ! pgrep -f "[t]ailscaled .*--statedir=$STATE" >/dev/null; then
  setsid "$RUNTIME/bin/tailscaled" --tun=userspace-networking --statedir="$STATE" \
    --socket="$SOCK" --port=0 >>"$STATE/tailscaled.log" 2>&1 </dev/null &
  for _ in $(seq 50); do [[ -S "$SOCK" ]] && break; sleep 0.2; done
fi

ts up --hostname="$NAME"      # waits for login on first run
ts funnel --bg "$PORT"         # first run asks to approve HTTPS + Funnel for the tailnet
ts funnel status
