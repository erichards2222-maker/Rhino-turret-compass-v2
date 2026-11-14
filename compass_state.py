"""Testable calibration state for screen-derived bearing estimates."""
from dataclasses import dataclass
import math
from sector_core import Ring, SectorDetection, signed_delta, turret_bearing


def parse_heading(text: str) -> float | None:
    try:
        value=float(text.strip().removesuffix('°').strip())
    except (ValueError,TypeError):
        return None
    return value if math.isfinite(value) and 0 <= value < 360 else None


@dataclass
class Session:
    ring: Ring | None = None
    heading: float | None = None
    zero: float | None = None
    sign: int | None = None
    expected_width: float | None = None
    confirmed: bool = False
    paused: bool = False
    detection: SectorDetection | None = None
    frame_time: float | None = None
    source_key: str | None = None
    MAX_FRAME_AGE = 1.0

    def reset_angles(self):
        self.zero=self.sign=self.expected_width=None
        self.confirmed=False
        self.detection=None;self.frame_time=None

    def change_source(self,key):
        self.source_key=key;self.ring=None;self.reset_angles()

    def lock(self,ring):
        self.ring=ring;self.reset_angles()

    def unlock(self):
        self.ring=None;self.reset_angles()

    def set_heading(self,text):
        self.heading=parse_heading(text);self.confirmed=False

    def observe(self,detection,now):
        self.detection=detection;self.frame_time=now

    def forward(self,detection):
        if not self.ring or not detection or not detection.valid:
            raise ValueError('Lock a valid ring and obtain a clear cone first')
        if detection.ring!=self.ring:raise ValueError('Detection uses a different ring')
        self.zero=detection.image_angle;self.expected_width=detection.angular_width
        self.sign=None;self.confirmed=False

    def right(self,detection):
        if self.zero is None or not detection or not detection.valid:
            raise ValueError('Set forward and obtain a clear cone first')
        if detection.ring!=self.ring:raise ValueError('Detection uses a different ring')
        if abs(detection.angular_width-self.expected_width)>8:
            raise ValueError('Cone width changed since forward calibration')
        delta=signed_delta(detection.image_angle-self.zero)
        if not 45<=abs(delta)<=135:
            raise ValueError('Aim about 90 degrees to the Rhino RIGHT; observed change is not plausible')
        self.sign=1 if delta>0 else -1;self.confirmed=False
        return delta

    def value(self,now):
        d=self.detection
        if self.paused:return None,'Paused'
        if self.ring is None:return None,'Fit and lock the ring'
        if self.heading is None:return None,'Enter chassis heading 0 to less than 360'
        if self.zero is None or self.sign is None:return None,'Set forward, then check RIGHT'
        if not self.confirmed:return None,'Confirm stationary/level/aligned conditions'
        if d is None or not d.valid:return None,d.reason if d else 'No valid current frame'
        if d.ring!=self.ring:return None,'Frame/calibration ring mismatch'
        if self.frame_time is None or not 0<=now-self.frame_time<=self.MAX_FRAME_AGE:
            return None,'Frame is stale; capture again'
        if abs(d.angular_width-self.expected_width)>8:
            return None,'Cone width differs from calibration; clear obstruction or recalibrate'
        return turret_bearing(self.heading,d.image_angle,self.zero,self.sign),'Screen-derived estimate'
