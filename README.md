# π³ SPACE

사진 몇 장을 Google Colab의 Pi3X로 재구성하고, 브라우저에서 3D 점 구름을 탐색하는 수업 과제용 웹 앱입니다. 로컬에는 패키지를 설치하지 않습니다. HTML, CSS, JavaScript와 기존 Python만 사용합니다.

## 바로 실행

```bash
cd /home/lee/vivecode
python3 start.py
```

Chrome에서 **http://localhost:8000** 을 여세요. `index.html`을 더블클릭하면 브라우저의 ES 모듈 제한 때문에 동작하지 않습니다. 인터넷 연결 없이도 예제 조작, 사진 미리보기, PLY 가져오기·저장을 사용할 수 있습니다.

VS Code에서 `/home/lee/vivecode`를 폴더로 열었다면 **터미널 → 작업 실행 → SPACE: 웹 실행**으로 같은 서버를 시작할 수 있습니다. 원격 SSH·컨테이너 환경에서는 VS Code의 **포트** 탭에서 8000번 포트를 전달하고 브라우저에 표시되는 전달 주소를 사용하세요. 다른 포트가 필요하면 `python3 start.py --port 8001`로 실행할 수 있습니다.

이 방식은 VS Code의 브라우저 제어 플러그인을 사용하지 않습니다. Colab 계정 로그인과 GPU 런타임 시작만 사용자가 직접 진행합니다.

## 실제 사진으로 재구성

1. GitHub Pages 웹 화면의 **Colab 연결 → Colab에서 열기**를 누릅니다. 저장소의 `colab/Pi3X_SPACE.ipynb`를 바로 열며 다운로드·업로드는 필요 없습니다.
2. Colab 마지막 코드 셀의 `VIEWER_URL`을 실제 Pages 주소로 확인합니다. 웹의 **이 페이지로 돌아오는 주소 → 복사**로 가져올 수 있습니다. 아래 배포 설정으로 노트북을 재생성했다면 주소가 이미 들어 있습니다.
3. **런타임 → 런타임 유형 변경 → T4 GPU**를 선택한 뒤 **런타임 → 모두 실행**합니다.
4. 실행 결과의 **SPACE 웹 화면 연결** 링크를 누릅니다. 웹 화면이 열리면서 Colab에 연결합니다. 링크 대신 출력된 `https://….gradio.live` 주소를 웹의 **Colab 연결** 창에 직접 붙여넣어도 됩니다.
5. 같은 공간을 다른 위치에서 촬영한 JPG·PNG·WEBP **2–8장**을 추가합니다. 처음에는 **3–4장 + 가볍게**를 권장합니다.
6. **3D 공간 만들기**를 누릅니다. 첫 실행은 약 5.4 GB의 모델 체크포인트 다운로드와 로딩 때문에 시간이 걸립니다. 정확한 시간은 Colab GPU와 네트워크에 따라 달라집니다.
7. 드래그·휠·우클릭으로 탐색하고, 점 크기와 신뢰도 기준을 조절합니다. **PLY 저장**은 현재 신뢰도 필터를 적용한 점을 저장합니다.

Colab은 계속 열어두어야 합니다. 런타임이 종료되거나 공개 주소가 만료되면 마지막 셀을 다시 실행하고 새 주소를 연결하세요. 공유 주소를 아는 사람은 Colab API를 호출할 수 있습니다. 사진은 재구성 버튼을 누를 때 해당 Colab에 업로드됩니다. Gradio 임시 업로드와 출력은 런타임 디스크에 남을 수 있으므로, 작업 후 Colab의 **런타임 → 연결 해제 및 런타임 삭제**로 정리할 수 있습니다.

Colab에서만 Gradio·huggingface_hub·safetensors를 설치합니다. Colab의 PyTorch·NumPy·Pillow는 그대로 사용하며 torch/CUDA를 다시 설치하지 않습니다. 설치에 사용한 API 버전을 고정했습니다. Pi3X 공식 소스와 가중치도 버전을 고정했으며, image-only 분기와 PyTorch attention을 사용합니다. CUDA 확장, xFormers, flash-attn의 추가 설치는 없습니다.

## GitHub Pages 배포

이 폴더는 `main` 브랜치의 Git 저장소입니다. `.github/workflows/pages.yml`이 `main`에 푸시할 때마다 사이트를 배포합니다. Python 표준 라이브러리로 웹 파일을 모으고, GitHub 저장소와 실제 Pages 주소를 배포 설정에 넣습니다. 로컬이나 배포 과정에서 npm·pip 설치는 필요 없습니다.

1. VS Code에서 `/home/lee/vivecode`를 폴더로 엽니다.
2. 왼쪽 **소스 제어 → GitHub에 게시 / Publish to GitHub**를 눌러 로그인하고 **공개 저장소**를 만듭니다. 예를 들어 저장소 이름은 `pi3x-space`로 지정합니다. 초기화와 첫 커밋은 이미 준비되어 있습니다.
3. GitHub 저장소의 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 선택합니다. 기존 안내의 **Deploy from a branch** 대신 이 구성을 사용합니다.
4. **Actions → Deploy SPACE to GitHub Pages → Run workflow → main**으로 첫 배포를 실행합니다. 처음 게시할 때 Pages가 비활성화되어 실패한 실행이 있다면 같은 화면에서 **Re-run all jobs**로 다시 실행할 수도 있습니다.
5. 완료되면 **Settings → Pages → Visit site**로 엽니다. 보통 주소는 `https://계정명.github.io/pi3x-space/`입니다. 이후 수정은 커밋 후 **변경 내용 동기화 / Sync Changes**하면 자동 배포됩니다.

배포 결과에는 HTML·CSS·JavaScript·`vendor/`·`colab/Pi3X_SPACE.ipynb`·`space.config.json`만 들어갑니다. 로컬 서버, 테스트 도구, Git 메타데이터, 스크린샷은 배포 대상에서 제외합니다. 저장소의 원본 파일은 유지합니다. `.nojekyll`이 포함되어 있고 Python GPU 코드는 Colab에서 실행됩니다.

Pages 배포 시 웹의 **Colab에서 열기**는 해당 저장소 `main` 브랜치의 노트북을 직접 엽니다. 노트북 원본의 `VIEWER_URL`이 아직 `localhost`이면 **이 페이지로 돌아오는 주소 → 복사**를 이용해 실제 배포 주소로 바꿔주세요. 아래 원본 설정을 지정하고 노트북을 재생성해 커밋하면 다음부터 해당 주소가 기본값이 됩니다.

### 로컬 페이지와 노트북에도 배포 주소 적용

`space.config.json`을 아래처럼 수정하세요. 이 원본 설정은 로컬 8000 페이지에서도 저장소의 노트북을 바로 열 때 사용합니다. GitHub Actions는 배포 파일에 실제 저장소·브랜치·Pages 주소를 별도로 자동 적용합니다.

```json
{
  "githubRepository": "계정명/pi3x-space",
  "githubRef": "main",
  "notebookPath": "colab/Pi3X_SPACE.ipynb",
  "viewerUrl": "https://계정명.github.io/pi3x-space/"
}
```

```bash
python3 scripts/build_notebook.py
```

설정 파일과 다시 생성된 노트북을 커밋하고 동기화하세요. 커스텀 도메인은 GitHub Pages 설정에서 지정합니다. 원본의 `viewerUrl`도 해당 주소로 맞추면 Colab 복귀 링크에 적용됩니다.

### 설치 없이 배포 파일 검증

```bash
python3 scripts/test_pages.py
python3 scripts/build_pages.py
```

`dist/`에 웹 배포 파일이 생성됩니다. 이 폴더는 Git에서 제외됩니다. 주소를 지정해 미리 확인할 수도 있습니다.

```bash
python3 scripts/build_pages.py --repository 계정명/pi3x-space --viewer-url https://계정명.github.io/pi3x-space/ --ref main
```

로컬 8000에서도 **페이지에서 노트북 보기**로 실제 `.ipynb` 내용을 확인합니다. 아직 저장소를 정하지 않았다면 **실행 코드 전체 복사** 후 Colab의 새 노트북 코드 셀 하나에 붙여넣고 실행하세요. 복사 코드는 현재 웹 주소를 복귀 주소로 자동 적용합니다. 파일 다운로드는 선택 사항입니다.

## 화면 기능

- 페이지 내 노트북 미리보기, 전체 실행 코드 복사, GitHub → Colab 바로 열기
- 사진 드래그 앤 드롭, 미리보기, 삭제, 개수·형식·크기 검증
- 실제 Colab 연결 및 `/reconstruct` API 확인, GPU 대기·진행·실패 상태
- 회전, 확대, 이동, 위에서 보기, 자동 회전, 전체 화면
- 원본 색·높이 색, 점 크기, 신뢰도 필터, 표시 중인 점 개수
- binary / ASCII PLY 가져오기와 binary PLY 저장
- 반응형 화면, 모바일 터치, 한국어 가이드

첫 화면의 거실은 **합성 예제**입니다. Pi3X가 사진으로 만든 결과라고 표시하지 않습니다. 결과는 **점 구름**이며, 메시·텍스처 생성이나 정확한 치수 측정은 제공하지 않습니다. Pi3X OpenCV 좌표를 화면에서 Y-up 방향으로 변환하고 정규화하지만, PLY 내보내기에는 원래 좌표를 보존합니다. 외부 PLY는 OpenCV 좌표를 기본 가정합니다.

## 파일

- `index.html`, `styles.css`: 화면과 반응형 스타일
- `start.py`, `.vscode/tasks.json`: 설치 없이 웹 서버 시작, VS Code 실행 작업
- `app.js`: 사진·Colab 연결·진행 상태·가져오기·저장
- `notebook.js`, `space.config.json`: 페이지 내 노트북, Colab 링크·배포 주소 설정
- `viewer.js`: Three.js 점 구름 뷰어와 PLY 입출력
- `demo.js`: 재현 가능한 합성 거실 데이터
- `colab/backend.py`: 노트북에 포함된 실제 GPU 백엔드 원본
- `colab/Pi3X_SPACE.ipynb`: 배포·업로드 가능한 자체 포함 Colab 노트북
- `scripts/build_notebook.py`: backend.py 수정 후 노트북 재생성 도구 (표준 Python)
- `.github/workflows/pages.yml`: main 푸시 시 GitHub Pages 배포
- `scripts/build_pages.py`, `scripts/test_pages.py`: 설치 없는 배포 파일 생성·검증
- `vendor/`: 버전이 고정된 브라우저 라이브러리와 라이선스

노트북 재생성:

```bash
python3 scripts/build_notebook.py
```

## 검증 범위

설치된 Chrome에서 데스크톱·모바일 레이아웃과 실제 WebGL 렌더링, 사진 업로드 검증, PLY 입출력 및 필터링을 확인했고, 33개 브라우저 검증을 통과했습니다. Colab 응답을 모사한 테스트로 업로드→결과 표시와 오류 복구 경로를 검증했습니다. 노트북 코드 셀의 Python 문법, 백엔드 원본과의 일치, 공식 체크포인트 헤더에 필요한 정규화·신뢰도 텐서가 있는지도 확인했습니다. VS Code 실행을 위한 서버와 Colab 복귀 링크의 생성·주소 검증도 확인했습니다. 페이지 내 노트북과 GitHub Pages 링크는 코드 수준에서 주소 변환·셀 내용·복사 흐름을 확인했습니다. 배포 파일과 프로젝트 하위 경로의 의존성, 설정 주입, 원본 유지, 노트북 Python 문법을 표준 Python 테스트로 검증했습니다. 새 노트북 창의 실제 브라우저 화면과 GitHub의 실제 배포 실행은 아직 확인하지 않았습니다.

**Google 계정의 실제 Colab GPU에서의 모델 다운로드·추론·공개 터널 실행은 이 로컬 환경에서 검증하지 않았습니다.** 수업 발표 전 본인의 Colab에서 사진 3–4장으로 한 번 실행하고, 결과 PLY를 저장해두세요.

브라우저 검증 스크립트는 Python 표준 라이브러리만 사용합니다. 웹 서버가 실행 중인 상태에서 설치된 Chrome을 테스트 모드로 시작합니다.

```bash
google-chrome --headless --no-sandbox --disable-dev-shm-usage --enable-unsafe-swiftshader --remote-debugging-port=9222 --remote-allow-origins=http://localhost:9222 --user-data-dir=/tmp/space-chrome 'http://127.0.0.1:8000/?test=1'
```

별도 터미널에서 `python3 scripts/test_browser.py`를 실행합니다. `preview-desktop.png`와 `preview-mobile.png`에 캡처가 저장됩니다. 테스트의 Colab 응답은 모사 데이터이며 실제 GPU 추론 검증을 대신하지 않습니다.

## 참고와 라이선스

- [Pi3 / Pi3X 공식 저장소](https://github.com/yyfz/Pi3): BSD-3-Clause 코드, CC BY-NC 4.0 가중치. 이 프로젝트는 교육·비상업 과제 범위에 맞춰 제작했습니다.
- [Pi3X 가중치](https://huggingface.co/yyfz233/Pi3X)
- [Gradio JavaScript client](https://www.gradio.app/guides/getting-started-with-the-js-client): 브라우저에서 Colab API 호출
- Three.js **0.170.0**: MIT, `vendor/THREE-LICENSE.txt`
- Gradio JavaScript client **1.17.0**: Apache-2.0, `vendor/GRADIO-LICENSE.txt`
