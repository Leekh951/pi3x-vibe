"""Register a running Colab or Hugging Face GPU server without local installs."""
import argparse
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def normalize_endpoint(value):
    url = urlsplit(value.strip())
    if (url.scheme != "https" or not re.fullmatch(r"[a-z0-9-]+\.(?:gradio\.live|hf\.space)", url.hostname or "", re.I)
            or url.username or url.password or url.port):
        raise ValueError("https://…gradio.live 또는 https://…hf.space 서버 주소를 입력하세요.")
    return f"https://{url.hostname}"


def set_backend(value):
    endpoint = normalize_endpoint(value)
    def read(path):
        request = urllib.request.Request(endpoint + path, headers={"User-Agent": "SPACE-setup"})
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response)
    config = read("/config")
    info = read((config.get("api_prefix") or "/gradio_api") + "/info")
    if "/reconstruct" not in info.get("named_endpoints", {}):
        raise ValueError("Pi3X SPACE 재구성 API가 없는 서버입니다.")
    path = ROOT / "space.config.json"
    site = json.loads(path.read_text(encoding="utf-8"))
    site["colabEndpoint"] = endpoint
    path.write_text(json.dumps(site, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("실행 중인 Pi3X 서버 확인 및 등록 완료:", endpoint)
    print("space.config.json을 커밋하고 푸시하면 모든 방문자가 자동으로 연결됩니다.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("endpoint", help="GPU 서버의 gradio.live 또는 hf.space 주소")
    args = parser.parse_args()
    set_backend(args.endpoint)
