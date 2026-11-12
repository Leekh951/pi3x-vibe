"""Space entry point. Dependencies and model download run on Hugging Face only."""
# Import first to activate ZeroGPU's CUDA emulation before torch is imported.
import spaces

import os
import subprocess
import sys
from pathlib import Path

SOURCE_REVISION = "9fa3ddb3f8d53041f8b2738df404f62223bbaa7b"
os.environ["XFORMERS_DISABLED"] = "1"
source = Path("/tmp/Pi3_SPACE_source")
if not (source / ".git").exists():
    subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout",
                    "https://github.com/yyfz/Pi3.git", str(source)], check=True)
subprocess.run(["git", "-C", str(source), "checkout", "--detach", SOURCE_REVISION], check=True)
sys.path.insert(0, str(source))

# backend.py is copied alongside this entry point by scripts/build_space.py.
import gradio as gr
import backend

# Initialize at startup, outside the GPU-decorated request. ZeroGPU emulates CUDA
# here and restores the model on the real GPU when a request is scheduled.
backend.load_model()


def gpu_duration(images, quality, progress=None):
    # Ten detail photos take about 2-3 s of inference. ZeroGPU refuses a job whose
    # requested duration exceeds the visitor's remaining quota, so ask for a short
    # window (model transfer included) to fit more jobs into each visitor's budget.
    count = min(10, max(2, len(images or [])))
    return 20 + count * 2 if quality == "fast" else 25 + count * 3


@spaces.GPU(duration=gpu_duration)
def reconstruct(images, quality, progress=gr.Progress()):
    return backend.reconstruct(images, quality, progress)


# A full queue sends the visitor's page to the operator's GPU instead of waiting.
demo = backend.build_demo(reconstruct, queue_size=8)
# Uploaded photos and results: checked hourly, removed after 6 hours (same as the home server).
demo.delete_cache = (3600, 6 * 3600)
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False,
                show_error=True, max_file_size="15mb", ssr_mode=False)
