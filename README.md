# π³ SPACE · pi3x-vibe

사진 2–8장을 올리면 준비된 Pi3X GPU 서버가 처리하고, 같은 페이지에서 3D 점 구름을 표시합니다. 방문자는 Colab, 노트북 코드, 연결 주소 입력을 보지 않습니다. 사진 업로드 후 자동으로 생성하며, 설정을 바꾸거나 재시도할 때는 **3D 공간 만들기**를 누릅니다.

웹 사이트: **https://leekh951.github.io/pi3x-vibe/**

## 방문자 사용법

1. 같은 공간을 다른 각도에서 찍은 JPG·PNG·WEBP 사진 2–8장을 선택하거나 놓습니다.
2. 업로드와 처리 진행 상황을 보며 기다립니다. 처음에는 사진 3–4장과 ‘가볍게’를 권장합니다.
3. 완성된 공간을 드래그·휠·우클릭으로 탐색합니다. 점 크기, 색 표현, 신뢰도를 조절하고 PLY로 저장할 수 있습니다.

첫 화면의 거실은 **합성 예제**입니다. 실제 사진 결과는 서버에서 반환한 PLY를 받은 뒤 표시합니다. 서버가 준비되지 않은 경우 그 상태를 안내하고 사진과 이전 결과를 유지합니다. 결과는 색이 있는 점 구름이며 정밀 치수 측정이나 메시 생성은 제공하지 않습니다.

## 운영자: GPU 서버 시작

GitHub Pages는 웹 화면을 제공하며 Python GPU 코드는 실행하지 않습니다. 운영자가 이 노트북을 실행해 서버를 유지하면 방문자는 사진만 올립니다.

1. **[Pi3X 운영자 노트북 열기](https://colab.research.google.com/github/Leekh951/pi3x-vibe/blob/main/colab/Pi3X_SPACE.ipynb)**
2. **런타임 → 런타임 유형 변경 → T4 GPU → 런타임 → 모두 실행**합니다.
3. 마지막 셀에서 나온 **https://…gradio.live** 주소를 등록합니다. 로컬 터미널에서 다음 명령은 실제 `/reconstruct` API를 확인하고 설정 파일에 저장합니다.

```bash
cd /home/lee/pi3x-vibe
python3 scripts/set_backend.py https://실제주소.gradio.live
```

4. `space.config.json` 변경을 커밋하고 푸시합니다. GitHub Pages가 새 주소로 자동 배포되고, 모든 방문자가 서버에 자동 연결합니다.

`space.config.json`의 `colabEndpoint`가 비어 있으면 아직 공개 서버가 등록되지 않은 상태입니다. Colab 재시작으로 주소가 바뀌면 새 주소를 등록하세요. 공개 주소를 아는 사람은 API를 사용할 수 있습니다. 사진은 생성 시 해당 Colab으로 전송되고 임시 파일이 런타임 디스크에 남을 수 있습니다. 작업 후 Colab의 **연결 해제 및 런타임 삭제**로 정리할 수 있습니다.

노트북의 **SPACE 웹 화면 연결**은 운영자가 현재 실행을 시험하는 링크입니다. 이 링크의 `?colab=…` 주소는 해당 방문에만 사용되며 공개 서버 설정을 바꾸지 않습니다. 누구나 기본 사이트 주소로 이용하게 하려면 `colabEndpoint`를 등록해야 합니다.

Colab 기본 PyTorch·NumPy·Pillow를 유지하고 Gradio·huggingface_hub·safetensors만 Colab에 설치합니다. 로컬에는 설치하지 않습니다. Pi3X 공식 소스와 가중치 버전은 고정되어 있습니다. torch/CUDA, xFormers, flash-attn 재설치는 없습니다. 첫 재구성 시 약 5.4 GB 모델을 다운로드하므로 시간이 걸립니다.

Colab 런타임과 공유 주소는 상시 운영을 보장하지 않습니다. 무료 Colab은 노트북을 우회해 웹 UI로 주로 사용하는 실행을 제한할 수 있습니다. [Colab 공식 안내](https://research.google.com/colaboratory/faq.html)

## 로컬 미리보기

```bash
cd /home/lee/pi3x-vibe
python3 start.py
```

**http://localhost:8000/** 을 엽니다. VS Code 작업 **SPACE: 웹 실행**도 사용할 수 있습니다. 원격 SSH·컨테이너에서는 VS Code **포트** 탭에서 8000을 전달합니다. `index.html` 더블클릭은 ES 모듈 제한으로 지원하지 않습니다. 예제, 사진 미리보기, PLY 입출력은 서버 연결 없이 사용할 수 있습니다.

## GitHub Pages 배포

대상 저장소는 **[Leekh951/pi3x-vibe](https://github.com/Leekh951/pi3x-vibe)**입니다. `main`에 푸시하면 `.github/workflows/pages.yml`이 검증 후 웹 파일을 배포합니다. GitHub **Settings → Pages → Source**는 **GitHub Actions**입니다.

배포 주소와 저장소 정보를 자동 적용하며 Python 표준 라이브러리로 파일을 준비합니다. npm·pip 설치 없이 GitHub 러너의 Python과 Node를 사용합니다. 노트북은 저장소에 유지되지만 사용자 화면에서 표시하거나 실행하도록 요구하지 않습니다. GPU 처리는 이미 실행 중인 서버의 `/reconstruct` API를 호출합니다.

## 검증

```bash
python3 scripts/test_pages.py
python3 scripts/build_pages.py
```

기존 Node가 있는 환경에서는 `node scripts/test_backend.mjs`로 자동 연결을 검증합니다. 로컬 Node가 없으면 설치하지 않아도 되며 GitHub Actions가 이 검증을 실행합니다. `dist/`는 Git에서 제외합니다.

배포 검증 3개와 자동 연결 검증 17개로 경로·필수 파일, 방문자 화면의 설정 제거, 서버 주소 갱신, 중복 연결 방지, 연결 실패·시간 초과·재시도를 확인합니다. 자동 연결 테스트는 모사 API이며 실제 모델 추론을 대신하지 않습니다.

이전 화면은 Chrome에서 WebGL·PLY 입출력·사진 검증을 확인했습니다. 새 자동 생성 화면의 실제 브라우저 조작과 **실제 Colab GPU의 모델 다운로드·추론은 아직 검증하지 않았습니다.** `scripts/test_browser.py`는 새 흐름에 맞춰 갱신했으며 실행 시 같은 폴더의 Chrome 테스트 도구를 사용합니다.

## 주요 파일

- `index.html`, `styles.css`, `app.js`: 사진 업로드, 자동 생성, 진행 상태와 결과 화면
- `gpu-backend.mjs`: 공개 서버 자동 연결, 재시도, 연결 상태
- `viewer.js`, `demo.js`: Three.js 점 구름 뷰어와 합성 거실
- `space.config.json`: 저장소·웹 주소·공개 GPU 서버 주소
- `colab/backend.py`, `colab/Pi3X_SPACE.ipynb`: 운영자가 실행하는 GPU 서버
- `scripts/set_backend.py`: 실행 중인 서버 확인·등록
- `scripts/build_notebook.py`: 백엔드 변경 후 노트북 재생성
- `scripts/build_pages.py`, `scripts/test_pages.py`, `scripts/test_backend.mjs`: 배포 파일 생성·검증
- `start.py`, `.vscode/tasks.json`: 설치 없는 로컬 웹 서버 실행
- `vendor/`: 고정된 브라우저 라이브러리와 라이선스

## 라이선스

- [Pi3 / Pi3X](https://github.com/yyfz/Pi3): BSD-3-Clause 코드, CC BY-NC 4.0 가중치. 교육·비상업 과제용입니다.
- [Pi3X 가중치](https://huggingface.co/yyfz233/Pi3X)
- Three.js 0.170.0: MIT, `vendor/THREE-LICENSE.txt`
- Gradio JavaScript client 1.17.0: Apache-2.0, `vendor/GRADIO-LICENSE.txt`
