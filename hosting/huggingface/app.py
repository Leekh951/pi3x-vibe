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


@spaces.GPU(duration=120)
def reconstruct(images, quality, progress=gr.Progress()):
    return backend.reconstruct(images, quality, progress)


demo = backend.build_demo(reconstruct)
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False,
                show_error=True, max_file_size="15mb")
