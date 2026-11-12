"""Prepare the static Pages artifact with Python's standard library only."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE_FILES = (
    "index.html", "styles.css", "landing.css", "landing.js", "landing-cloud.bin", "app.js", "gpu-backend.mjs", "gpu-job.mjs", "gpu-failover.mjs", "gpu-upload.mjs", "viewer.js", "orientation.mjs", "demo.js",
    ".nojekyll", "colab/Pi3X_SPACE.ipynb",
    # Mesh Studio (mesh-studio.js, mesh-viewer.js, mesh-progress.mjs) is kept in the repo but not published.
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
    shutil.copytree(ROOT / "examples", output / "examples", dirs_exist_ok=True)
    (output / "space.config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    version_assets(output)
    print(f"Pages 파일 준비 완료: {output}")
    return config


# GitHub Pages serves every file with max-age=600. Without versioned URLs a visitor can
# run a cached app.js against a newer examples/images.json (or vice versa) for ten minutes
# after a deploy. One content hash per build makes each page load a consistent set.
JS_REFERENCE = re.compile(r"""((?:from\s*|import\s*\(\s*|new URL\s*\(\s*)(['"]))(\./(?!vendor/)[^'"?]+\.(?:js|mjs|json|bin))(\2)""")
HTML_REFERENCE = re.compile(r'((?:src|href)=")([A-Za-z0-9_.-]+\.(?:js|css))(")')


def version_assets(output):
    digest = hashlib.sha256()
    for path in sorted(output.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(output).as_posix().encode() + b"\0" + path.read_bytes())
    version = digest.hexdigest()[:10]
    for path in output.glob("*"):
        if path.suffix in (".js", ".mjs"):
            path.write_text(JS_REFERENCE.sub(rf"\1\3?v={version}\4", path.read_text(encoding="utf-8")), encoding="utf-8")
        elif path.suffix == ".html":
            path.write_text(HTML_REFERENCE.sub(rf"\1\2?v={version}\3", path.read_text(encoding="utf-8")), encoding="utf-8")
    return version


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
