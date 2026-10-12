"""CPU reconstruction, pose alignment, visibility-aware camera UVs."""
import io
import itertools
import numpy as np
import open3d as o3d
from PIL import Image
from scipy.ndimage import minimum_filter
from plyfile import PlyData

from contracts import validate_cameras
from glb import write_glb

TILE = (384,224)


def read_cloud(path):
    if path.stat().st_size > 40*1024*1024:
        raise ValueError('PLY는 40 MB 이하로 선택해주세요.')
    with path.open('rb') as stream:
        header = stream.read(65536)
    if header.splitlines()[0:1] != [b'ply'] or b'end_header' not in header:
        raise ValueError('올바른 PLY 파일을 선택해주세요.')
    import re
    count = re.search(rb'element vertex\s+(\d+)',header)
    if not count or not 100 <= int(count[1]) <= 2000000:
        raise ValueError('점이 100–2,000,000개인 PLY를 선택해주세요.')
    if any(kind != b'vertex' and int(amount) != 0 for kind,amount in re.findall(rb'element\s+(\w+)\s+(\d+)',header)):
        raise ValueError('면 데이터가 아닌 Pi3X 점군 PLY를 선택해주세요.')
    data = PlyData.read(str(path))['vertex'].data
    points = np.stack([data[k] for k in ('x','y','z')],axis=1).astype(np.float64)
    names = data.dtype.names
    keep = np.isfinite(points).all(axis=1)
    if 'confidence' in names: keep &= np.isfinite(data['confidence']) & (data['confidence'] >= .1)
    colors = (np.stack([data[k] for k in ('red','green','blue')],axis=1)/255
              if all(k in names for k in ('red','green','blue')) else np.full_like(points,.7))
    points,colors = points[keep],np.clip(colors[keep],0,1)
    if len(points) < 100: raise ValueError('신뢰도가 충분한 점이 너무 적어요.')
    cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
    cloud.colors = o3d.utility.Vector3dVector(colors)
    diagonal = np.linalg.norm(np.ptp(points,axis=0))
    if not np.isfinite(diagonal) or diagonal < 1e-6: raise ValueError('공간 크기를 확인해주세요.')
    voxel = diagonal/300
    cloud = cloud.voxel_down_sample(voxel)
    while len(cloud.points) > 100000:
        voxel *= 1.4
        cloud = cloud.voxel_down_sample(voxel)
    basis = 'Y_UP' if b'comment SPACE coordinate_system Y_UP' in header else 'OpenCV'
    return cloud,basis


def align_recovered(predicted, target, cameras):
    """Recovered Pi3X coordinates are aligned to the supplied PLY, never substituted."""
    predicted = predicted[np.isfinite(predicted).all(axis=1)]
    if len(predicted) < 100: raise ValueError('포즈를 복원할 유효한 점이 부족해요.')
    src = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(predicted[::max(1,len(predicted)//12000)]))
    dst = target.uniform_down_sample(max(1,len(target.points)//12000))
    a,b = np.asarray(src.points),np.asarray(dst.points)
    ca,cb = np.median(a,axis=0),np.median(b,axis=0)
    scale = np.linalg.norm(np.percentile(b,95,axis=0)-np.percentile(b,5,axis=0))/max(1e-8,np.linalg.norm(np.percentile(a,95,axis=0)-np.percentile(a,5,axis=0)))
    src.points = o3d.utility.Vector3dVector(a*scale)
    ca *= scale
    threshold = np.linalg.norm(np.ptp(b,axis=0))*.025
    rotations = [np.eye(3)]
    va = np.linalg.eigh(np.cov(a.T))[1]
    vb = np.linalg.eigh(np.cov(b.T))[1]
    for signs in itertools.product((-1,1),repeat=3):
        rotation = vb@np.diag(signs)@va.T
        if np.linalg.det(rotation) > 0: rotations.append(rotation)
    results = []
    for rotation in rotations:
        initial = np.eye(4); initial[:3,:3] = rotation; initial[:3,3] = cb-rotation@ca
        result = o3d.pipelines.registration.registration_icp(src,dst,threshold,initial,
            o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=35))
        results.append(result)
    best = max(results,key=lambda x:(x.fitness,-x.inlier_rmse))
    if best.fitness < .55:
        raise ValueError('사진과 PLY의 좌표를 맞추지 못했어요. PLY 생성에 사용한 원본 사진과 포즈 파일을 넣어주세요.')
    rotation,translation = best.transformation[:3,:3],best.transformation[:3,3]
    for frame in cameras['frames']:
        pose = np.asarray(frame['camera_to_world'])
        pose[:3,:3] = rotation@pose[:3,:3]
        pose[:3,3] = rotation@(pose[:3,3]*scale)+translation
        frame['camera_to_world'] = pose.tolist()
    return cameras, {'alignment_fitness':round(best.fitness,3),'alignment_rmse':round(best.inlier_rmse,5)}


def triangulate(cloud):
    diagonal = np.linalg.norm(np.ptp(np.asarray(cloud.points),axis=0))
    cloud.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=diagonal*.025,max_nn=30))
    # Orient locally; no watertight surface or unseen room geometry is invented.
    try: cloud.orient_normals_consistent_tangent_plane(20)
    except RuntimeError: cloud.orient_normals_to_align_with_direction()
    distances = np.asarray(cloud.compute_nearest_neighbor_distance())
    radius = max(float(np.median(distances))*1.7,diagonal/600)
    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(cloud,
        o3d.utility.DoubleVector([radius,radius*2]))
    mesh.remove_degenerate_triangles(); mesh.remove_duplicated_triangles()
    if len(mesh.triangles) > 60000: mesh = mesh.simplify_quadric_decimation(60000)
    vertices,faces = np.asarray(mesh.vertices),np.asarray(mesh.triangles)
    if not len(faces): raise ValueError('면을 연결하지 못했어요. 더 겹치는 사진으로 만든 PLY를 사용해주세요.')
    edges = vertices[faces][:,[1,2,0]]-vertices[faces]
    faces = faces[(np.linalg.norm(edges,axis=2).max(axis=1) < diagonal*.06)]
    if not len(faces): raise ValueError('유효한 메시 면이 부족해요.')
    colors = np.asarray(mesh.vertex_colors)
    if len(colors) != len(vertices): colors = np.full_like(vertices,.75)
    return vertices,faces,colors


def camera_uv(vertices,faces,cloud,frames):
    columns,rows = 2,(len(frames)+1)//2
    width,height = TILE[0]*columns,TILE[1]*rows
    # Reserve a white strip for unseen faces, preserving their vertex colors.
    atlas_height = height+16
    triangles = vertices[faces]
    centroids = triangles.mean(axis=1)
    normal = np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    normal /= np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-8)
    best = np.full(len(faces),-np.inf)
    uv = np.tile([.5,(height+8)/atlas_height],(len(faces),3,1))
    view_ids = np.full(len(faces),-1)
    points = np.asarray(cloud.points)
    for index,frame in enumerate(frames):
        pose = np.asarray(frame['camera_to_world']); intrinsic = np.asarray(frame['intrinsics']).copy()
        intrinsic[0] *= TILE[0]/frame['image_size'][0]
        intrinsic[1] *= TILE[1]/frame['image_size'][1]
        def project(world):
            local = (world-pose[:3,3])@pose[:3,:3]
            projected = local@intrinsic.T
            return projected[...,:2]/np.maximum(projected[...,2:],1e-8),local[...,2]
        xy,z = project(triangles)
        center_xy,center_z = project(centroids)
        cloud_xy,cloud_z = project(points)
        grid = np.full((TILE[1],TILE[0]),np.inf)
        visible = (cloud_z>0)&(cloud_xy[:,0]>=0)&(cloud_xy[:,0]<TILE[0])&(cloud_xy[:,1]>=0)&(cloud_xy[:,1]<TILE[1])
        pixels = cloud_xy[visible].astype(int)
        np.minimum.at(grid,(pixels[:,1],pixels[:,0]),cloud_z[visible])
        grid = minimum_filter(grid,size=7)
        centers = np.clip(center_xy,0,np.array(TILE)-1).astype(int)
        nearest = grid[centers[:,1],centers[:,0]]
        valid = (z>0).all(axis=1)&(xy[...,0]>=0).all(axis=1)&(xy[...,0]<TILE[0]).all(axis=1)&(xy[...,1]>=0).all(axis=1)&(xy[...,1]<TILE[1]).all(axis=1)
        valid &= np.isfinite(nearest)&(np.abs(center_z-nearest)<np.maximum(nearest*.06,.005))
        direction = pose[:3,3]-centroids
        distance = np.linalg.norm(direction,axis=1)
        cosine = np.abs((normal*direction).sum(axis=1))/np.maximum(distance,1e-8)
        score = cosine/np.maximum(distance,1e-6)
        take = valid&(score>best)
        best[take] = score[take]; view_ids[take] = index
        uv[take] = (xy[take]+[index%2*TILE[0],index//2*TILE[1]])/[width,atlas_height]
    return uv.reshape(-1,2),view_ids,(width,height)


def build_atlas(images):
    atlas = Image.new('RGB',(TILE[0]*2,TILE[1]*((len(images)+1)//2)),(40,45,48))
    for i,image in enumerate(images):
        atlas.paste(image.resize(TILE,Image.Resampling.LANCZOS),(i%2*TILE[0],i//2*TILE[1]))
    return atlas


def export_scene(path,vertices,faces,uv,colors,view_ids,atlas,metadata):
    # Observed faces use camera textures; unobserved faces keep original PLY color.
    padded = Image.new('RGB',(atlas.width,atlas.height+16),'white'); padded.paste(atlas,(0,0))
    encoded = io.BytesIO(); padded.save(encoded,format='PNG')
    tinted = np.where(colors<=.04045,colors/12.92,((colors+.055)/1.055)**2.4)
    # Duplicated corners permit per-face fallback without tinting textured faces.
    indices = faces.reshape(-1)
    corner_colors = np.ones((len(indices),3))
    fallback = np.repeat(view_ids<0,3)
    corner_colors[fallback] = tinted[indices[fallback]]
    expanded = vertices[indices]
    sequential = np.arange(len(indices)).reshape(-1,3)
    return write_glb(path,expanded.tolist(),sequential.tolist(),uv.tolist(),encoded.getvalue(),corner_colors.tolist(),metadata)
