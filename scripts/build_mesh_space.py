"""Prepare the independent Mesh Space upload; standard library only."""
import ast
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(output=None):
    source = ROOT/'hosting/mesh-huggingface'
    output = Path(output or ROOT/'dist/mesh-huggingface').resolve()
    if not output.is_relative_to(ROOT/'dist'):
        raise ValueError('배포 폴더는 dist/ 아래로 지정해주세요.')
    files = sorted(p for p in source.iterdir() if p.is_file())
    for file in files:
        if file.suffix == '.py': ast.parse(file.read_text(),filename=file.name)
    output.mkdir(parents=True,exist_ok=True)
    for file in files: shutil.copy2(file,output/file.name)
    archive = output.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
        for file in files: bundle.write(output/file.name,file.name)
    print('새 Space 업로드 폴더:',output)
    print('새 Space ZIP:',archive)
    return output,archive


if __name__ == '__main__': build()
