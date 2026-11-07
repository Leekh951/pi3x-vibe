#!/usr/bin/env bash
# Start the home-GPU Pi3X server in the foreground.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME="${PI3X_RUNTIME:-/root/workspace/pi3x-runtime}"
exec "$RUNTIME/venv/bin/python" -u "$HERE/app.py"
