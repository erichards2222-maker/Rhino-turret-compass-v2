"""Qt interface smoke check with the bundled static image and fictional calibration.
Run through Run_UI_Check.cmd on the target machine or in Windows CI.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,time
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from turret_compass_beta import MainWindow


def main():
    app=QApplication([]);w=MainWindow();passed=[]
    try:
        w.timer.stop();passed.append('construct UI')
        w.load_sample();assert w.source_type=='image';passed.append('load supplied offline sample')
        assert w.candidate_ring is not None;passed.append('fit sample ring')
        assert w.last_detection.valid;passed.append('detect sample cone')
        assert 295<w.last_detection.image_angle<301;passed.append('image geometry regression bounds')
        assert not w.crop_preview.pixmap().isNull();passed.append('render diagnostic preview')
        w.session.lock(w.candidate_ring);d=w.analyze_frame();assert d.valid;passed.append('locked ring frame')
        w.hull.setText('075');assert w.session.heading==75;passed.append('heading input wiring')
        # Fictional calibration exercises UI state only, not game truth.
        w.session.forward(d);w.session.right(replace(d,image_angle=(d.image_angle+90)%360))
        w.assume_box.setChecked(True);w.session.observe(d,time.monotonic());w.update_readout()
        assert '075.0' in w.bearing_text.text();passed.append('calibrated readout wiring')
        w.session.observe(replace(d,quality='APEX_CAUTION'),time.monotonic());w.update_readout()
        assert 'CAUTION' in w.bearing_text.text();passed.append('qualified apex warning displayed')
        w.pause_box.setChecked(True);assert w.session.value(time.monotonic())[0] is None;passed.append('pause invalidates readout')
        w.pause_box.setChecked(False);assert not w.session.confirmed;passed.append('resume requires confirmation')
        w.load_sample();assert w.session.zero is None;passed.append('source switch resets calibration')
        w.show();app.processEvents();assert not w.grab().isNull();passed.append('Qt widget painting')
        w.close();assert not w.hotkey.enabled and not w.timer.isActive();passed.append('clean shutdown')
        print('\n'.join('PASS '+p for p in passed))
        print(f'\n{len(passed)} Qt smoke checks passed. This is NOT a live capture/Windows hotkey/Elite test.')
        return 0
    except Exception as exc:
        print('\n'.join('PASS '+p for p in passed));print('FAIL',type(exc).__name__,str(exc));return 1
    finally:w.close();app.quit()

if __name__=='__main__':raise SystemExit(main())
