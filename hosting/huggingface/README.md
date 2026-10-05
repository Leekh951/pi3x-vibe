---
title: Pi3X SPACE GPU
emoji: 🏠
colorFrom: green
colorTo: gray
sdk: gradio
sdk_version: 5.49.1
python_version: 3.10.13
app_file: app.py
startup_duration_timeout: 1h
models:
  - yyfz233/Pi3X
preload_from_hub:
  - yyfz233/Pi3X model.safetensors bb1deea4d7423de5b30691739cb451a3f57dc1d5
---

# Pi3X SPACE GPU

Backend for https://leekh951.github.io/pi3x-vibe/ . Photos → Pi3X → colored PLY.
The `/reconstruct` API accepts `images` (2–8 files) and `quality` (`fast` or
`detail`), and returns a PLY file plus JSON metadata.

Select **ZeroGPU** in the Space hardware settings. A dedicated paid GPU also
works with the same app; do not select paid hardware unless you accept its cost.
The README does not allocate GPU hardware by itself.

The app prepares the pinned model at startup and requests a GPU for each
inference through `spaces.GPU`. ZeroGPU has daily quotas and queueing; this does
not provide unlimited free compute. Inactive Spaces may sleep and take time to
start again. Their address remains stable across restarts.

Photos and results are temporarily stored on the Space server. Old generated
scene folders are cleaned when a request arrives after six hours. Gradio also
caches uploads/results; stop/restart the Space to clear its ephemeral disk.
The public API is accessible to anyone who knows its address.

Pi3X weights are CC BY-NC 4.0, for noncommercial research and education.
Source: https://github.com/yyfz/Pi3 (BSD-3-Clause). We use image-only inference
with the pinned source and weights revisions; no xFormers or flash-attn build.

Deployment package source: https://github.com/Leekh951/pi3x-vibe .
This package has not yet been validated with actual inference on a live Space.
