"""v0.2 image-array geometry for the Rhino turret indicator.

A fitted orange ring supplies a FIXED origin. Two independently observed cyan
boundaries supply a bisector. A pixel centroid is never used as the bearing.
All numerical quality measures describe image fit, not in-game accuracy.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
import numpy as np

VERSION = '0.2.2-beta.1'


def normalize(degrees: float) -> float:
    if not math.isfinite(degrees):
        raise ValueError('Angle must be finite')
    return degrees % 360.0


def signed_delta(degrees: float) -> float:
    return (normalize(degrees) + 180.0) % 360.0 - 180.0


def turret_bearing(chassis_heading: float, image_angle: float,
                   forward_zero: float, direction_sign: int) -> tuple[float, float]:
    if direction_sign not in (-1, 1):
        raise ValueError('Rotation sign must be -1 or +1')
    relative = direction_sign * signed_delta(image_angle - forward_zero)
    return normalize(chassis_heading + relative), relative


def lateral_error(range_m: float, bearing_error_degrees: float) -> float:
    if not math.isfinite(range_m) or not 0 <= range_m <= 20000:
        raise ValueError('Invalid range')
    return 2.0 * range_m * abs(math.sin(math.radians(signed_delta(bearing_error_degrees) / 2)))


@dataclass(frozen=True)
class Ring:
    cx: float
    cy: float
    rx: float
    ry: float
    support: float = 0.0
    residual_px: float = 0.0
    model: str = 'axis-aligned ellipse'

    @property
    def radius(self) -> float:
        return min(self.rx, self.ry)

    def point(self, angle: float, fraction: float = 1.0) -> tuple[float, float]:
        a = math.radians(angle)
        return (self.cx + self.rx * fraction * math.sin(a),
                self.cy - self.ry * fraction * math.cos(a))


@dataclass(frozen=True)
class RingFit:
    valid: bool
    ring: Ring | None
    reason: str


@dataclass
class SectorDetection:
    valid: bool
    image_angle: float | None = None
    pixels: int = 0
    angular_width: float | None = None
    reason: str = ''
    ring: Ring | None = None
    edge1: float | None = None
    edge2: float | None = None
    edge_spread_deg: float | None = None
    occupancy_angle: float | None = None
    disagreement_deg: float | None = None
    apex_offset_px: float | None = None
    apex_xy: tuple[float,float] | None = None
    support_rows: int = 0
    quality: str = 'UNAVAILABLE'  # STANDARD / APEX_CAUTION / UNAVAILABLE
    radial_axis_drift_deg: float | None = None
    mask: np.ndarray | None = field(default=None, repr=False)
    edge_points1: np.ndarray | None = field(default=None, repr=False)
    edge_points2: np.ndarray | None = field(default=None, repr=False)


def rgb_array(width: int, height: int, rgb: bytes, stride: int | None = None) -> np.ndarray:
    if not isinstance(width, int) or not isinstance(height, int) or not (40 <= width <= 800 and 40 <= height <= 800):
        raise ValueError('Select only the full round indicator, 40–800 pixels per side')
    stride = width * 3 if stride is None else stride
    if not isinstance(stride, int) or stride < width * 3 or len(rgb) < stride * height:
        raise ValueError('Invalid RGB buffer dimensions')
    return np.frombuffer(rgb, dtype=np.uint8, count=stride * height).reshape(height, stride)[:, :width * 3].reshape(height, width, 3).copy()


def color_maps(image: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Broad cyan evidence with brightness/contrast safeguards; orange excluded.

    Pale pixels need less absolute contrast than the v0.1 hard threshold.
    The diagnostic mask contains observed classified pixels, NOT a painted wedge.
    """
    c = image.astype(float)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    orange_base = (r > 70) & (g > 40) & (r - g > 16) & (g - b > 14)
    # Reject the brown panel itself: use the bright orange ridge, not all orange pixels.
    strength = r + g
    threshold = max(200.0, float(np.percentile(strength[orange_base], 72))) if orange_base.any() else 500.0
    orange = orange_base & (strength >= threshold)
    diff = np.minimum(g - r, b - r)
    score = np.clip((diff - 3.0) / 18.0, 0, 1)
    score *= np.clip((np.minimum(g, b) - 55) / 65, 0, 1)
    score *= np.clip((b - g + 30) / 20, 0, 1)
    # The screenshot's antialiased rim is pale/near-white, not saturated cyan.
    # Require brightness and blue/green balance; orange vehicle lines fail this.
    pale = np.clip((np.minimum(np.minimum(r,g),b)-155)/55,0,1)
    pale *= np.clip((np.minimum(g-r,b-r)+12)/12,0,1)
    pale *= np.clip((b-g+30)/20,0,1)
    score = np.maximum(score,pale)
    mask = ((diff >= 5) & (g >= 85) & (b >= 85) & (b >= g - 22)) | (pale >= .20)
    return orange, score, mask


def sample(image: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Bilinear samples, outside image is zero. Coordinates are pixel centers."""
    h, w = image.shape
    ok = (x >= 0) & (x <= w - 1) & (y >= 0) & (y <= h - 1)
    x = np.clip(x, 0, w - 1); y = np.clip(y, 0, h - 1)
    x0 = x.astype(int); y0 = y.astype(int)
    x1 = np.minimum(x0 + 1, w - 1); y1 = np.minimum(y0 + 1, h - 1)
    dx = x - x0; dy = y - y0
    return ((1-dx)*(1-dy)*image[y0,x0] + dx*(1-dy)*image[y0,x1]
            + (1-dx)*dy*image[y1,x0] + dx*dy*image[y1,x1]) * ok


def _ring_from_points(points: np.ndarray) -> Ring | None:
    # Normalize for conditioning; solve x² + B*y² + C*x + D*y + E = 0.
    origin = points.mean(axis=0)
    scale = max(1.0, float(np.std(points)))
    p = (points - origin) / scale
    x, y = p[:,0], p[:,1]
    try:
        b,c,d,e = np.linalg.lstsq(np.column_stack([y*y,x,y,np.ones(len(x))]), -x*x, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    if b <= 0:
        return None
    cx, cy = -c/2, -d/(2*b)
    rr = cx*cx + b*cy*cy - e
    if rr <= 0:
        return None
    return Ring(float(origin[0]+scale*cx), float(origin[1]+scale*cy),
                float(scale*np.sqrt(rr)), float(scale*np.sqrt(rr/b)))


def _plausible(ring: Ring | None, w: int, h: int) -> bool:
    if ring is None or not all(math.isfinite(x) for x in (ring.cx,ring.cy,ring.rx,ring.ry)):
        return False
    return (ring.radius >= 18 and 0.65 <= ring.rx/ring.ry <= 1.54 and
            .22*w <= ring.rx <= .50*w and .22*h <= ring.ry <= .50*h and
            ring.cx-ring.rx >= 1 and ring.cy-ring.ry >= 1 and
            ring.cx+ring.rx < w-1 and ring.cy+ring.ry < h-1)


def _metrics(ring: Ring, points: np.ndarray, threshold: float = 1.65):
    x = (points[:,0]-ring.cx)/ring.rx; y = (points[:,1]-ring.cy)/ring.ry
    residual = np.abs(np.sqrt(x*x+y*y)-1)*ring.radius
    inliers = residual < threshold
    if inliers.sum() < 20:
        return 0.0, 99.0, inliers
    a = np.mod(np.arctan2(x[inliers], -y[inliers]), 2*np.pi)
    counts = np.bincount((a*72/(2*np.pi)).astype(int), minlength=72)
    support = np.count_nonzero(counts >= 1)/72
    return support, float(np.median(residual[inliers])), inliers


def fit_ring(image: np.ndarray, hint: Ring | None = None) -> RingFit:
    """Robust orange ellipse fitting. A cyan sector cannot move the fitted origin.

    Full fit is only for source selection/recalibration. Runtime uses verify_ring
    against this frozen geometry instead of refitting a cone-dependent origin.
    Ellipse correction handles axis-aligned resize, NOT arbitrary perspective.
    """
    h,w = image.shape[:2]
    orange,_,_ = color_maps(image)
    border_count = int(orange[:2,:].sum()+orange[-2:,:].sum()+orange[:, :2].sum()+orange[:, -2:].sum())
    if border_count >= 8:
        return RingFit(False,None,'Orange ring/graphics touch crop edge; include the complete ring with margin')
    ys,xs = np.nonzero(orange)
    if len(xs) < 50:
        return RingFit(False,None,'Not enough orange perimeter; include the complete ring')
    points = np.column_stack([xs,ys]).astype(float)
    rng = np.random.default_rng(2042)
    if len(points) > 2500:
        points = points[rng.choice(len(points),2500,replace=False)]
    best = None; best_score = -1.0
    # Deterministic RANSAC: interior vehicle lines are outliers.
    candidates = [hint] if hint else []
    candidates.append(_ring_from_points(points))
    for _ in range(340):
        candidates.append(_ring_from_points(points[rng.choice(len(points),4,replace=False)]))
    for ring in candidates:
        if not _plausible(ring,w,h):
            continue
        support, residual, inliers = _metrics(ring,points)
        score = support*100 + min(float(inliers.sum())/len(points), .6)*8 - residual
        if score > best_score:
            best_score=score; best=ring
    if best is None:
        return RingFit(False,None,'No complete plausible ring; crop only this gauge with a little margin')
    # Refine near-ring pixels; retain robust residual rejection.
    for _ in range(5):
        _,_,keep = _metrics(best,points,1.8)
        refined = _ring_from_points(points[keep])
        if not _plausible(refined,w,h):
            break
        best=refined
    support,residual,_ = _metrics(best,points,1.8)
    best=Ring(best.cx,best.cy,best.rx,best.ry,support,residual)
    if support < .65:
        return RingFit(False,None,'Ring fit lacks distributed perimeter support; crop/lighting may be wrong')
    return RingFit(True,best,'Ring fitted; pivot must be visually confirmed before locking')


def verify_ring(image: np.ndarray, ring: Ring) -> tuple[bool,str,float]:
    """Check frozen ring against current pixels; never re-center automatically."""
    h,w=image.shape[:2]
    if not _plausible(ring,w,h):
        return False,'Locked ring no longer fits capture dimensions',0.0
    orange,_,_=color_maps(image)
    angles=np.arange(0,360,3)*np.pi/180
    # Locate ring ridge separately on every ray; reject coherent radial drift.
    offsets=np.linspace(-3.5,3.5,29)
    x=ring.cx+(ring.rx+offsets[:,None])*np.sin(angles)
    y=ring.cy-(ring.ry+offsets[:,None])*np.cos(angles)
    values=sample(orange.astype(float),x,y)
    evidence=values.max(axis=0)>.50
    if evidence.mean()<.62:
        return False,'Ring obscured or moved: reselect/relock after restoring the HUD',float(evidence.mean())
    # average matching ridge offsets, not one arbitrarily selected thick-ring edge
    weights=np.where(values>.45,values,0)
    delta=np.sum(weights*offsets[:,None],axis=0)/np.maximum(weights.sum(axis=0),1e-6)
    a=np.column_stack([np.sin(angles[evidence]),-np.cos(angles[evidence]),np.ones(evidence.sum())])
    fit=np.linalg.lstsq(a,delta[evidence],rcond=None)[0]
    shift=math.hypot(float(fit[0]),float(fit[1]))
    if shift>1.5 or abs(fit[2])>1.5:
        return False,'HUD ring moved/scaled: calibration invalidated; reselect and relock',float(evidence.mean())
    return True,'Locked ring matches',float(evidence.mean())


def _runs(mask: np.ndarray) -> list[tuple[int,int]]:
    """Contiguous true runs on a circular grid, start index and count."""
    n=len(mask)
    if mask.all():return [(0,n)]
    if not mask.any():return []
    start=int(np.flatnonzero(~mask)[0]); a=np.roll(mask,-start)
    edges=np.diff(np.r_[False,a,False].astype(int)); ss=np.flatnonzero(edges==1); ee=np.flatnonzero(edges==-1)
    return [((int(s)+start)%n,int(e-s)) for s,e in zip(ss,ee)]


def _smooth(a: np.ndarray) -> np.ndarray:
    return (np.roll(a,2)+2*np.roll(a,1)+3*a+2*np.roll(a,-1)+np.roll(a,-2))/9


def _crossing(row: np.ndarray, index: int, direction: int, level: float) -> float:
    n=len(row); inside=index%n; outside=(inside+direction)%n
    a,b=row[inside],row[outside]
    frac=(a-level)/(a-b) if abs(a-b)>1e-9 else .5
    return (inside + direction*float(np.clip(frac,0,1))) % n


def _line_fit(points: np.ndarray) -> tuple[np.ndarray,np.ndarray,float]:
    center=points.mean(axis=0)
    for _ in range(3):
        _,_,v=np.linalg.svd(points-center,full_matrices=False)
        vector=v[0]; normal=np.array([-vector[1],vector[0]])
        residual=np.abs((points-center)@normal)
        keep=residual<=max(.012,float(np.median(residual))*3.5)
        if keep.sum()<6:break
        points=points[keep];center=points.mean(axis=0)
    _,_,v=np.linalg.svd(points-center,full_matrices=False)
    vector=v[0]
    if np.dot(vector,center)<0:vector=-vector
    normal=np.array([-vector[1],vector[0]])
    return center,vector,float(np.sqrt(np.mean(((points-center)@normal)**2)))


def detect(image: np.ndarray, ring: Ring, verify: bool = True) -> SectorDetection:
    d=SectorDetection(False,ring=ring)
    def reject(reason):
        d.reason=reason; d.valid=False; d.image_angle=None;d.quality='UNAVAILABLE';return d
    if image.ndim!=3 or image.shape[2]!=3:
        return reject('Expected an RGB image')
    if verify:
        ok,reason,_=verify_ring(image,ring)
        if not ok:return reject(reason)
    _,score,mask=color_maps(image)
    yy,xx=np.indices(mask.shape)
    rho=np.hypot((xx-ring.cx)/ring.rx,(yy-ring.cy)/ring.ry)
    d.mask=mask & (rho<=1.015)
    d.pixels=int(d.mask.sum())
    if d.pixels < max(30,ring.radius):return reject('Too few cyan pixels')
    n=720;angles=np.arange(n)*2*np.pi/n
    radii=np.linspace(.30,.84,30)
    x=ring.cx+ring.rx*radii[:,None]*np.sin(angles)
    y=ring.cy-ring.ry*radii[:,None]*np.cos(angles)
    polar=sample(score,x,y)
    # Radial upper quartile tolerates internal occlusions but requires repeated support.
    occupancy=_smooth(np.quantile(polar,.75,axis=0))
    peak=float(np.percentile(occupancy,98))
    if peak < .24:return reject('Cone color too weak; check HUD brightness/crop')
    threshold=max(.16,peak*.48)
    occ_runs=_runs(occupancy>threshold)
    major=[r for r in occ_runs if r[1]>=12]
    if len(major)!=1:return reject('Missing or multiple cyan sectors')
    start,length=major[0]
    if not 15<=length*.5<=105:return reject('Sector width is implausible')
    left=_crossing(occupancy,start,-1,threshold)*.5
    right=_crossing(occupancy,(start+length-1)%n,1,threshold)*.5
    reference=normalize(left+((right-left)%360)/2)
    d.occupancy_angle=reference
    boundaries=[]
    for ri,row in zip(radii,polar):
        row=_smooth(row);level=max(.16,float(np.percentile(row,98))*.48)
        runs=_runs(row>level)
        # Locate both OUTER transitions near independently found sector sides.
        # Internal missing-color patches are not interpreted as new outer edges.
        starts=[_crossing(row,s,-1,level)*.5 for s,l in runs if l>=4]
        ends=[_crossing(row,(s+l-1)%n,1,level)*.5 for s,l in runs if l>=4]
        starts=[a for a in starts if abs(signed_delta(a-left))<10]
        ends=[b for b in ends if abs(signed_delta(b-right))<10]
        if not starts or not ends:continue
        a=min(starts,key=lambda a:abs(signed_delta(a-left)))
        b=min(ends,key=lambda b:abs(signed_delta(b-right)))
        if not 15 <= (b-a)%360 <= 105:continue
        boundaries.append((ri,a,b))
    d.support_rows=len(boundaries)
    if len(boundaries)<18:return reject('Both cone edges are not sufficiently visible')
    data=np.array(boundaries)
    if data[:,0].max()-data[:,0].min()<.40:return reject('Cone edges lack radial extent')
    # Fit the TWO straight boundaries in rectified coordinates, independently
    # of the ring center. The free apex is a diagnostic, never a moving origin.
    p1=np.column_stack([data[:,0]*np.sin(np.deg2rad(data[:,1])), -data[:,0]*np.cos(np.deg2rad(data[:,1]))])
    p2=np.column_stack([data[:,0]*np.sin(np.deg2rad(data[:,2])), -data[:,0]*np.cos(np.deg2rad(data[:,2]))])
    c1,v1,res1=_line_fit(p1);c2,v2,res2=_line_fit(p2)
    try:
        t=np.linalg.solve(np.column_stack([v1,-v2]),c2-c1)
    except np.linalg.LinAlgError:return reject('Cone edges do not define a unique apex')
    apex=c1+t[0]*v1
    d.apex_offset_px=float(np.hypot(apex[0]*ring.rx,apex[1]*ring.ry))
    d.apex_xy=(float(ring.cx+apex[0]*ring.rx),float(ring.cy+apex[1]*ring.ry))
    d.edge_points1=p1;d.edge_points2=p2
    # Do not reject on free-apex displacement before assessing independently
    # anchored edge angles. Vehicle HUD artwork can distort one sampled edge.
    # The locked ring remains the ONLY origin used for any bearing.
    fit_residual_px=max(res1,res2)*ring.radius
    if fit_residual_px>1.0:return reject('Cone sides are not straight enough')
    # Angular direction uses each boundary relative to the LOCKED origin.
    # Robust median over several radii avoids a brightness-weighted centroid.
    e1=normalize(reference+float(np.median([signed_delta(a-reference) for a in data[:,1]])))
    e2=normalize(reference+float(np.median([signed_delta(a-reference) for a in data[:,2]])))
    width=(e2-e1)%360
    if not 15<=width<=105:return reject('Invalid edge order/width')
    axis=normalize(e1+width/2)
    d.edge1=e1;d.edge2=e2;d.angular_width=width
    d.edge_points1=p1;d.edge_points2=p2
    deviations=np.r_[[abs(signed_delta(a-e1)) for a in data[:,1]], [abs(signed_delta(b-e2)) for b in data[:,2]]]
    d.edge_spread_deg=float(np.percentile(deviations,90))
    d.disagreement_deg=abs(signed_delta(axis-reference))
    # Compare independent centerline estimates at inner and outer sampling
    # radii. A truly displaced physical wedge tends to drift with radius; the
    # free-apex offset alone cannot distinguish that from HUD edge artifacts.
    row_axes=np.array([normalize(a+((b-a)%360)/2) for a,b in data[:,1:3]])
    relative_rows=np.array([signed_delta(x-reference) for x in row_axes])
    d.radial_axis_drift_deg=float(abs(np.median(relative_rows[-10:])-
                                      np.median(relative_rows[:10])))
    if d.edge_spread_deg>4 or d.disagreement_deg>2.5:
        return reject('Cone edges disagree across radii; restore a clear view')
    if d.radial_axis_drift_deg>2.75:
        return reject('Cone centerline drifts across radii; restore a clear view')

    strict_apex=max(2.1,ring.radius*.065)
    if d.apex_offset_px>strict_apex:
        # Allow a bounded contour artifact only when radial checks agree.
        # Tolerance by itself is NOT sufficient: require multiple independent
        # checks and clearly distinguish the estimate from standard readings.
        caution_apex=max(4.8,ring.radius*.12)
        if (d.apex_offset_px>caution_apex or d.support_rows<27 or
            d.edge_spread_deg>2.8 or d.disagreement_deg>1.0 or
            d.radial_axis_drift_deg>1.75 or fit_residual_px>.65):
            return reject('Apex-fit discrepancy exceeds corroborated tolerance; bearing unavailable')
        d.quality='APEX_CAUTION'
        d.reason='Apex-fit caution: edges agree but visual apex is displaced; verify bearing'
    else:
        d.quality='STANDARD'
        d.reason='Two-edge bisector supported; gameplay accuracy unvalidated'
    d.valid=True;d.image_angle=axis
    return d
