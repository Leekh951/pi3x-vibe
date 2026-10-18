"""Content keys for a session's already prepared scenes; no cross-user cache."""
import hashlib
import json
from pathlib import Path


def input_fingerprint(ply,images,poses,quality):
    files=[(ply,40*1024*1024),*((p,15*1024*1024) for p in images)]
    if poses:files.append((poses,1024*1024))
    signature=[]
    for filename,limit in files:
        path=Path(filename)
        if path.stat().st_size>limit:raise ValueError('파일 크기 제한을 확인해주세요.')
        digest=hashlib.sha256()
        with path.open('rb') as source:
            for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
        signature.append([path.name,digest.hexdigest()])
    return hashlib.sha256(json.dumps([quality,bool(poses),signature],ensure_ascii=False).encode()).hexdigest()
