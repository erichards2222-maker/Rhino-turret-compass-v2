"""Deterministic diagnostic rendering, using the SAME fixed pivot as detection."""
import numpy as np
from sector_core import Ring, SectorDetection


def render_preview(image,ring=None,detection=None,show_mask=True,show_geometry=True):
    out=image.astype(float).copy();h,w=image.shape[:2];yy,xx=np.indices((h,w),dtype=float)
    def blend(alpha,color):
        nonlocal out
        a=np.clip(alpha,0,1)[...,None];out=out*(1-a)+np.array(color)*a
    def line(p1,p2,color,width=1.0):
        vx,vy=p2[0]-p1[0],p2[1]-p1[1];den=vx*vx+vy*vy
        if den<=0:return
        t=np.clip(((xx-p1[0])*vx+(yy-p1[1])*vy)/den,0,1)
        dist=np.hypot(xx-(p1[0]+t*vx),yy-(p1[1]+t*vy))
        blend(np.clip(width/2+.6-dist,0,1),color)
    if show_mask and detection is not None and detection.mask is not None:
        blend(detection.mask.astype(float)*.40,(255,30,190))
    if ring is not None and show_geometry:
        rho=np.hypot((xx-ring.cx)/ring.rx,(yy-ring.cy)/ring.ry)
        blend(np.clip(1.0-np.abs(rho-1)*ring.radius,0,1),(255,183,40))
        if detection is not None and detection.valid:
            pivot=(ring.cx,ring.cy)
            line(pivot,ring.point(detection.edge1),(230,240,255),.7)
            line(pivot,ring.point(detection.edge2),(230,240,255),.7)
            line(pivot,ring.point(detection.image_angle),(52,255,110),1.2)
        blend(np.clip(1.8-np.hypot(xx-ring.cx,yy-ring.cy),0,1),(52,255,110))
    return np.clip(out,0,255).astype(np.uint8)
