# Pi3X 집 GPU 서버 (Tailscale Funnel)

Hugging Face ZeroGPU 대신 이 PC의 GPU로 `/reconstruct` API를 제공합니다. API 계약과
추론 코드(`colab/backend.py`)는 Space와 같으므로 웹 화면은 주소만 바꿔 연결합니다.

```
GitHub Pages (브라우저) ──HTTPS──▶ https://pi3x.<tailnet>.ts.net (Tailscale Funnel)
                                      └─▶ 127.0.0.1:7860  Gradio + Pi3X (RTX GPU, 이 컨테이너)
```

## 처음 한 번

```bash
hosting/local/setup.sh   # git·curl(apt), uv, Python 3.10, torch cu128, Pi3 고정 커밋, 가중치 5.1GB, tailscale
hosting/local/up.sh      # 서버 시작 → Tailscale 로그인 URL, Funnel 승인 URL을 차례로 안내
python scripts/set_backend.py https://pi3x.<tailnet>.ts.net   # 실제 /reconstruct 확인 후 등록
```

`space.config.json` 변경을 커밋·푸시하면 Pages가 새 주소로 배포됩니다. Funnel 주소는 고정이므로
이후 재시작에는 다시 등록할 필요가 없습니다.

## 재시작 후

컨테이너나 PC를 재시작하면 `hosting/local/up.sh`만 실행합니다. 로그인 상태는
`/root/workspace/pi3x-runtime/tailscale`에 남습니다. 중지는 `hosting/local/down.sh`입니다.
서버가 꺼져 있으면 방문자 화면은 "서버에 연결하지 못했어요"를 표시하고 사진은 유지합니다.

## 저장 위치

- 런타임 전체: `/root/workspace/pi3x-runtime/` (Git 밖, 마운트된 디스크라 컨테이너를 다시 만들어도 유지)
- apt로 설치하는 `git`, `curl`만 컨테이너가 새로 만들어지면 `setup.sh`가 다시 설치합니다.
- `uv-cache/`(약 6.7GB)는 재설치용 캐시입니다. 디스크가 부족하면 지워도 동작에는 영향이 없습니다.

## 보안·운영 메모

- Gradio는 `127.0.0.1`에만 열립니다. 외부 경로는 Funnel뿐이고 LAN에는 노출되지 않습니다.
- tailscaled는 userspace 모드입니다. `network_mode: host` 컨테이너라도 호스트에 TUN·라우팅·DNS를 추가하지 않습니다.
- 공개 주소를 아는 누구나 사용할 수 있습니다. 사진 장당 15MB 제한은 Space와 같습니다.

## 여러 사람이 동시에 쓸 때 (대기열)

- GPU는 **한 번에 1건**만 처리합니다(VRAM 초과 방지). 나머지는 Gradio 대기열에서 순서를 기다립니다.
- 대기열 크기는 `PI3X_QUEUE_SIZE`(기본 16)입니다. 예: `PI3X_QUEUE_SIZE=32 hosting/local/up.sh`.
- 방문자 화면은 "앞에 N명이 기다리고 있어요"와 서버가 보낸 예상 시간을 표시합니다.
- 대기열이 가득 차면 사진을 다시 올리지 않고 5초마다 자동으로 재시도합니다(최대 24번, 약 2분). 그래도 자리가 없으면 "지금 이용자가 많아요"를 안내합니다.
- "대기 취소"나 탭 닫기로 떠난 사람의 대기 작업은 GPU를 쓰지 않고 대기열에서 빠집니다(로컬 Chromium에서 확인, Funnel 경유는 미확인).
- 2026-11-07 부하 시험: 동시 사용자 18명이 사진 8장 `detail`을 90초 동안 연속 요청했을 때 58건 모두 성공, VRAM 최대 11.5GB. 한 건 처리 간격은 약 2초였고, 브라우저는 대기열 진입 후 "앞에 13명"에서 26초 만에 결과를 받았습니다.
- 방문자 사진과 결과는 이 PC의 `/tmp/gradio`, `/tmp/SPACE_results`에 저장되고 6시간 뒤 정리됩니다.
- Pi3X 가중치는 CC BY-NC 4.0입니다. 비상업 연구·교육용으로만 운영합니다.

## 확인한 수치 (RTX 4060 Ti 16GB, 2026-11-07)

공식 room 사진, 서버 처리 시간(업로드·대기 제외):

| 입력 | 처리 시간 | 점 개수 | 최대 VRAM |
|---|---|---|---|
| 3장 `fast` | 2.1초 | 250,487 | 8.1GB |
| 3장 `detail` | 0.6초 | 600,000 | 8.9GB |
| 8장 `detail` | 1.7초 | 600,000 | 11.6GB |

공개 주소(Funnel) 경유 3장 `fast`: 업로드 6.5초, 추론 2.2초, PLY 4.7MB 다운로드 20.1초. 집 회선은 약 4.2MB/s지만
Funnel 중계가 약 0.1–0.25MB/s라 대기 시간 대부분은 전송입니다(gzip은 PLY를 11%만 줄여 적용하지 않음).

모델 적재 약 25초, 대기 상태 VRAM 약 3.6GB. 메시(`meshEndpoint`)는 계속 Hugging Face Space를 사용합니다.
