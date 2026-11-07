#!/usr/bin/env bash
# Prepare the home-GPU Pi3X server. Safe to re-run, including in a recreated
# container: everything except apt packages lives on the mounted workspace.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME="${PI3X_RUNTIME:-/root/workspace/pi3x-runtime}"
# Keep these in step with hosting/huggingface/app.py and colab/backend.py.
PI3_REVISION="9fa3ddb3f8d53041f8b2738df404f62223bbaa7b"
WEIGHTS_REVISION="bb1deea4d7423de5b30691739cb451a3f57dc1d5"
TORCH_INDEX="https://download.pytorch.org/whl/cu128"
TAILSCALE_VERSION="1.104.5"

missing=()
for tool in git curl; do command -v "$tool" >/dev/null || missing+=("$tool"); done
if ((${#missing[@]})); then
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends "${missing[@]}" ca-certificates
fi

mkdir -p "$RUNTIME"
export UV_INSTALL_DIR="$RUNTIME/bin" UV_PYTHON_INSTALL_DIR="$RUNTIME/python"
export UV_CACHE_DIR="$RUNTIME/uv-cache" INSTALLER_NO_MODIFY_PATH=1
if [[ ! -x "$RUNTIME/bin/uv" ]]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
UV="$RUNTIME/bin/uv"

[[ -x "$RUNTIME/venv/bin/python" ]] || "$UV" venv --python 3.10 "$RUNTIME/venv"
"$UV" pip install --python "$RUNTIME/venv/bin/python" \
  --index-url "$TORCH_INDEX" --extra-index-url https://pypi.org/simple \
  --index-strategy unsafe-best-match -r "$HERE/requirements.txt"

if [[ ! -d "$RUNTIME/Pi3/.git" ]]; then
  git clone --filter=blob:none --no-checkout https://github.com/yyfz/Pi3.git "$RUNTIME/Pi3"
fi
git -c safe.directory="$RUNTIME/Pi3" -C "$RUNTIME/Pi3" checkout --quiet --detach "$PI3_REVISION"

if [[ "$("$RUNTIME/bin/tailscale" version 2>/dev/null | head -1)" != "$TAILSCALE_VERSION" ]]; then
  archive="tailscale_${TAILSCALE_VERSION}_amd64.tgz" work="$(mktemp -d)"
  curl -fsSL -o "$work/$archive" "https://pkgs.tailscale.com/stable/$archive"
  echo "$(curl -fsSL "https://pkgs.tailscale.com/stable/$archive.sha256")  $work/$archive" | sha256sum -c --quiet
  tar -xzf "$work/$archive" -C "$work"
  install -m 755 "$work/${archive%.tgz}/tailscale" "$work/${archive%.tgz}/tailscaled" "$RUNTIME/bin/"
  rm -rf "$work"
fi

HF_HOME="$RUNTIME/hf-cache" "$RUNTIME/venv/bin/python" - "$WEIGHTS_REVISION" <<'PY'
import sys
from huggingface_hub import hf_hub_download
print(hf_hub_download("yyfz233/Pi3X", "model.safetensors", revision=sys.argv[1]))
PY

"$RUNTIME/venv/bin/python" -c 'import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0))'
echo "Pi3X runtime ready: $RUNTIME"
