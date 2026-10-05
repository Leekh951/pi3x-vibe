# π³ SPACE · pi3x-vibe

사진 2–8장을 올리면 준비된 Pi3X GPU 서버가 처리하고, 같은 페이지에서 3D 점 구름을 표시합니다. 방문자는 Colab, 노트북 코드, 연결 주소 입력을 보지 않습니다. 사진 업로드 후 자동으로 생성하며, 설정을 바꾸거나 재시도할 때는 **3D 공간 만들기**를 누릅니다.

웹 사이트: **https://leekh951.github.io/pi3x-vibe/**

현재 GPU 서버: **https://huggingface.co/spaces/leekh951/pi3x-vibe** (ZeroGPU). 기본 웹 화면은 이 서버에 자동 연결하며 Colab 실행이 필요 없습니다. 2026-10-05 GPU 예약 시간을 줄인 서버에서 공식 샘플 사진 3장, `fast`로 실제 GPU 추론을 확인했습니다: 250,405개 점, 1.7초(서버 추론 시간, 업로드·대기 시간 제외), 4,757,956바이트 PLY. 모든 점의 좌표·신뢰도가 유한하고 점 개수가 메타데이터와 일치하는 것을 확인했습니다. 같은 서버에 배포된 JavaScript 클라이언트로 사진 전송·완료 이벤트·PLY 다운로드도 확인했습니다.

## 방문자 사용법

1. 같은 공간을 다른 각도에서 찍은 JPG·PNG·WEBP 사진 2–8장을 선택하거나 놓습니다.
2. 업로드와 처리 진행 상황을 보며 기다립니다. 처음에는 사진 3–4장과 ‘가볍게’를 권장합니다.
3. 완성된 공간을 드래그·휠·우클릭으로 탐색합니다. 점 크기, 색 표현, 신뢰도를 조절하고 PLY로 저장할 수 있습니다.

첫 화면의 거실은 **합성 예제**입니다. 실제 사진 결과는 서버에서 반환한 PLY를 받은 뒤 표시합니다. 서버가 준비되지 않은 경우 그 상태를 안내하고 사진과 이전 결과를 유지합니다. 결과는 색이 있는 점 구름이며 정밀 치수 측정이나 메시 생성은 제공하지 않습니다.

새 Pi3X 결과는 바닥으로 보이는 평면을 추정해 자동으로 수평을 맞춥니다. **수평 맞추기**를 펼치면 자동 정렬을 다시 실행하거나 좌우·앞뒤 기울기를 직접 조절하고 원래 방향으로 되돌릴 수 있습니다. 평면을 찾기 어렵거나 벽을 바닥으로 추정하면 수동으로 조절합니다. 실제 중력 센서를 사용하는 보정은 아닙니다. 저장한 PLY에도 보정한 회전을 적용하되 원래 길이 단위·색·신뢰도를 유지합니다. `Y_UP` 표시로 저장된 결과는 다시 불러올 때 자동 보정을 중복 적용하지 않습니다.

처리 화면은 서버 대기 순서, GPU 준비, 실제 Pi3X 진행을 구분하고 경과 시간을 표시합니다. Gradio의 `process_starts`는 `pending` 상태여도 서버 처리가 시작된 것으로 다룹니다. 대기가 길면 **대기 취소**를 누를 수 있으며, 5분 안에 완료되지 않는 요청도 대기를 끝내고 사진을 유지합니다. 화면의 서버 대기 순서는 ZeroGPU 전체의 GPU 배정 순서를 뜻하지 않습니다.

2026-10-05 웹 클라이언트 검증에서 `handle_file(File)`이 사진을 확장자 없는 Blob으로 바꿔 Gradio가 거부하고, SDK의 오류 후 `return()`도 멈추는 문제를 확인했습니다. 성공한 요청도 마지막 완료 이벤트 뒤 `next()`가 멈출 수 있었습니다. `gpu-upload.mjs`로 원본 File 이름과 MIME 정보를 보존해 먼저 업로드하고, `gpu-job.mjs`가 명시적인 완료 이벤트에서 종료하며 SDK의 정리 응답을 무한히 기다리지 않도록 처리합니다.

## 운영자: 고정 주소 GPU 서버 (Hugging Face Spaces)

GPU 백엔드는 Hugging Face Spaces에 배포되어 있습니다. 웹 화면은 기존 GitHub Pages를 사용합니다. 아래 절차는 서버를 새로 만들거나 다른 계정에 배포할 때 사용합니다.

```bash
python3 scripts/build_space.py
```

로컬 설치와 모델 다운로드 없이 `dist/huggingface/`에 업로드할 **4개 파일**(`app.py`, `backend.py`, `requirements.txt`, `README.md`)과 `dist/huggingface.zip`을 만듭니다. ZIP은 보관용이며 Hugging Face에는 폴더 안의 4개 파일을 저장소 최상위에 업로드합니다.

1. [새 Space 만들기](https://huggingface.co/new-space)에서 소유자 `leekh951`, 이름 `pi3x-vibe`, SDK **Gradio**, 공개 **Public**, 하드웨어 **ZeroGPU**를 선택합니다. 선택 가능 여부와 이메일 인증은 계정에서 확인합니다.
2. **Files → Add file → Upload files**에서 위 4개 파일을 최상위에 올리고 커밋합니다. 서버에서 필요한 패키지와 고정된 Pi3 소스·모델을 준비합니다. 모델은 시작할 때 준비하며, 사진 처리 함수에만 GPU를 할당합니다. Colab 공유 링크는 생성하지 않습니다.
3. Space가 **Running**이 되면 먼저 사진 3장 + `fast`로 실제 PLY 생성까지 확인합니다. API가 연결된 것만으로 추론이 검증되지는 않습니다.
4. Space의 **Embed this Space → Direct URL**에 표시된 `https://….hf.space` 주소를 등록합니다.

```bash
python3 scripts/set_backend.py https://실제서버주소.hf.space
```

설정 변경을 커밋·푸시하면 방문자는 같은 GitHub Pages 주소에서 사진만 올립니다. 서버 주소는 재시작해도 유지됩니다. 쉬고 있던 서버는 방문으로 다시 시작하며, 웹은 최대 3분 동안 연결을 재시도합니다. 모델 준비가 더 오래 걸리면 잠시 후 다시 시도할 수 있습니다.

ZeroGPU는 GPU를 24시간 독점하는 방식이 아닙니다. 무료 개인 계정은 이메일 인증·가입 30일 경과 등 조건을 충족하면 최대 2개를 호스팅할 수 있습니다. 방문자별 GPU 사용량·대기열 제한이 있으며 외부 웹에서 로그인 없이 사용하는 요청에는 비로그인 할당량이 적용될 수 있습니다. 무제한 무료 운영을 보장하지 않습니다. [ZeroGPU 공식 안내](https://huggingface.co/docs/hub/spaces-zerogpu)

같은 패키지는 전용 GPU에서도 사용할 수 있습니다. 유료 하드웨어는 사용하지 않는 시간에도 실행 중이면 과금되므로 운영자가 비용을 확인한 뒤 직접 선택해야 합니다. T4-small은 시간당 $0.40, 30일 내내 실행하면 GPU 요금만 약 $288입니다. 요금·계정 요건은 서비스에서 다시 확인하세요. [GPU 운영·요금 안내](https://huggingface.co/docs/hub/spaces-gpus)

사진과 결과는 해당 Space 서버의 임시 디스크에서 처리됩니다. 공개 API 주소를 아는 사람은 사용할 수 있습니다. HF 토큰을 웹 설정·소스 코드에 넣으면 안 됩니다.

GPU 할당 요청도 남은 사용량보다 작아야 합니다. 초기 Space에서 `180s requested vs. 175s left` 오류를 확인했습니다. 현재 Space에는 사진 수·품질에 따라 예약 시간을 줄이는 `app.py`가 적용되어 있습니다(`fast` 3장: 45초, 최대 90초). 수정 후 같은 경로의 실제 추론이 정상 완료되는 것을 확인했습니다. 다른 Space가 초기 파일을 사용한다면 새 `dist/huggingface/app.py`를 다시 업로드해야 적용됩니다. 실제 GPU 할당량의 계산은 서비스 정책에 따라 예약 시간과 다를 수 있습니다.

## 운영자: Colab GPU 서버 시작 (대체 경로)

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

기존 Node가 있는 환경에서는 `node scripts/test_backend.mjs`로 자동 연결을 검증합니다. `node --experimental-default-type=module scripts/test_gradio_transport.mjs`는 실제 배포 SDK의 공개 API 연결·사진 전송·대기열·진행 스트림을 모사 서버로 검증합니다. 로컬 Node가 없으면 설치하지 않아도 되며 GitHub Actions가 이 검증을 실행합니다. `dist/`는 Git에서 제외합니다.

`python3 scripts/test_space.py`는 업로드 패키지와 GPU 서버 주소 검증을 확인합니다. 배포 검증과 자동 연결 검증으로 경로·필수 파일, 방문자 화면의 설정 제거, 서버 주소 갱신, 중복 연결 방지, 연결 실패·시간 초과·재시도, Space 시작 대기를 확인합니다. 자동 연결 테스트는 모사 API이며 실제 모델 추론을 대신하지 않습니다.

`node scripts/test_gpu_job.mjs`는 실제 처리 시작을 대기 순서로 잘못 표시하던 회귀, 진행 상태, 멈춘 요청 시간 초과와 사용자 취소를 확인합니다. GitHub Actions의 **Verify live Pi3X client**는 수동으로 실행할 때만 배포된 JavaScript SDK로 공식 사진 3장을 처리합니다. 실제 GPU를 사용하므로 일반 푸시 검증에서는 실행하지 않습니다.

`node scripts/test_orientation.mjs`는 기울어진 바닥, 큰 벽, 잡음, 평면이 없는 데이터, 수동 회전과 길이 보존을 확인합니다. `node --experimental-default-type=module scripts/test_viewer_orientation.mjs`는 Node 22.15 이상에서 실제 Three.js geometry와 PLY 저장·재불러오기를 확인합니다. 보정한 방향, 신뢰도 필터, 원본 보존, 반복 조절 후 원래 방향 복원을 검증하며 로컬 설치 없이 GitHub Actions에서도 실행합니다.

이전 화면은 Chrome에서 WebGL·PLY 입출력·사진 검증을 확인했습니다. 이전 Colab 실행 코드의 모델 초기화 오류를 CPU 초기화로 수정했고, 수정된 코드의 **실제 ZeroGPU 추론·PLY 다운로드·전체 점 데이터 검증을 완료했습니다.** GitHub Pages 출처의 CORS 응답과 사전 요청도 확인했습니다. 새 자동 생성 화면의 실제 브라우저 조작은 아직 추가 검증이 필요합니다.

Hugging Face 프록시의 OPTIONS 응답에 `Access-Control-Allow-Credentials`가 없어, 공개 API 요청은 쿠키를 보내지 않습니다. `vendor/gradio-client.js`의 8개 `credentials` 설정을 `omit`으로 바꾸었고 파일 상단에 수정 사실을 표시했습니다. 로그인 쿠키가 필요한 비공개 서버는 지원하지 않습니다.

## 주요 파일

- `index.html`, `styles.css`, `app.js`: 사진 업로드, 자동 생성, 진행 상태와 결과 화면
- `orientation.mjs`: 평면 추정에 따른 자동 수평과 수동 회전
- `gpu-backend.mjs`: 공개 서버 자동 연결, 재시도, 연결 상태
- `viewer.js`, `demo.js`: Three.js 점 구름 뷰어와 합성 거실
- `space.config.json`: 저장소·웹 주소·공개 GPU 서버 주소
- `colab/backend.py`, `colab/Pi3X_SPACE.ipynb`: 운영자가 실행하는 GPU 서버
- `hosting/huggingface/`: 고정 주소 Space 서버 시작 코드·원격 의존성·설정
- `scripts/build_space.py`, `scripts/test_space.py`: 로컬 설치 없는 Space 업로드 파일 생성·검증
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
