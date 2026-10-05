"""Exercise a running Pi3X server with official sample photos (uses GPU)."""
import argparse
import json
import math
import re
import struct
import time
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import quote

from set_backend import normalize_endpoint

SOURCE_REVISION = "9fa3ddb3f8d53041f8b2738df404f62223bbaa7b"


def exercise(endpoint, destination):
    endpoint = normalize_endpoint(endpoint)
    started = time.monotonic()

    def request(path, body=None, headers=None):
        url = path if path.startswith("https://") else endpoint + path
        req = urllib.request.Request(url, data=body, headers=headers or {})
        return urllib.request.urlopen(req, timeout=60)

    with request("/config") as response:
        config = json.load(response)
    prefix = config.get("api_prefix") or "/gradio_api"
    boundary = "SPACE-" + uuid.uuid4().hex
    parts = []
    for index in range(3):
        name = f"{index}.png"
        url = f"https://raw.githubusercontent.com/yyfz/Pi3/{SOURCE_REVISION}/examples/room/rgb/{name}"
        with request(url) as response:
            photo = response.read()
        assert photo.startswith(b"\x89PNG"), "Official sample is not a PNG"
        assert len(photo) <= 15 * 1024 * 1024
        print(f"Official photo {index + 1}: {len(photo):,} bytes", flush=True)
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\nContent-Type: image/png\r\n\r\n'.encode() + photo + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    with request(prefix + "/upload", b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"}) as response:
        paths = json.load(response)
    assert len(paths) == 3, paths
    input_data = [[{"path": path, "meta": {"_type": "gradio.FileData"}} for path in paths], "fast"]
    # Use the normal queue transport once. It exposes GPU/quota errors directly
    # without spending another ZeroGPU request on a diagnostic retry.
    session = uuid.uuid4().hex
    dependency = next(item for item in config["dependencies"] if item.get("api_name") == "reconstruct")
    payload = {"data": input_data, "fn_index": dependency["id"], "session_hash": session}
    with request(prefix + "/queue/join", json.dumps(payload).encode(), {"Content-Type": "application/json"}) as response:
        event_id = json.load(response)["event_id"]
    print("GPU reconstruction requested:", event_id, flush=True)
    output = None
    with request(prefix + "/queue/data?session_hash=" + session) as response:
        for raw in response:
            if time.monotonic() - started > 600:
                raise TimeoutError("GPU queue/inference did not complete within ten minutes")
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            message = json.loads(line.split(":", 1)[1].strip())
            stage = message.get("msg")
            if stage == "process_completed":
                if not message.get("success"):
                    raise RuntimeError(f"GPU inference failed: {message.get('output')}")
                output = message["output"]["data"]
                break
            if stage in {"queue_full", "unexpected_error", "server_stopped"}:
                raise RuntimeError(f"GPU queue failed: {message}")
            if stage != "heartbeat":
                print("GPU queue:", json.dumps(message, ensure_ascii=False), flush=True)
    assert output and output[0].get("path"), output
    with request(prefix + "/file=" + quote(output[0]["path"], safe="")) as response:
        ply = response.read()
    split = ply.index(b"end_header\n") + len(b"end_header\n")
    header = ply[:split].decode()
    assert "format binary_little_endian 1.0" in header
    count = int(re.search(r"element vertex (\d+)", header)[1])
    assert count > 0
    # Backend records: XYZ float32, RGB uint8, confidence float32 (19 bytes).
    assert len(ply) - split == count * 19, (len(ply), count)
    low, high = [math.inf] * 3, [-math.inf] * 3
    for index in range(count):
        x, y, z, red, green, blue, confidence = struct.unpack_from("<fffBBBf", ply, split + index * 19)
        assert all(math.isfinite(value) for value in (x, y, z, confidence))
        assert 0 <= confidence <= 1
        for axis, value in enumerate((x, y, z)):
            low[axis], high[axis] = min(low[axis], value), max(high[axis], value)
    assert any(high[axis] - low[axis] > 1e-6 for axis in range(3)), "Degenerate point cloud"
    assert output[1]["engine"] == "Pi3X"
    assert output[1]["image_count"] == 3 and output[1]["point_count"] == count
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(ply)
    destination.with_suffix(".json").write_text(json.dumps(output[1], ensure_ascii=False, indent=2) + "\n")
    print(f"PASS actual GPU inference: {count:,} finite point records, {len(ply):,} PLY bytes", flush=True)
    print("Metadata:", json.dumps(output[1], ensure_ascii=False), flush=True)
    print("Saved:", destination, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("endpoint")
    parser.add_argument("--output", type=Path, default=Path("/tmp/space-live-result.ply"))
    args = parser.parse_args()
    exercise(args.endpoint, args.output)
