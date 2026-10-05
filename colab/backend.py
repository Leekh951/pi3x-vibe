"""Pi3X SPACE GPU backend. Run in Google Colab, never on the local viewer server.

Model source: https://github.com/yyfz/Pi3
Weights: https://huggingface.co/yyfz233/Pi3X (CC BY-NC 4.0).
"""
import gc
import math
import os
import shutil
import tempfile
import time
from html import escape
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Force the repository's PyTorch attention fallback; no compiled extension installs.
os.environ["XFORMERS_DISABLED"] = "1"

import gradio as gr
import numpy as np
import torch
from huggingface_hub import hf_hub_download
from PIL import Image, ImageOps, UnidentifiedImageError
from safetensors import safe_open

from pi3.models.pi3x import Pi3X
from pi3.utils.geometry import depth_normal_edge

WEIGHTS_REVISION = "bb1deea4d7423de5b30691739cb451a3f57dc1d5"
PIXEL_LIMITS = {"fast": 90000, "detail": 230000}
OUTPUT_ROOT = Path("/content/SPACE_results")
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
MODEL = None


def load_model(progress):
    global MODEL
    if MODEL is not None:
        return MODEL
    progress(.10, desc="Pi3X 모델을 내려받고 있어요. 첫 실행은 몇 분 걸릴 수 있어요.")
    checkpoint = hf_hub_download(
        repo_id="yyfz233/Pi3X", filename="model.safetensors", revision=WEIGHTS_REVISION
    )
    # DINOv2 reads scalar initialization values (linspace(...).item()), so its
    # constructor must run on CPU. A global meta device breaks that constructor.
    # Safetensors maps the checkpoint; assign=True replaces the random parameters
    # instead of copying checkpoint tensors into a second parameter allocation.
    with torch.device("cpu"):
        candidate = Pi3X(use_multimodal=False).eval()
    expected = set(candidate.state_dict())
    with safe_open(checkpoint, framework="pt", device="cpu") as handle:
        available = set(handle.keys())
        missing = expected - available
        if missing:
            raise RuntimeError("Pi3X checkpoint is missing model tensors: " + str(sorted(missing)[:5]))
        tensors = {key: handle.get_tensor(key) for key in expected}
    candidate.load_state_dict(tensors, strict=True, assign=True)
    del tensors
    progress(.22, desc="모델을 GPU에 준비하고 있어요.")
    candidate = candidate.to("cuda").eval()
    MODEL = candidate
    gc.collect()
    return MODEL


def load_photos(paths, pixel_limit):
    photos = []
    for path in paths:
        path = Path(path)
        if path.stat().st_size > 15 * 1024 * 1024:
            raise gr.Error("사진은 장당 15 MB 이하로 선택해주세요.")
        try:
            with Image.open(path) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise gr.Error("JPG, PNG, WEBP 사진만 지원합니다.")
                if min(source.size) < 28 or max(source.size) / min(source.size) > 6:
                    raise gr.Error("너무 작거나 긴 사진입니다. 일반적인 가로·세로 사진을 사용해주세요.")
                photos.append(ImageOps.exif_transpose(source).convert("RGB"))
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise gr.Error("읽을 수 없는 사진입니다. 파일을 확인해주세요.") from None
    width, height = photos[0].size
    scale = math.sqrt(pixel_limit / (width * height))
    cols, rows = max(1, round(width * scale / 14)), max(1, round(height * scale / 14))
    while cols * rows * 196 > pixel_limit:
        if cols / rows > width / height and cols > 1:
            cols -= 1
        elif rows > 1:
            rows -= 1
        else:
            cols -= 1
    target = (cols * 14, rows * 14)
    rgb = np.stack([np.asarray(photo.resize(target, Image.Resampling.LANCZOS), dtype=np.uint8) for photo in photos])
    tensor = torch.from_numpy(rgb.copy()).permute(0, 3, 1, 2).float().div_(255).unsqueeze(0).to("cuda")
    return tensor, rgb, target


def save_cloud(path, points, colors, confidence):
    """Packed binary PLY with an extra confidence property for browser filtering."""
    count = len(points)
    records = np.empty(count, dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                                  ("red", "u1"), ("green", "u1"), ("blue", "u1"),
                                  ("confidence", "<f4")])
    for i, key in enumerate(("x", "y", "z")):
        records[key] = points[:, i]
    for i, key in enumerate(("red", "green", "blue")):
        records[key] = colors[:, i]
    records["confidence"] = confidence
    header = ("ply\nformat binary_little_endian 1.0\n"
              "comment Pi3X SPACE; OpenCV camera-to-world coordinates\n"
              f"element vertex {count}\nproperty float x\nproperty float y\nproperty float z\n"
              "property uchar red\nproperty uchar green\nproperty uchar blue\n"
              "property float confidence\nend_header\n")
    with open(path, "wb") as stream:
        stream.write(header.encode("ascii"))
        records.tofile(stream)


def clean_old_results():
    # Keep results long enough for viewing/downloading, without unbounded disk growth.
    for directory in OUTPUT_ROOT.glob("scene_*"):
        if directory.is_dir() and directory.stat().st_mtime < time.time() - 6 * 3600:
            shutil.rmtree(directory, ignore_errors=True)


def reconstruct(images, quality, progress=gr.Progress()):
    if not torch.cuda.is_available():
        raise gr.Error("Colab에서 런타임 → 런타임 유형 변경 → T4 GPU를 선택해주세요.")
    if not images or not 2 <= len(images) <= 8:
        raise gr.Error("같은 공간의 사진 2–8장을 선택해주세요.")
    if quality not in PIXEL_LIMITS:
        raise gr.Error("지원하지 않는 품질 설정입니다.")
    started = time.monotonic()
    tensor = result = masks = model = None
    try:
        clean_old_results()
        model = load_model(progress)
        progress(.30, desc="사진의 크기와 방향을 맞추고 있어요.")
        tensor, rgb, target = load_photos(images, PIXEL_LIMITS[quality])
        progress(.42, desc="Pi3X가 사진을 연결해 3D 공간을 재구성하고 있어요.")
        dtype = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
        with torch.inference_mode(), torch.amp.autocast("cuda", dtype=dtype):
            result = model(imgs=tensor)
        progress(.82, desc="경계의 노이즈를 정리하고 점 구름을 만들고 있어요.")
        scores = torch.sigmoid(result["conf"][..., 0]).float()
        # Preserve low confidence values so the user can adjust filtering live.
        masks = (scores >= .01) & torch.isfinite(result["points"]).all(dim=-1)
        masks &= ~depth_normal_edge(result["local_points"], rtol=.03, mask=masks)
        selection = masks[0].cpu().numpy()
        points = result["points"][0].float().cpu().numpy()[selection]
        confidence = scores[0].cpu().numpy()[selection]
        colors = rgb[selection]
        if not len(points):
            raise gr.Error("유효한 점이 없어요. 겹치는 영역이 더 많은 선명한 사진으로 시도해주세요.")
        if len(points) > 600000:
            indices = np.random.default_rng(0).choice(len(points), 600000, replace=False)
            points, colors, confidence = points[indices], colors[indices], confidence[indices]
        directory = Path(tempfile.mkdtemp(prefix="scene_", dir=OUTPUT_ROOT))
        output = directory / "SPACE_reconstruction.ply"
        save_cloud(output, points, colors, confidence)
        metadata = {"engine": "Pi3X", "image_count": len(images), "point_count": len(points),
                    "resolution": list(target), "quality": quality,
                    "elapsed_seconds": round(time.monotonic() - started, 1),
                    "coordinate_system": "OpenCV", "weights_revision": WEIGHTS_REVISION}
        progress(1, desc="완성! 브라우저로 공간을 보내고 있어요.")
        return str(output), metadata
    except torch.cuda.OutOfMemoryError:
        raise gr.Error("GPU 메모리가 부족해요. ‘가볍게’로 바꾸거나 사진을 2–4장으로 줄여주세요.") from None
    finally:
        tensor = result = masks = None
        gc.collect()
        torch.cuda.empty_cache()


def viewer_connection_url(viewer_url, public_url):
    """Return a click-to-connect browser URL without persisting any credentials."""
    parts = urlsplit(viewer_url)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
        raise ValueError("웹 화면 주소에는 http:// 또는 https:// 주소를 입력해주세요.")
    query = [(key, value) for key, value in parse_qsl(parts.query) if key != "colab"]
    query.append(("colab", public_url))
    return urlunsplit(parts._replace(query=urlencode(query)))


def launch(viewer_url="http://localhost:8000/"):
    if not torch.cuda.is_available():
        raise RuntimeError("GPU가 연결되지 않았습니다. 런타임 유형을 T4 GPU로 변경하고 다시 실행하세요.")
    with gr.Blocks(title="Pi3X SPACE · Colab GPU") as demo:
        gr.Markdown("# π³ SPACE · 운영자 GPU 서버\n이 탭을 유지하고 공개 주소를 사이트 설정의 colabEndpoint에 등록하세요. 방문자는 사진만 올리면 됩니다.\n"
                    "사진은 이 Colab 런타임에서 처리됩니다. 모델 가중치는 비상업 연구·교육용입니다.")
        images = gr.File(label="같은 공간의 사진 2–8장", file_count="multiple", type="filepath", file_types=["image"])
        quality = gr.Radio(choices=[("가볍게", "fast"), ("섬세하게", "detail")], value="fast", label="품질")
        run = gr.Button("3D 공간 만들기")
        output = gr.File(label="PLY 결과")
        metadata = gr.JSON(label="재구성 정보")
        run.click(reconstruct, inputs=[images, quality], outputs=[output, metadata],
                  api_name="reconstruct", concurrency_limit=1)
    demo.queue(max_size=4, default_concurrency_limit=1)
    _, _, public_url = demo.launch(share=True, debug=False, show_error=True, max_file_size="15mb")
    print("\n" + "=" * 50)
    print("SPACE 웹 화면에 붙여넣을 주소:", public_url)
    print("이 셀과 Colab 런타임을 실행 상태로 유지하세요.")
    print("=" * 50)
    if public_url:
        try:
            connection_url = viewer_connection_url(viewer_url, public_url)
            from IPython.display import HTML, display
            display(HTML(
                '<a target="_blank" rel="noopener" href="' + escape(connection_url, quote=True)
                + '" style="display:inline-block;padding:14px 22px;border-radius:8px;'
                + 'background:#baff6c;color:#1d3412;text-decoration:none;font-weight:700">'
                + 'SPACE 웹 화면 연결</a>'
                + '<p>이 링크를 누르면 SPACE 웹 화면이 열리고 Colab GPU에 연결됩니다.</p>'
            ))
        except (ValueError, ImportError) as error:
            print("웹 자동 연결 링크를 만들지 못했습니다:", error)
            print("위 gradio.live 주소를 웹 화면의 Colab 연결 창에 붙여넣으세요.")
    return demo


if __name__ == "__main__":
    launch()
