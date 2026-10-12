---
title: Pi3X Mesh Studio
emoji: 🪵
colorFrom: green
colorTo: gray
sdk: gradio
sdk_version: 5.49.1
python_version: 3.10.13
app_file: app.py
pinned: false
models:
  - yyfz233/Pi3X
  - black-forest-labs/FLUX.2-klein-9B
  - CompVis/stable-diffusion-safety-checker
---

# Pi3X Mesh Studio

Independent noncommercial educational prototype. The original `leekh951/pi3x-vibe`
Space is neither updated nor called by this backend.

Create a **Gradio / ZeroGPU** Space named `leekh951/pi3x-mesh`, agree to the
[FLUX.2-klein-9B conditions](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B),
and register a read token for the approved account as this Space's `HF_TOKEN` Secret.
Upload every file in this folder, including `packages.txt`. Dependencies install only
in the Space; no local model or package installation is needed.

Input: colored Pi3X PLY, the original 2–8 images, and optionally camera JSON.
The original Pi3X API does not export poses. If poses are omitted this Space runs
Pi3X again and aligns the recovered cameras to the supplied PLY using ICP.
Alignment can fail for unrelated photos, extensive cropping or strongly altered PLYs.
Use the original raw PLY when possible. Uploaded cameras are used without a second
Pi3X inference. Input names must exactly match camera frame names.

Camera contract (`image_size` is the resolution at which K is expressed):

```json
{
  "coordinate_system": "OpenCV",
  "pose_convention": "camera_to_world",
  "frames": [{
    "image": "living-room-01.jpg",
    "image_size": [960, 540],
    "intrinsics": [[800,0,480],[0,800,270],[0,0,1]],
    "camera_to_world": [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
  }]
}
```

The example matrix is illustrative, not an estimate for the example photos.

API: `/prepare_scene(ply, images, poses, quality)` → original GLB, scene ID,
cameras JSON, metadata, posed-images ZIP. `/restyle_scene(scene_id, prompt, seed)`
→ styled GLB, texture PNG, metadata. Reuse the same Gradio Client/session for both.
Scenes expire after six hours or container restart. `/capabilities` is CPU-only.

Ball pivoting builds the mesh on CPU. Visible triangle corners are projected through
their actual cameras into a shared atlas, with a point-cloud z-buffer for occlusion.
FLUX edits the atlas jointly in one four-step call. Mesh vertices, topology and UVs
remain exactly fixed for every style. GLB embeds its PNG; textures are not just vertex
colors. Areas outside photographed views retain the PLY colors. Geometry hashes are
included for comparison. An input/output image checker runs with the editing model.

Limitations: the image model does not enforce 3D consistency, so texture seams and
misaligned painted edges can occur. Holes in the input remain holes; this prototype
does not invent an unseen, watertight room or change furniture/layout. Small atlas
tiles prioritize GPU budget over texture resolution. Inference speed, memory use,
and ZeroGPU runtime compatibility still require an actual deployment test.

Pi3X weights: CC BY-NC 4.0. FLUX weights: FLUX Non-Commercial License. Review model
conditions before deployment. CPU package compilation is avoided; neither SAM,
PyTorch3D, gsplat nor a custom CUDA rasterizer is required.
