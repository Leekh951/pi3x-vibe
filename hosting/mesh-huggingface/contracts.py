"""Portable camera contract; deliberately independent of torch/numpy."""
import math


def matrix(value, rows, cols):
    if not isinstance(value, list) or len(value) != rows:
        raise ValueError('카메라 행렬 크기를 확인해주세요.')
    if any(not isinstance(row, list) or len(row) != cols for row in value):
        raise ValueError('카메라 행렬 크기를 확인해주세요.')
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
           for row in value for x in row):
        raise ValueError('카메라 행렬에 유효하지 않은 값이 있어요.')
    return value


def validate_cameras(document, names):
    if not isinstance(document,dict):
        raise ValueError('카메라 JSON 형식을 확인해주세요.')
    if document.get('coordinate_system') != 'OpenCV' or document.get('pose_convention') != 'camera_to_world':
        raise ValueError('포즈는 OpenCV 좌표계의 camera_to_world 형식이어야 해요.')
    frames = document.get('frames', [])
    if not isinstance(frames, list) or len(frames) != len(names):
        raise ValueError('사진과 카메라 포즈 개수가 달라요.')
    if len(set(names)) != len(names):
        raise ValueError('사진 파일 이름은 서로 달라야 해요.')
    mapped = {}
    for frame in frames:
        if not isinstance(frame,dict):
            raise ValueError('카메라 frames 형식을 확인해주세요.')
        name = frame.get('image')
        if name not in names or name in mapped:
            raise ValueError('카메라 포즈의 사진 이름과 업로드한 이름을 맞춰주세요.')
        intrinsic = matrix(frame.get('intrinsics'), 3, 3)
        pose = matrix(frame.get('camera_to_world'), 4, 4)
        size = frame.get('image_size')
        if not isinstance(size, list) or len(size) != 2 or any(type(x) is not int or not 28 <= x <= 20000 for x in size):
            raise ValueError('image_size에는 사진의 [너비, 높이]를 넣어주세요.')
        if intrinsic[0][0] <= 0 or intrinsic[1][1] <= 0 or any(abs(a-b) > 1e-6 for a,b in zip(intrinsic[2], [0,0,1])):
            raise ValueError('카메라 초점거리와 투영 행렬을 확인해주세요.')
        if any(abs(a-b) > 1e-6 for a,b in zip(pose[3], [0,0,0,1])):
            raise ValueError('camera_to_world의 마지막 행은 [0,0,0,1]이어야 해요.')
        for i in range(3):
            for j in range(3):
                dot = sum(pose[k][i]*pose[k][j] for k in range(3))
                if abs(dot-(i == j)) > .015:
                    raise ValueError('카메라 회전 행렬에 스케일이나 왜곡이 있어요.')
        r = pose
        determinant = (r[0][0]*(r[1][1]*r[2][2]-r[1][2]*r[2][1])
                       -r[0][1]*(r[1][0]*r[2][2]-r[1][2]*r[2][0])
                       +r[0][2]*(r[1][0]*r[2][1]-r[1][1]*r[2][0]))
        if abs(determinant-1) > .02:
            raise ValueError('카메라 회전 방향을 확인해주세요.')
        mapped[name] = frame
    return [mapped[name] for name in names]


def validate_prompt(prompt):
    if not isinstance(prompt, str) or not 2 <= len(prompt.strip()) <= 600:
        raise ValueError('원하는 재질과 분위기를 2–600자로 적어주세요.')
    return prompt.strip()
