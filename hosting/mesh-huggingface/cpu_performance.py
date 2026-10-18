"""Bounded synthetic CPU comparisons; never calls models or acquires ZeroGPU."""
import time
import numpy as np
from accelerated import triangle_arrays,camera_oriented_normals
from raster import triangle_samples


def legacy_arrays(corners,width,height):
    samples=list(triangle_samples(corners,width,height))
    if not samples:return np.empty(0,np.intp),np.empty(0,np.intp),np.empty((0,3))
    xy=np.array([(s[0],s[1]) for s in samples])
    return xy[:,0],xy[:,1],np.array([s[2] for s in samples])


def verify_numerics():
    random=np.random.default_rng(951)
    cases=[np.array([[0,0],[1,0],[0,1]]),np.array([[0,0],[.5,.5],[1,1]]),
           np.array([[-2,-2],[2,-2],[0,2]]),np.array([[.1,.1],[.12,.1],[.1,.12]])]
    cases.extend(random.uniform(-.5,1.5,(80,3,2)))
    for corners in cases:
        for triangle in (corners,corners[::-1]):
            expected=legacy_arrays(triangle,64,48);actual=triangle_arrays(triangle,64,48)
            if not np.array_equal(expected[0],actual[0]) or not np.array_equal(expected[1],actual[1]):
                raise ValueError('CPU raster coverage differs from the reference')
            np.testing.assert_allclose(expected[2],actual[2],atol=1e-12,rtol=1e-10)
    points=np.array([[-1,0,0],[1,0,0],[0,1,0],[0,-1,0]],np.float64)
    normals=points.copy();centers=np.array([[0,0,0],[.1,0,0]])
    oriented=camera_oriented_normals(points,normals,centers)
    if not np.all(np.einsum('ij,ij->i',oriented,-points)>0):raise ValueError('Camera-facing surface normals failed')
    np.testing.assert_array_equal(normals,points)
    np.testing.assert_allclose(np.linalg.norm(oriented,axis=1),np.linalg.norm(normals,axis=1))
    return {'raster_cases':len(cases)*2,'camera_normal_orientation':True}


def raster_benchmark():
    triangle=np.array([[.02,.02],[.98,.02],[.02,.98]])
    before=time.perf_counter();old=legacy_arrays(triangle,1024,1024);baseline=time.perf_counter()-before
    before=time.perf_counter();new=triangle_arrays(triangle,1024,1024);optimized=time.perf_counter()-before
    np.testing.assert_array_equal(old[0],new[0]);np.testing.assert_array_equal(old[1],new[1])
    np.testing.assert_allclose(old[2],new[2],rtol=1e-10,atol=1e-12)
    return {'pixels':len(new[0]),'baseline_seconds':round(baseline,4),
            'optimized_seconds':round(optimized,4),'speedup':round(baseline/max(optimized,1e-9),2)}


def mesh_benchmark():
    import open3d as o3d
    from geometry import triangulate
    random=np.random.default_rng(951)
    first,second=np.meshgrid(np.linspace(-1.2,1.2,48),np.linspace(.3,3,48))
    a,b=first.ravel(),second.ravel()
    points=np.concatenate([np.column_stack([a,np.full_like(a,1.2),b]),
        np.column_stack([np.full_like(a,-1.2),a,b]),
        np.column_stack([np.full_like(a,1.2),a,b]),
        np.column_stack([a,(b-1.65)*.8,np.full_like(a,3)])])
    points+=random.normal(0,.0003,points.shape)
    frames=[]
    for center in ([0,0,0],[.3,0,.5],[-.3,0,.5]):
        pose=np.eye(4);pose[:3,3]=center;frames.append({'camera_to_world':pose.tolist()})
    results=[]
    for cameras in (None,frames):
        cloud=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
        cloud.colors=o3d.utility.Vector3dVector(np.full_like(points,.7))
        started=time.perf_counter();vertices,faces,_=triangulate(cloud,cameras)
        results.append((time.perf_counter()-started,len(vertices),len(faces)))
    old,new=results
    if new[2]<old[2]*.85:raise ValueError('Camera normal optimization lost too much synthetic room coverage')
    return {'input_points':len(points),'baseline_seconds':round(old[0],4),
        'optimized_seconds':round(new[0],4),'speedup':round(old[0]/max(new[0],1e-9),2),
        'baseline_faces':old[2],'optimized_faces':new[2],
        'limitation':'Synthetic room only; excludes Pi3X inference, queueing and full scene UV preparation.'}


def run_benchmark():
    return {'gpu_used':False,'numerics':verify_numerics(),
            'raster':raster_benchmark(),'meshing':mesh_benchmark()}
