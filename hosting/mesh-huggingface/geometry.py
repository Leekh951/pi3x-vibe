"""Whole-scene meshing, shared UVs, interior-camera depth and texture baking."""
import io
import itertools
import numpy as np
import open3d as o3d
from PIL import Image
from scipy.ndimage import distance_transform_edt
from plyfile import PlyData

from accelerated import triangle_arrays,camera_oriented_normals
from glb import write_glb

TEXTURE_SIZE = 1024


def read_cloud(path,max_points=100000):
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
    while len(cloud.points) > max_points:
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


def triangulate(cloud,frames=None,report=None,max_faces=30000):
    report=report or (lambda fraction,desc:None)
    diagonal = np.linalg.norm(np.ptp(np.asarray(cloud.points),axis=0))
    report(0,'점군 표면의 방향을 계산하고 있어요.')
    cloud.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=diagonal*.025,max_nn=30))
    report(.2,'촬영한 카메라를 기준으로 표면 방향을 맞추고 있어요.')
    if frames:
        centers=[np.asarray(frame['camera_to_world'])[:3,3] for frame in frames]
        cloud.normals=o3d.utility.Vector3dVector(camera_oriented_normals(
            np.asarray(cloud.points),np.asarray(cloud.normals),centers))
    else:
        # Compatibility path for PLY-only CPU comparisons without camera poses.
        try: cloud.orient_normals_consistent_tangent_plane(20)
        except RuntimeError: cloud.orient_normals_to_align_with_direction()
    distances = np.asarray(cloud.compute_nearest_neighbor_distance())
    radius = max(float(np.median(distances))*1.7,diagonal/600)
    report(.35,'가까운 점들을 연결해 삼각형 표면을 만들고 있어요.')
    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(cloud,
        o3d.utility.DoubleVector([radius,radius*2]))
    mesh.remove_degenerate_triangles(); mesh.remove_duplicated_triangles(); mesh.remove_unreferenced_vertices()
    report(.8,'메시의 중복 면과 지나치게 큰 면을 정리하고 있어요.')
    if len(mesh.triangles) > max_faces: mesh = mesh.simplify_quadric_decimation(max_faces)
    vertices,faces = np.asarray(mesh.vertices),np.asarray(mesh.triangles)
    if not len(faces): raise ValueError('면을 연결하지 못했어요. 더 겹치는 사진으로 만든 PLY를 사용해주세요.')
    edges = vertices[faces][:,[1,2,0]]-vertices[faces]
    faces = faces[(np.linalg.norm(edges,axis=2).max(axis=1) < diagonal*.06)]
    if not len(faces): raise ValueError('유효한 메시 면이 부족해요.')
    colors = np.asarray(mesh.vertex_colors)
    if len(colors) != len(vertices): colors = np.full_like(vertices,.75)
    report(1,'삼각형 표면을 만들었어요.')
    return vertices,faces,colors


def unwrap_surface(vertices,faces,iterations=2):
    import xatlas
    atlas = xatlas.Atlas()
    atlas.add_mesh(vertices.astype(np.float32),faces.astype(np.uint32))
    charts = xatlas.ChartOptions(); charts.max_iterations = iterations
    # A fixed-resolution pack may allocate multiple sub-atlases. The room has
    # one texture, so pack into a single atlas before normalizing to 1024 UVs.
    packing = xatlas.PackOptions(); packing.resolution = 0; packing.padding = 4
    packing.blockAlign = True
    atlas.generate(chart_options=charts,pack_options=packing)
    mapping,indices,coordinates = atlas[0]
    if not np.array_equal(mapping[indices],faces):
        raise ValueError('UV 생성 중 메시의 면 순서가 바뀌었어요.')
    uv = coordinates[indices].copy()
    uv[...,1] = 1-uv[...,1]  # xatlas bottom-left -> image and glTF top-left
    if not np.isfinite(uv).all() or np.any((uv<0)|(uv>1)):
        raise ValueError('유효한 UV를 만들지 못했어요.')
    return uv.reshape(-1,2)


def surface_maps(vertices,faces,colors,uv,report=None):
    """Rasterize every triangle into ONE room-wide non-overlapping UV atlas."""
    shape = (TEXTURE_SIZE,TEXTURE_SIZE)
    world = np.zeros((*shape,3),np.float32)
    texture = np.full((*shape,3),.7,np.float32)
    coverage = np.zeros(shape,bool)
    # Compare distance to UV edges in pixels, not barycentric weights: skinny
    # triangles magnify float32 atlas rounding into large barycentric changes.
    # Shared edges within 0.001 pixel are valid, in either traversal order.
    margin = np.full(shape,-np.inf,np.float32)
    for index,(face,corners) in enumerate(zip(faces,uv.reshape(-1,3,2))):
        if report and index%1024==0:report(index/len(faces))
        x,y,weights=triangle_arrays(corners,TEXTURE_SIZE,TEXTURE_SIZE)
        if not len(x):continue
        pixels = np.asarray(corners,np.float64)*TEXTURE_SIZE
        edge = pixels[[2,0,1]]-pixels[[1,2,0]]
        area = abs(np.linalg.det(np.stack([pixels[1]-pixels[0],pixels[2]-pixels[0]])))
        altitude = area/np.maximum(np.linalg.norm(edge,axis=1),1e-15)
        interior = (weights*altitude).min(axis=1)
        if np.any((margin[y,x]>1e-3) & (interior>1e-3)):
            raise ValueError('UV 표면이 겹쳐 텍스처를 만들 수 없어요.')
        take = interior>margin[y,x]
        x,y,weights,interior = x[take],y[take],weights[take],interior[take]
        world[y,x] = weights@vertices[face]
        texture[y,x] = weights@colors[face]
        coverage[y,x] = True
        margin[y,x] = interior
    if coverage.sum() < 100: raise ValueError('텍스처를 입힐 표면이 부족해요.')
    if report:report(1)
    return world,coverage,texture


def project(points,frame,size):
    pose = np.asarray(frame['camera_to_world'])
    local = (points-pose[:3,3])@pose[:3,:3]
    intrinsic = np.asarray(frame['intrinsics'],dtype=np.float64).copy()
    intrinsic[0] *= size[0]/frame['image_size'][0]
    intrinsic[1] *= size[1]/frame['image_size'][1]
    intrinsic[0,2] += (size[0]/frame['image_size'][0]-1)*.5
    intrinsic[1,2] += (size[1]/frame['image_size'][1]-1)*.5
    projected = local@intrinsic.T
    return projected[...,:2]/np.maximum(local[...,2:],1e-8),local[...,2]


def frame_size(frame):
    width,height = frame['image_size']
    scale = 512/max(width,height)
    return max(64,round(width*scale/8)*8),max(64,round(height*scale/8)*8)


def render_frame(vertices,faces,uv,frame,report=None):
    """Z-buffer an interior input camera. No object-centered turntable cameras."""
    width,height = frame_size(frame)
    xy,z = project(vertices,frame,(width,height))
    depth = np.full((height,width),np.inf,np.float32)
    coordinates = np.zeros((height,width,2),np.float32)
    face_uv = uv.reshape(-1,3,2)
    for index,face in enumerate(faces):
        if report and index%1024==0:report(index/len(faces))
        values = z[face]
        if not np.isfinite(xy[face]).all() or np.any(values<=1e-6): continue
        x,y,weights=triangle_arrays((xy[face]+.5)/[width,height],width,height)
        if not len(x):continue
        # Perspective correction is needed both for UVs and the z-buffer.
        weights = weights/values
        denominator = weights.sum(axis=1)
        distances = 1/denominator
        take = distances<depth[y,x]
        x,y,weights,denominator = x[take],y[take],weights[take],denominator[take]
        depth[y,x] = distances[take]
        coordinates[y,x] = (weights/denominator[:,None])@face_uv[index]
    if np.isfinite(depth).sum() < width*height*.03:
        raise ValueError('카메라에서 장면 표면이 거의 보이지 않아요. 포즈와 PLY를 확인해주세요.')
    if report:report(1)
    return depth,coordinates


def sample_rgb(image,xy):
    height,width = image.shape[:2]
    xy = np.clip(xy,[0,0],[width-1,height-1])
    lower = np.floor(xy).astype(int); upper = np.minimum(lower+1,[width-1,height-1])
    dx,dy = (xy-lower).T
    return (image[lower[:,1],lower[:,0]]*((1-dx)*(1-dy))[:,None]
            +image[lower[:,1],upper[:,0]]*(dx*(1-dy))[:,None]
            +image[upper[:,1],lower[:,0]]*((1-dx)*dy)[:,None]
            +image[upper[:,1],upper[:,0]]*(dx*dy)[:,None])


def bake_camera(texture,painted,world,coverage,frame,depth,image):
    """Only write new visible texels; earlier views' surface colors are immutable."""
    height,width = depth.shape
    y,x = np.where(coverage & ~painted)
    if not len(x): return 0
    xy,z = project(world[y,x],frame,(width,height))
    valid = np.isfinite(xy).all(axis=1)&(z>0)&(xy[:,0]>=0)&(xy[:,0]<width)&(xy[:,1]>=0)&(xy[:,1]<height)
    x,y,xy,z = x[valid],y[valid],xy[valid],z[valid]
    pixels = np.clip(np.floor(xy+.5).astype(int),[0,0],[width-1,height-1])
    nearest = depth[pixels[:,1],pixels[:,0]]
    visible = np.isfinite(nearest)&(np.abs(z-nearest)<np.maximum(z*.015,1e-5))
    x,y,xy = x[visible],y[visible],xy[visible]
    if len(x):
        rgb = np.asarray(image.resize((width,height),Image.Resampling.LANCZOS),np.float32)/255
        texture[y,x] = sample_rgb(rgb,xy)
        painted[y,x] = True
    return len(x)


def view_inputs(texture,painted,depth,coordinates):
    """Render shared texture, preserve painted regions and condition on mesh depth."""
    visible = np.isfinite(depth)
    height,width = depth.shape
    rgb = np.zeros((height,width,3),np.float32)
    rgb[visible] = sample_rgb(texture,coordinates[visible]*TEXTURE_SIZE-.5)
    pixels = np.clip((coordinates*TEXTURE_SIZE).astype(int),0,TEXTURE_SIZE-1)
    locked = painted[pixels[...,1],pixels[...,0]]
    mask = visible & ~locked
    values = 1/depth[visible]
    low,high = np.percentile(values,[2,98])
    gray = np.zeros(depth.shape,np.uint8)
    gray[visible] = np.clip(32+223*(values-low)/max(high-low,1e-6),32,255).astype(np.uint8)
    return (Image.fromarray(np.clip(rgb*255,0,255).astype(np.uint8)),
            Image.fromarray(mask.astype(np.uint8)*255),Image.fromarray(gray).convert('RGB'),int(mask.sum()))


def texture_image(texture,coverage):
    # Dilate into a narrow gutter for bilinear sampling, without painting other charts.
    distance,indices = distance_transform_edt(~coverage,return_indices=True)
    result = texture.copy(); padding = (~coverage)&(distance<=4)
    result[padding] = texture[indices[0][padding],indices[1][padding]]
    return Image.fromarray(np.clip(result*255,0,255).astype(np.uint8))


def export_scene(path,vertices,faces,uv,texture,metadata):
    encoded = io.BytesIO(); texture.save(encoded,format='PNG')
    return write_glb(path,vertices.tolist(),faces.tolist(),uv.tolist(),encoded.getvalue(),
                     np.ones_like(vertices).tolist(),metadata)


def cpu_check():
    """Synthetic room surfaces: depth occlusion, UV unwrap, and view color locks."""
    vertices = np.array([[-1,-1,2],[1,-1,2],[1,1,2],[-1,1,2],
                         [-1,-1,4],[1,-1,4],[1,1,4],[-1,1,4]],np.float64)
    faces = np.array([[0,1,2],[0,2,3],[4,5,6],[4,6,7]],np.int32)
    colors = np.full_like(vertices,.7)
    # Exercise the deployed native wheel as well as the numerical renderer.
    packed = unwrap_surface(vertices,faces)
    if packed.shape != (12,2): raise ValueError('CPU UV check failed')
    # An extremely narrow neighbor amplifies shared-edge float32 rounding.
    edge=(512.5+1e-5)/TEXTURE_SIZE
    seam_uv=np.array([[edge,.1],[edge,.9],[.1,.5],
                      [edge,.1],[edge,.9],[edge-1e-5,.5]])
    seam_vertices=np.column_stack([seam_uv,np.ones(6)])
    seam_faces=np.array([[0,1,2],[3,4,5]])
    seam_colors=np.full_like(seam_vertices,.7)
    first=surface_maps(seam_vertices,seam_faces,seam_colors,seam_uv)
    reverse=surface_maps(seam_vertices,seam_faces[::-1],seam_colors,
                         seam_uv.reshape(2,3,2)[::-1].reshape(6,2))
    np.testing.assert_array_equal(first[1],reverse[1])
    np.testing.assert_allclose(first[0],reverse[0],atol=1e-6)
    try:surface_maps(seam_vertices,seam_faces,seam_colors,np.tile(seam_uv[:3],(2,1)))
    except ValueError:pass
    else:raise ValueError('CPU true UV overlap was not rejected')
    uv = np.array([[.02,.02],[.48,.02],[.48,.98],[.02,.02],[.48,.98],[.02,.98],
                   [.52,.02],[.98,.02],[.98,.98],[.52,.02],[.98,.98],[.52,.98]])
    world,coverage,texture = surface_maps(vertices,faces,colors,uv)
    frame = {'image_size':[512,512],'intrinsics':[[128,0,256],[0,128,256],[0,0,1]],
             'camera_to_world':np.eye(4).tolist()}
    depth,coordinates = render_frame(vertices,faces,uv,frame)
    if abs(float(depth[256,256])-2)>1e-6: raise ValueError('CPU depth occlusion check failed')
    painted = np.zeros_like(coverage)
    count = bake_camera(texture,painted,world,coverage,frame,depth,Image.new('RGB',(512,512),'red'))
    if count < 1000 or painted[:,TEXTURE_SIZE//2:].any(): raise ValueError('CPU visibility check failed')
    before = texture.copy()
    count_again = bake_camera(texture,painted,world,coverage,frame,depth,Image.new('RGB',(512,512),'blue'))
    if count_again or not np.array_equal(before,texture): raise ValueError('CPU surface color lock check failed')
    _,mask,_,_ = view_inputs(texture,painted,depth,coordinates)
    if mask.getpixel((256,256)): raise ValueError('CPU inpainting mask check failed')
    return {'ok':True,'gpu_used':False,'uv_unwrap':True,'uv_shared_edges':True,
            'depth_occlusion':True,'surface_color_lock':True}
