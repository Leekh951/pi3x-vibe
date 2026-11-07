"""Home-GPU entry point: serves the same /reconstruct API as the Hugging Face Space.

Run through start.sh. Binds to localhost only; the HTTPS tunnel is the sole public path.
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ.get("PI3X_RUNTIME", "/root/workspace/pi3x-runtime"))

# These must be set before gradio, huggingface_hub and backend are imported.
os.environ.setdefault("HF_HOME", str(RUNTIME / "hf-cache"))
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
sys.path[:0] = [str(RUNTIME / "Pi3"), str(REPO / "colab")]

import backend  # noqa: E402

# Visitor photos and results land on this machine's disk: sweep hourly, keep six hours.
CACHE_SWEEP = (3600, 6 * 3600)


def main():
    backend.load_model()
    demo = backend.build_demo()
    demo.delete_cache = CACHE_SWEEP
    demo.launch(server_name="127.0.0.1", server_port=int(os.environ.get("PI3X_PORT", "7860")),
                share=False, show_error=True, max_file_size="15mb", ssr_mode=False)


if __name__ == "__main__":
    main()
