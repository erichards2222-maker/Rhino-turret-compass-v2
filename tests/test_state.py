import unittest
from dataclasses import replace
from sector_core import Ring,SectorDetection
from compass_state import *
from capture_geometry import *

class StateTests(unittest.TestCase):
    def setUp(self):
        self.r=Ring(50,50,43,43)
        self.d=SectorDetection(True,10,400,50,'test',self.r)
        self.s=Session();self.s.change_source('live');self.s.lock(self.r);self.s.set_heading('075')
    def ready(self):
        self.s.forward(self.d);self.s.right(replace(self.d,image_angle=100));self.s.confirmed=True
        self.s.observe(replace(self.d,image_angle=190),10)
    def test_unset(self):self.assertIsNone(self.s.value(10)[0])
    def test_success(self):self.ready();self.assertEqual(self.s.value(10)[0],(255,-180))
    def test_stale(self):self.ready();self.assertIsNone(self.s.value(11.01)[0])
    def test_time_reversal(self):self.ready();self.assertIsNone(self.s.value(9)[0])
    def test_paused(self):self.ready();self.s.paused=True;self.assertIsNone(self.s.value(10)[0])
    def test_heading_change_requires_confirmation(self):
        self.ready();self.s.set_heading('90');self.assertIsNone(self.s.value(10)[0])
    def test_source_reset(self):self.ready();self.s.change_source('image');self.assertIsNone(self.s.ring);self.assertIsNone(self.s.zero)
    def test_relock_resets_angles(self):self.ready();self.s.lock(self.r);self.assertIsNone(self.s.zero)
    def test_unlock(self):self.ready();self.s.unlock();self.assertIsNone(self.s.value(10)[0])
    def test_invalid_detection(self):self.ready();self.s.observe(SectorDetection(False,reason='missing'),10);self.assertIsNone(self.s.value(10)[0])
    def test_cone_width_change(self):self.ready();self.s.observe(replace(self.d,angular_width=65),10);self.assertIsNone(self.s.value(10)[0])
    def test_different_ring(self):self.ready();self.s.observe(replace(self.d,ring=Ring(52,50,43,43)),10);self.assertIsNone(self.s.value(10)[0])
    def test_bad_right(self):
        self.s.forward(self.d)
        with self.assertRaises(ValueError):self.s.right(replace(self.d,image_angle=30))
    def test_bad_forward(self):
        self.s.unlock()
        with self.assertRaises(ValueError):self.s.forward(self.d)
    def test_reverse_sign(self):
        self.s.forward(replace(self.d,image_angle=100));self.s.right(self.d);self.assertEqual(self.s.sign,-1)
    def test_heading_parse(self):
        self.assertEqual(parse_heading(' 075° '),75)
        for v in ('nan','inf','-1','360','','abc'):self.assertIsNone(parse_heading(v))
    def test_move_invalidates(self):self.ready();self.s.reset_angles();self.assertIsNone(self.s.value(10)[0])

class CoordinateTests(unittest.TestCase):
    def test_dpi_100(self):self.assertEqual(logical_crop((100,100,120,120),(1920,1080),(1920,1080)),(100,100,120,120))
    def test_dpi_150(self):self.assertEqual(logical_crop((150,150,180,180),(2880,1620),(1920,1080)),(100,100,120,120))
    def test_dpi_200(self):self.assertEqual(logical_crop((200,200,240,240),(3840,2160),(1920,1080)),(100,100,120,120))
    def test_fractional_encloses(self):self.assertEqual(logical_crop((151,151,179,179),(2880,1620),(1920,1080)),(100,100,120,120))
    def test_outside(self):
        with self.assertRaises(ValueError):logical_crop((-1,0,100,100),(1920,1080),(1920,1080))
    def test_overlap(self):self.assertTrue(rectangles_intersect((10,10,50,50),(40,40,30,30)))
    def test_negative_monitor_origin(self):self.assertFalse(rectangles_intersect((-1920,0,200,200),(0,0,200,200)))
