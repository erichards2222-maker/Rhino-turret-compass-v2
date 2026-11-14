"""Physical image pixels versus screen-relative logical coordinates (no Qt)."""
import math


def logical_crop(rect,physical_size,logical_size):
    x,y,w,h=rect;pw,ph=physical_size;lw,lh=logical_size
    if min(pw,ph,lw,lh,w,h)<=0 or x<0 or y<0 or x+w>pw or y+h>ph:
        raise ValueError('Invalid selection bounds')
    x0=math.floor(x*lw/pw);y0=math.floor(y*lh/ph)
    x1=math.ceil((x+w)*lw/pw);y1=math.ceil((y+h)*lh/ph)
    return x0,y0,x1-x0,y1-y0


def rectangles_intersect(a,b):
    ax,ay,aw,ah=a;bx,by,bw,bh=b
    return ax<bx+bw and bx<ax+aw and ay<by+bh and by<ay+ah
