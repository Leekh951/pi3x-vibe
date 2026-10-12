"""Pixel-center triangle rasterization, also tested without NumPy or a GPU."""
import math


def triangle_samples(corners, width, height):
    """Yield x,y,screen barycentrics; UV/pixel coordinates have a top-left origin."""
    points = [(float(u)*width-.5,float(v)*height-.5) for u,v in corners]
    (ax,ay),(bx,by),(cx,cy) = points
    determinant = (by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
    if abs(determinant) < 1e-10: return
    left = max(0,math.ceil(min(ax,bx,cx))); right = min(width-1,math.floor(max(ax,bx,cx)))
    top = max(0,math.ceil(min(ay,by,cy))); bottom = min(height-1,math.floor(max(ay,by,cy)))
    for y in range(top,bottom+1):
        for x in range(left,right+1):
            a = ((by-cy)*(x-cx)+(cx-bx)*(y-cy))/determinant
            b = ((cy-ay)*(x-cx)+(ax-cx)*(y-cy))/determinant
            c = 1-a-b
            if min(a,b,c) >= -1e-7: yield x,y,(a,b,c)


def perspective_weights(weights, depths):
    """Convert screen weights to surface weights; depth = 1 / sum(w/z)."""
    if any(z <= 0 or not math.isfinite(z) for z in depths):
        raise ValueError('삼각형이 카메라 앞에 있어야 해요.')
    values = [w/z for w,z in zip(weights,depths)]
    total = sum(values)
    return tuple(v/total for v in values),1/total
