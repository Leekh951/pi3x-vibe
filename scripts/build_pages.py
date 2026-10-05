"""Prepare the static Pages artifact with Python's standard library only."""
import argparse
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE_FILES = (
    "index.html", "styles.css", "app.js", "gpu-backend.mjs", "viewer.js", "demo.js",
    ".nojekyll", "colab/Pi3X_SPACE.ipynb",
)


def build(output, repository=None, viewer_url=None, ref=None):
    output = Path(output).resolve()
    if output == ROOT or output in ROOT.parents:
        raise ValueError("빌드 경로로 저장소 루트나 상위 폴더를 사용할 수 없습니다.")
    config = json.loads((ROOT / "space.config.json").read_text(encoding="utf-8"))
    if repository is not None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("저장소는 계정명/저장소명 형식이어야 합니다.")
        config["githubRepository"] = repository
    if viewer_url is not None:
        url = urlsplit(viewer_url)
        if url.scheme not in ("http", "https") or not url.netloc or url.username or url.password or url.query or url.fragment:
            raise ValueError("웹 주소는 쿼리나 계정 정보가 없는 http(s) 주소여야 합니다.")
        config["viewerUrl"] = viewer_url.rstrip("/") + "/"
    if ref is not None:
        if not ref.strip():
            raise ValueError("브랜치 이름이 비어 있습니다.")
        config["githubRef"] = ref

    # Keep backend source, local tooling, screenshots, and Git metadata out of Pages.
    for name in SITE_FILES:
        source = ROOT / name
        if not source.is_file():
            raise FileNotFoundError(f"배포 파일이 없습니다: {name}")
    output.mkdir(parents=True, exist_ok=True)
    for name in SITE_FILES:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    shutil.copytree(ROOT / "vendor", output / "vendor", dirs_exist_ok=True)
    (output / "space.config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Pages 파일 준비 완료: {output}")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--repository", help="GitHub 계정명/저장소명")
    parser.add_argument("--viewer-url", help="실제 GitHub Pages 또는 커스텀 도메인 주소")
    parser.add_argument("--ref", help="Colab에서 열 브랜치 이름")
    args = parser.parse_args()
    build(args.output, args.repository, args.viewer_url, args.ref)


if __name__ == "__main__":
    main()
