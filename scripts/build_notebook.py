"""Generate a self-contained Colab notebook using only Python's standard library."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "space.config.json").read_text())
viewer_url = config.get("viewerUrl", "").strip()
repository_name = config.get("githubRepository", "").strip()
if not viewer_url and repository_name:
    owner, repository = repository_name.split("/")
    viewer_url = f"https://{owner}.github.io/"
    if repository.lower() != f"{owner}.github.io".lower():
        viewer_url += repository + "/"
viewer_url = viewer_url or "http://localhost:8000/"


def cell(kind, source):
    result = {"cell_type": kind, "metadata": {}, "source": source.splitlines(keepends=True)}
    if kind == "code":
        result.update(execution_count=None, outputs=[])
    return result


setup = '''# 이 셀은 Colab에서만 실행하세요. 로컬에는 설치하지 않습니다.
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

if not Path("/content").exists():
    raise RuntimeError("Google Colab에서 실행해주세요.")
import torch
if not torch.cuda.is_available():
    raise RuntimeError("런타임 → 런타임 유형 변경 → T4 GPU를 선택한 뒤 다시 실행하세요.")
print("GPU:", torch.cuda.get_device_name(0))
print("기존 PyTorch 사용:", torch.__version__)

# torch / torchvision / CUDA / numpy를 재설치하거나 다운그레이드하지 않습니다.
# Pi3X의 image-only 추론에는 아래 패키지만 추가로 필요합니다.
packages = ["gradio==5.49.1", "huggingface_hub==0.35.3", "safetensors==0.6.2"]
subprocess.run([sys.executable, "-m", "pip", "install", "-q", *packages], check=True)
for module in ("numpy", "PIL"):
    if importlib.util.find_spec(module) is None:
        raise RuntimeError(f"Colab 기본 패키지 {module}가 없습니다. 새 GPU 런타임에서 다시 실행하세요.")

# 공식 소스 버전을 고정해 이후 upstream 변경의 영향을 줄입니다.
SOURCE_REVISION = "9fa3ddb3f8d53041f8b2738df404f62223bbaa7b"
repository = Path("/content/Pi3_SPACE_source")
if not (repository / ".git").exists():
    subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", "https://github.com/yyfz/Pi3.git", str(repository)], check=True)
subprocess.run(["git", "-C", str(repository), "checkout", "--detach", SOURCE_REVISION], check=True)
if str(repository) not in sys.path:
    sys.path.insert(0, str(repository))
os.environ["XFORMERS_DISABLED"] = "1"
print("준비 완료! GPU 서버를 시작합니다. 셀이 나뉘어 있으면 다음 셀을 실행하세요.")
'''

backend = (ROOT / "colab/backend.py").read_text()
# The final cell launches once explicitly; repeat execution closes the old server.
backend = backend.replace('if __name__ == "__main__":\n    launch()\n', '')
backend += '''
# 실행 후 돌아갈 SPACE 주소. GitHub Pages를 쓰면 배포한 웹 주소를 넣으세요.
VIEWER_URL = __SPACE_VIEWER_URL__ # @param {type:"string"}

# 셀을 다시 실행하면 이전 Gradio 서버를 닫습니다.
gr.close_all()
space_demo = launch(VIEWER_URL)
'''
backend = backend.replace("__SPACE_VIEWER_URL__", json.dumps(viewer_url, ensure_ascii=False))
notebook = {
    "nbformat": 4, "nbformat_minor": 5,
    "metadata": {"colab": {"name": "Pi3X_SPACE.ipynb", "provenance": []},
                 "accelerator": "GPU", "kernelspec": {"display_name": "Python 3", "name": "python3"},
                 "language_info": {"name": "python", "version": "3"}},
    "cells": [
        cell("markdown", "# π³ SPACE · 사진에서 3D 공간으로\n\n"
             "이 노트북이 GPU 백엔드입니다. **런타임 → 런타임 유형 변경 → T4 GPU**를 선택하고 **런타임 → 모두 실행**하세요.\n\n"
             "**운영자가 실행하는 GPU 서버용 노트북**입니다. 방문자는 웹에서 사진만 올리면 됩니다.\n\n"
             "실행 결과의 `https://….gradio.live` 주소를 사이트 `space.config.json`의 **colabEndpoint**에 등록하고 푸시하세요. "
             "로컬에서는 `python3 scripts/set_backend.py https://….gradio.live`로 실행 중인 API를 확인하고 설정할 수 있습니다. "
             "출력의 **SPACE 웹 화면 연결** 링크는 현재 서버를 테스트할 때 사용합니다. "
             "사진 2–8장을 올리면 자동으로 처리하고 3D 점 구름을 표시합니다.\n\n"
             "- 첫 실행에는 약 5.4 GB의 모델 다운로드가 필요합니다. 시간은 네트워크·GPU에 따라 달라집니다.\n"
             "- 처음에는 사진 **3–4장 + 가볍게** 설정으로 시작하세요.\n"
             "- Colab 탭과 런타임을 유지하세요. 런타임이 종료되면 새 주소로 다시 연결합니다.\n"
             "- 사진과 결과는 이 Colab에 저장됩니다. 작업 후 **연결 해제 및 런타임 삭제**로 정리할 수 있습니다.\n"
             "- 공개 주소를 아는 사람은 API를 사용할 수 있습니다.\n"
             "- 결과는 색이 있는 점 구름입니다. **Pi3X 가중치는 비상업 연구·교육용**입니다.\n\n"
             "[공식 Pi3X 코드](https://github.com/yyfz/Pi3) · [모델](https://huggingface.co/yyfz233/Pi3X)\n"),
        cell("markdown", "## 1. GPU 확인과 준비\n필요한 패키지만 Colab에 설치합니다. 기존 PyTorch와 CUDA를 유지합니다.\n"),
        cell("code", setup),
        cell("markdown", "## 2. GPU 서버 시작\nGitHub Pages에서는 배포된 웹 주소를 사용하세요. "
             "로컬 미리보기에서는 VS Code에서 먼저 `python3 start.py`를 실행하세요. "
             "셀의 `VIEWER_URL` 값을 실제 브라우저에서 사용하는 주소로 확인해주세요. "
             "이 셀을 실행한 뒤 공개 주소를 사이트 설정에 등록하면 모든 방문자가 자동 연결됩니다. "
             "**SPACE 웹 화면 연결** 링크는 현재 실행을 미리 확인하는 용도입니다. "
             "웹 연결이 어려우면 이 셀의 Gradio 화면에서도 사진을 올려 PLY를 만들 수 있습니다. "
             "받은 PLY를 SPACE의 폴더 버튼으로 불러오세요.\n"),
        cell("code", backend),
    ]
}
for i, item in enumerate(notebook["cells"]):
    item["id"] = f"space-{i:02d}"
destination = ROOT / "colab/Pi3X_SPACE.ipynb"
destination.write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + "\n")
print(destination)
