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
  - stable-diffusion-v1-5/stable-diffusion-v1-5
  - lllyasviel/control_v11f1p_sd15_depth
  - CompVis/stable-diffusion-safety-checker
---

# Pi3X Mesh Studio

Independent noncommercial educational prototype. The original `leekh951/pi3x-vibe`
Space is neither updated nor called by this backend.

Use the separate **Gradio / ZeroGPU** Space `leekh951/pi3x-mesh`.
Register a read token as this Space's `HF_TOKEN` Secret for model downloads.
Upload every file in this folder, including `packages.txt`. Dependencies install only
in the Space; no local model or package installation is needed. FLUX is no longer
loaded or used; its previous access approval is not needed by this backend.
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
  "world_coordinate_system": "OpenCV",
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
`coordinate_system` describes optical camera axes. `world_coordinate_system`
describes the PLY world axes: `OpenCV` for raw Pi3X files, or `Y_UP` for files saved
by the page's orientation controls. Both cameras and PLY must use the same world
frame. Recovered poses are aligned to the actual uploaded PLY, including saved
orientation. The GLB converts raw OpenCV worlds once and leaves Y_UP worlds intact.

API: `/prepare_scene(ply, images, poses, quality)` → original GLB, scene ID,
cameras JSON, metadata, posed-images ZIP. `/restyle_scene(scene_id, prompt, seed)`
→ styled GLB, texture PNG, metadata. Reuse the same Gradio Client/session for both.
Scenes expire after six hours or container restart. `/capabilities` is CPU-only.

## Whole indoor scene texturing

The unit of work is the **entire reconstructed room**, including visible walls,
floor and furniture in one fixed mesh. No object extraction or turntable cameras
are used. Pi3X remains the reconstruction engine; this does not switch to VGGT.

1. Ball pivoting reconstructs observed surfaces on CPU (up to 30,000 triangles).
2. xatlas creates one non-overlapping UV atlas for the whole room (1024 square).
3. A CPU triangle z-buffer renders mesh depth and UV coordinates from the actual
   interior camera poses. Photo colors are visibility-tested and baked into UVs.
4. For each camera, depth-conditioned diffusion inpaints the unstyled visible
   surfaces. Previously styled surfaces are rendered from the SAME texture and
   masked out. The result is projected back into UVs using mesh depth; already
   painted texels cannot be overwritten. Each camera is a separate ZeroGPU task.
5. The GLB embeds the resulting PNG. Original/styled mesh positions, topology and
   UVs remain byte-identical. Unseen surfaces keep their original colors.

This is a custom **mesh-conditioned, multi-view indoor-scene texturing prototype**,
not the official SceneTex, TEXTure or Paint3D pipeline. It uses Stable Diffusion 1.5
and ControlNet depth inside a geometry-aware renderer/baker. It does not edit a
photo contact sheet or feed disconnected UV islands into an object-trained model.
Diffusion still operates on rendered images; 3D visibility and a shared texture
provide the scene constraint. Geometry conditioning and locked texels do NOT
prove semantic/style consistency across all viewpoints.

Each visible camera view uses 20 denoising steps and requests 45 seconds from
ZeroGPU. These are task parameters, not measured latency or total-budget promises.
A room with 3 photos can require 3 texture tasks, plus pose recovery if no camera
JSON is supplied. Repeating the same prompt/seed resumes completed camera views
within the same session instead of spending GPU time on them again. Completed
styles are reused. Cache and partial styles expire after six hours/container restart.

### CPU preparation performance

The `cpu-v2` fast path caps meshing input at 30,000 points and output at 20,000
triangles (previously 100,000 / 30,000). This reduces fine surface detail; choose
`detail` to retain the original 100,000 / 30,000 budgets. Both use a 1024 UV
texture. UV charts are packed into a single atlas with block-aligned placement.
Fast uses one chart-generation iteration; detail retains two.
Large projected triangles use NumPy array rasterization; tiny triangles
use a scalar path without generator/list conversion overhead. Camera poses orient
observed surface normals directly, avoiding whole-cloud tangent-graph propagation.
The CPU OpenMP/BLAS thread defaults are limited to 2 unless configured by the operator.

Prepared results are reused only for identical file contents/names/order, quality,
and poses in the same Gradio session. They are never shared across visitors. Server
mesh arrays are stored without CPU compression; JPEG/PNG inputs are stored in the
download ZIP without redundant compression. Temporary photo PNGs use a low
compression level. Stage timings are logged and the CPU stages appear in progress.

`/cpu_benchmark` runs bounded synthetic comparisons of the old/new pixel rasterizer
and the old/new normal-orientation meshing paths on the Space's CPU. It never calls
Pi3X or texture inference or acquires ZeroGPU. Its timings exclude GPU queueing,
pose inference, uploads and full real-scene UV preparation; a microbenchmark
speedup must not be presented as an end-to-end scene speedup. `/cpu_check` still
checks visibility, locked surface colors and deployed UV generation. The existing
Pi3X Space is unchanged, so absent camera poses still require separate recovery.

Prompts should describe the **whole interior**, e.g. `A cozy living room with oak
wood, beige linen, warm neutral walls`. English is recommended by these model
cards. Region selection and named-object editing are not implemented. A prompt
listing different materials cannot guarantee correct wall/furniture assignment.

Output is a **base-color texture**, not physically separated albedo/lighting or full
PBR materials. Roughness, metalness, normal maps and relighting are not generated.
No windows or furniture geometry are added. Holes and unobserved surfaces remain;
UV seams, painted silhouettes and style differences may occur. Reconstructed
room meshes are not guaranteed to be watertight.

## Candidate methods considered

- [SceneTex](https://github.com/daveredrum/SceneTex): explicitly supports indoor
  scenes, including composed reconstructed scene meshes. Official setup needs
  at least 48 GB GPU RAM, PyTorch3D and tiny-cuda-nn, plus iterative optimization.
  Its full optimization is not represented as a tested short ZeroGPU call here.
- [TEXTure](https://github.com/TEXTurePaper/TEXTurePaper): mesh + text, shared texture
  via multi-view painting; its object-centered viewpoints need interior-camera
  adaptation for rooms. The HSID link is a fork, not the upstream repository.
- [Paint3D](https://github.com/OpenTexture/Paint3D): text/image-conditioned UV
  texturing. UV-only object-model inference is not used as proof of room support.
- [TRELLIS.2 texturing](https://github.com/microsoft/TRELLIS.2/blob/main/example_texturing.py):
  existing mesh + reference image -> PBR GLB. It is not a direct text-prompt interface;
  its object/asset demos do not establish full indoor-room performance. CUDA build
  dependencies and different material channels need a separate adapter.
- TSDF fusion is a future meshing option when calibrated depth maps are supplied.
  The current input contract has PLY, RGB images and cameras, not saved depth maps.

Pi3X weights: CC BY-NC 4.0. SD 1.5 and ControlNet: CreativeML OpenRAIL-M (see their
model cards). xatlas: MIT. This combined demo stays noncommercial for Pi3X.
Model safety checking stays enabled on inputs and generated views. No paid API is
called, and neither PyTorch3D, gsplat nor a custom CUDA rasterizer is compiled.

Local validation covers camera contracts, raster math, and GLB geometry/embedded
textures without installing dependencies or invoking a GPU. Deployed CPU checks
cover native xatlas generation, UV boundary handling, depth visibility and surface
color locks. A bounded 9,216-point synthetic room comparison measured meshing at
0.313 s before and 0.144 s after (same 16,797 faces), on that worker. This is not a
whole real-scene latency estimate. Visual texture quality and ZeroGPU inference
latency remain untested during this performance change; no GPU inference was run.
