"""CPU-only array operations. No torch, CUDA, or extra dependencies."""
import math
import numpy as np


def triangle_arrays(corners,width,height):
    """Same pixel-center coverage as triangle_samples, without per-pixel Python."""
    points=[(float(u)*width-.5,float(v)*height-.5) for u,v in corners]
    (ax,ay),(bx,by),(cx,cy)=points
    determinant=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
    left=max(0,math.ceil(min(ax,bx,cx))); right=min(width-1,math.floor(max(ax,bx,cx)))
    top=max(0,math.ceil(min(ay,by,cy))); bottom=min(height-1,math.floor(max(ay,by,cy)))
    if abs(determinant)<1e-10 or left>right or top>bottom:
        return np.empty(0,np.intp),np.empty(0,np.intp),np.empty((0,3),np.float64)
    # For tiny projected faces, allocating several image-sized arrays costs more
    # than the few scalar samples. Avoid the generator/list-conversion overhead.
    if (right-left+1)*(bottom-top+1)<=64:
        positions=[];weights=[]
        for y in range(top,bottom+1):
            for x in range(left,right+1):
                a=((by-cy)*(x-cx)+(cx-bx)*(y-cy))/determinant
                b=((cy-ay)*(x-cx)+(ax-cx)*(y-cy))/determinant
                c=1-a-b
                if min(a,b,c)>=-1e-7:positions.append((x,y));weights.append((a,b,c))
        if not positions:return np.empty(0,np.intp),np.empty(0,np.intp),np.empty((0,3),np.float64)
        xy=np.array(positions,dtype=np.intp)
        return xy[:,0],xy[:,1],np.array(weights)
    x=np.arange(left,right+1,dtype=np.float64)[None,:]
    y=np.arange(top,bottom+1,dtype=np.float64)[:,None]
    a=((by-cy)*(x-cx)+(cx-bx)*(y-cy))/determinant
    b=((cy-ay)*(x-cx)+(ax-cx)*(y-cy))/determinant
    c=1-a-b
    valid=(a>=-1e-7)&(b>=-1e-7)&(c>=-1e-7)
    rows,columns=np.nonzero(valid)
    return columns+left,rows+top,np.column_stack((a[valid],b[valid],c[valid]))


def camera_oriented_normals(points,normals,centers):
    """Orient each observed surface toward its nearest capture camera, in O(N*C)."""
    result=np.asarray(normals).copy()
    centers=np.asarray(centers,dtype=np.float64)
    if centers.ndim!=2 or centers.shape[1]!=3 or not len(centers) or not np.isfinite(centers).all():
        raise ValueError('표면 정렬에 사용할 카메라 위치를 확인해주세요.')
    nearest=np.full(len(points),np.inf)
    sign=np.ones(len(points))
    for center in centers:
        direction=center-points
        distance=np.einsum('ij,ij->i',direction,direction)
        take=distance<nearest
        sign[take]=np.einsum('ij,ij->i',result[take],direction[take])
        nearest[take]=distance[take]
    result[sign<0]*=-1
    return result
