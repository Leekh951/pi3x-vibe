"""Run SPACE with the Python standard library; no packages to install."""
import argparse
import functools
import http.server
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="SPACE 웹 화면 실행")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    url = f"http://localhost:{args.port}/"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    print("SPACE STARTING", flush=True)
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    except OSError as error:
        try:
            with urlopen(url, timeout=2) as response:
                existing = response.read(20000).decode("utf-8")
            if "<title>π³ SPACE" in existing:
                print(f"SPACE READY: {url} (이미 실행 중)", flush=True)
                return
        except Exception:
            pass
        print(f"서버를 시작하지 못했습니다: {error}", file=sys.stderr)
        print("다른 포트 사용: python3 start.py --port 8001", file=sys.stderr)
        raise SystemExit(1)
    print(f"SPACE READY: {url}", flush=True)
    print("위 주소를 브라우저에서 열고 ‘Colab 연결’을 누르세요.", flush=True)
    print("Colab 노트북: " + str(ROOT / "colab/Pi3X_SPACE.ipynb"), flush=True)
    print("VS Code 원격 환경에서는 포트 탭에서 이 포트를 전달하세요.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSPACE 서버 종료", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
