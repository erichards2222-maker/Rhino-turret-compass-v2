import unittest,math
from pathlib import Path
import numpy as np
from sector_core import *
from tests.fixtures import fixture
from preview import render_preview

class MathTests(unittest.TestCase):
    def test_wrap(self):
        self.assertEqual(normalize(-1),359);self.assertEqual(signed_delta(359),-1)
    def test_nonfinite(self):
        for x in (float('nan'),float('inf'),-float('inf')):
            with self.assertRaises(ValueError):normalize(x)
    def test_bearing_clockwise(self):self.assertEqual(turret_bearing(75,190,100,1),(165,90))
    def test_bearing_reverse(self):self.assertEqual(turret_bearing(75,10,100,-1),(165,90))
    def test_wrap_bearing(self):self.assertEqual(turret_bearing(350,20,0,1),(10,20))
    def test_bad_sign(self):
        with self.assertRaises(ValueError):turret_bearing(0,0,0,0)
    def test_error_formula(self):self.assertAlmostEqual(lateral_error(2000,3),104.7077932,places=6)
    def test_buffer_stride(self):
        arr=rgb_array(40,40,bytes(128*40),128);self.assertEqual(arr.shape,(40,40,3))
    def test_buffer_limits(self):
        for w,h,b,s in [(10,40,b'',None),(40,40,b'',None),(900,40,b'',None),(40,40,bytes(4800),110)]:
            with self.assertRaises(ValueError):rgb_array(w,h,b,s)

class DetectorTests(unittest.TestCase):
    def check(self,**kw):
        im,truth=fixture(**kw);f=fit_ring(im);self.assertTrue(f.valid,f.reason)
        return im,f.ring,detect(im,f.ring),truth
    def test_supplied_screenshot(self):
        b=(Path(__file__).parent/'data/screenshot_crop.rgb').read_bytes();im=rgb_array(110,109,b)
        f=fit_ring(im);self.assertTrue(f.valid,f.reason);d=detect(im,f.ring)
        self.assertTrue(d.valid,d.reason)
        # Broad visual/geometric regression bounds, NOT game-bearing ground truth.
        self.assertTrue(52<f.ring.cx<56);self.assertTrue(52<f.ring.cy<56)
        self.assertTrue(295<d.image_angle<301);self.assertGreater(d.pixels,720)
    def test_offcenter_crop(self):
        im,r,d,t=self.check(offset=(8,-6));self.assertTrue(d.valid,d.reason)
        self.assertLess(math.hypot(r.cx-t[0],r.cy-t[1]),.5)
    def test_horizontal_stretch(self):
        im,r,d,t=self.check(aspect=1.25,angle=35);self.assertTrue(d.valid,d.reason)
        self.assertLess(abs(signed_delta(d.image_angle-35)),1.5)
    def test_vertical_stretch(self):
        im,r,d,t=self.check(aspect=.8,angle=145);self.assertTrue(d.valid,d.reason)
        self.assertLess(abs(signed_delta(d.image_angle-145)),1.5)
    def test_partial_internal_color(self):
        _,r,d,_=self.check(damage=True);self.assertTrue(d.valid,d.reason)
        self.assertLess(abs(signed_delta(d.image_angle-300)),1.5)
    def test_dark_but_visible(self):
        _,r,d,_=self.check(brightness=.6);self.assertTrue(d.valid,d.reason)
    def test_noise(self):
        _,r,d,_=self.check(noise=10);self.assertTrue(d.valid,d.reason)
    def test_north_crossing(self):
        for a in (0,.5,359.5,1,359):
            _,r,d,_=self.check(angle=a);self.assertTrue(d.valid,d.reason)
            self.assertLess(abs(signed_delta(d.image_angle-a)),1.5)
    def test_no_cone(self):
        _,_,d,_=self.check(missing_cone=True);self.assertFalse(d.valid)
    def test_multiple_cones(self):
        _,_,d,_=self.check(extra_sector=True);self.assertFalse(d.valid)
    def test_no_ring(self):
        im,_=fixture(missing_ring=True);self.assertFalse(fit_ring(im).valid)
    def test_cone_pivot_mismatch(self):
        _,_,d,_=self.check(apex_offset=(7,3));self.assertFalse(d.valid)
        self.assertIsNone(d.image_angle)
        self.assertEqual(d.quality,'UNAVAILABLE')
    def test_wide_sector(self):
        _,_,d,_=self.check(width=140);self.assertFalse(d.valid)
    def test_thin_sector(self):
        _,_,d,_=self.check(width=5);self.assertFalse(d.valid)
    def test_frozen_center_all_rotations(self):
        im,t=fixture(angle=0);r=fit_ring(im).ring
        for a in range(0,360,15):
            im,_=fixture(angle=a);d=detect(im,r);self.assertTrue(d.valid,d.reason)
            self.assertEqual(d.ring,r);self.assertLess(abs(signed_delta(d.image_angle-a)),1.5)
    def test_ring_shift_rejected(self):
        im,_=fixture();r=fit_ring(im).ring
        moved=np.roll(im,4,axis=1);ok,why,_=verify_ring(moved,r);self.assertFalse(ok,why)
    def test_ring_scaling_rejected(self):
        im,_=fixture();r=fit_ring(im).ring
        # Locked axes deliberately wrong by > tolerance.
        wrong=Ring(r.cx,r.cy,r.rx+4,r.ry+4)
        self.assertFalse(verify_ring(im,wrong)[0])
    def test_clipped_circle(self):
        im,_=fixture();im=im[:,:-25];self.assertFalse(fit_ring(im).valid)
    def test_preview_does_not_modify_raw(self):
        im,r,d,_=self.check();before=im.copy();out=render_preview(im,r,d)
        self.assertTrue(np.array_equal(before,im));self.assertFalse(np.array_equal(out,im))
    def test_preview_starts_at_fixed_pivot(self):
        im,r,d,_=self.check();out=render_preview(im,r,d,False,True)
        pixel=out[round(r.cy),round(r.cx)];self.assertGreater(pixel[1],pixel[0])
    def test_mask_does_not_fill_missing_color(self):
        im,r,d,_=self.check(damage=True)
        # Hole is not painted over merely to make the mask look complete.
        x,y=r.point(300,.55);self.assertFalse(d.mask[round(y),round(x)])
    def test_fit_deterministic(self):
        im,_=fixture();self.assertEqual(fit_ring(im),fit_ring(im))

    def test_minor_apex_artifact_warns_without_moving_pivot(self):
        im,truth=fixture(angle=210,radius=55,edge_artifact=6,edge_artifact_left=2,pale_edges=False)
        fit=fit_ring(im);self.assertTrue(fit.valid,fit.reason)
        d=detect(im,fit.ring)
        self.assertTrue(d.valid,d.reason)
        self.assertEqual(d.quality,'APEX_CAUTION')
        self.assertLess(abs(signed_delta(d.image_angle-210)),2.5)
        self.assertLess(abs(d.radial_axis_drift_deg),1.75)
        self.assertIs(d.ring,fit.ring)

    def test_severe_artifact_still_rejected(self):
        im,_=fixture(angle=210,radius=55,edge_artifact=12,pale_edges=False)
        f=fit_ring(im);d=detect(im,f.ring)
        self.assertFalse(d.valid)
        self.assertIsNone(d.image_angle)
        self.assertEqual(d.quality,'UNAVAILABLE')

    def test_actual_displaced_apex_not_accepted_in_caution_band(self):
        im,_=fixture(angle=210,radius=55,apex_offset=(5,0))
        f=fit_ring(im);d=detect(im,f.ring)
        self.assertFalse(d.valid,d.reason)
        self.assertEqual(d.quality,'UNAVAILABLE')

    def test_displaced_origin_radial_drift_does_not_get_caution(self):
        im,_=fixture(angle=60,radius=55,apex_offset=(4,0))
        f=fit_ring(im);d=detect(im,f.ring)
        self.assertFalse(d.valid)
        self.assertIsNone(d.image_angle)
        self.assertEqual(d.quality,'UNAVAILABLE')
        self.assertGreater(d.radial_axis_drift_deg,1.75)

    def test_clean_pivot_uses_standard_quality(self):
        im,r,d,_=self.check(angle=210,radius=55)
        self.assertTrue(d.valid,d.reason)
        self.assertEqual(d.quality,'STANDARD')
