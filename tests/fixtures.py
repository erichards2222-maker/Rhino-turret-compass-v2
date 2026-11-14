"""Fictional image generator. Independent analytic geometry; no game evidence.
Antialiasing is by supersampling; inputs and outputs are arrays.
"""
import numpy as np


def fixture(angle=300.0, radius=43, width=50, aspect=1.0, offset=(0.,0.),
            damage=False, pale_edges=True, missing_cone=False, missing_ring=False,
            extra_sector=False, apex_offset=(0.,0.), brightness=1.0, noise=0., seed=8,
            scale=4, edge_artifact=0., edge_artifact_left=0.):
    rx,ry=float(radius)*aspect,float(radius)
    w,h=int(2*rx+32),int(2*ry+32)
    cx,cy=(w-1)/2+offset[0],(h-1)/2+offset[1]
    yy,xx=np.indices((h*scale,w*scale),dtype=float)
    x=(xx+.5)/scale-.5;y=(yy+.5)/scale-.5
    image=np.zeros((*xx.shape,3),float)+[70,44,16]
    rr=np.hypot((x-cx)/rx,(y-cy)/ry)
    ring=np.abs(rr-1)*min(rx,ry)<=.9
    if not missing_ring:image[ring]=[236,166,50]
    # Fictional stationary orange vehicle graphic, well inside ring.
    vx=(x-cx)/rx;vy=(y-cy)/ry
    body=(np.abs(vx)<.32)&(np.abs(vy)<.62)
    edge=body & ((np.abs(np.abs(vx)-.30)<.026)|(np.abs(np.abs(vy)-.60)<.026))
    image[edge]=[224,153,53]
    sx=(x-cx-apex_offset[0])/rx;sy=(y-cy-apex_offset[1])/ry
    a=np.rad2deg(np.arctan2(sx,-sy))%360
    diff=(a-angle+180)%360-180
    # Synthetic fading boundary contamination: imprecise tint where the cone
    # overlaps stationary vehicle artwork, without moving its true ring pivot.
    shift=float(edge_artifact)*np.clip((.84-rr)/(.84-.30),0,1)
    left_shift=float(edge_artifact_left)*np.clip((.84-rr)/(.84-.30),0,1)
    inside=(diff >= -width/2-left_shift)&(diff <= width/2+shift)&(rr<=.98)
    if extra_sector:inside |= (np.abs((a-angle-135+180)%360-180)<=width/2)&(rr<=.98)
    if not missing_cone:
        image[inside]=[173,237,244]
        if pale_edges:
            edge_distance=np.abs(np.abs(diff)-width/2)*np.pi/180*np.hypot(x-cx,y-cy)
            image[inside & (edge_distance<=.85)]=[238,249,251]
        if damage:
            # Internal colored occlusion. Boundaries stay observable.
            hole=inside & (np.abs(diff)<width*.23)&(rr>.38)&(rr<.73)
            image[hole]=[96,57,20]
    image=(image.reshape(h,scale,w,scale,3).mean(axis=(1,3))*brightness)
    if noise:
        image += np.random.default_rng(seed).normal(0,noise,image.shape)
    return np.clip(image,0,255).astype(np.uint8),(cx,cy,rx,ry)
