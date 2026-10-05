"""Export a self-contained Hugging Face upload folder and ZIP; no installs/network."""
import argparse
import ast
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "hosting/huggingface"


def build_space(output):
    output = Path(output).resolve()
    # Limit generated files to a disposable build folder, outside source files.
    if output == ROOT or ROOT.is_relative_to(output) or (output.is_relative_to(ROOT)
            and not output.is_relative_to(ROOT / "dist")):
        raise ValueError("저장소 안에서는 dist/ 아래에 배포 폴더를 지정하세요.")
    sources = {name: TEMPLATE / name for name in ("app.py", "README.md", "requirements.txt")}
    sources["backend.py"] = ROOT / "colab/backend.py"
    for name, source in sources.items():
        content = source.read_text(encoding="utf-8")
        if name.endswith(".py"):
            ast.parse(content, filename=name)
    output.mkdir(parents=True, exist_ok=True)
    for name, source in sources.items():
        shutil.copyfile(source, output / name)
    archive = output.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in sources:
            bundle.write(output / name, arcname=name)
    return output, archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/huggingface")
    folder, archive = build_space(parser.parse_args().output)
    print("Hugging Face 업로드 파일:", folder)
    print("ZIP:", archive)
