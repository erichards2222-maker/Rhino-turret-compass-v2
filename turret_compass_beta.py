"""RHINO Turret Compass v0.2.2-beta.2: a local HUD-image bearing estimator.

Inputs are a user-selected screen rectangle or an image, plus manual calibration.
Outputs are a floating readout, an explicit clipboard copy, and optional diagnostics.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import math
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone
import numpy as np

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QLineEdit, QScrollArea,
    QVBoxLayout, QWidget)

from sector_core import VERSION, SectorDetection, rgb_array, fit_ring, detect, verify_ring
from compass_state import Session
from capture_geometry import logical_crop, rectangles_intersect
from preview import render_preview
from diagnostics import write_diagnostic


class RegionCanvas(QWidget):
    """Display one captured frame; drag around the turret circle (not the full panel)."""
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.image = QPixmap(pixmap)
        self.image.setDevicePixelRatio(1.0)
        self.begin = None
        self.end = None
        self.setMinimumSize(680, 450)
        self.setMouseTracking(True)
        self.setToolTip("Drag around the whole golden CIRCLE with 5–15 pixels of margin, then click Use selection")

    def viewport(self) -> QRectF:
        size = self.image.size()
        scale = min(self.width() / size.width(), self.height() / size.height())
        w, h = size.width() * scale, size.height() * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def to_source(self, pos: QPointF) -> QPointF | None:
        bounds = self.viewport()
        if bounds.width() <= 0 or bounds.height() <= 0 or not bounds.contains(pos):
            return None
        return QPointF((pos.x() - bounds.x()) * self.image.width() / bounds.width(),
                       (pos.y() - bounds.y()) * self.image.height() / bounds.height())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.to_source(event.position())
            if p is not None:
                self.begin = p
                self.end = p
                self.update()

    def mouseMoveEvent(self, event):
        if self.begin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.end = self.to_source(event.position()) or self.end
            self.update()

    def mouseReleaseEvent(self, event):
        if self.begin is not None and event.button() == Qt.MouseButton.LeftButton:
            self.end = self.to_source(event.position()) or self.end
            self.update()

    def selected_rect(self) -> QRectF | None:
        if self.begin is None or self.end is None:
            return None
        r = QRectF(self.begin, self.end).normalized()
        return r if r.width() >= 20 and r.height() >= 20 else None

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#12171c"))
        target = self.viewport()
        p.drawPixmap(target, self.image, QRectF(self.image.rect()))
        rect = self.selected_rect()
        if rect is not None:
            sx, sy = target.width()/self.image.width(), target.height()/self.image.height()
            dr = QRectF(target.x()+rect.x()*sx, target.y()+rect.y()*sy,
                        rect.width()*sx, rect.height()*sy)
            p.setPen(QPen(QColor("#31edf4"), 2))
            p.setBrush(QColor(0, 200, 255, 25))
            p.drawRect(dr)
        p.end()


class RegionDialog(QDialog):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select turret direction indicator")
        self.canvas = RegionCanvas(pixmap)
        self.message = QLabel("Drag around the rightmost ROUND Rhino silhouette and cyan sector, with a small margin.\n"
                              "Exclude the middle shield diamond and the outer SYSTEMS border.")
        self.message.setWordWrap(True)
        use = QPushButton("Use selected region")
        use.clicked.connect(self._apply)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(use)
        row.addWidget(cancel)
        layout = QVBoxLayout(self)
        layout.addWidget(self.message)
        layout.addWidget(self.canvas, 1)
        layout.addLayout(row)
        self.resize(1100, 780)

    def _apply(self):
        rect = self.canvas.selected_rect()
        if rect is None:
            QMessageBox.warning(self, "Select the indicator", "Drag a region covering the whole turret direction circle.")
            return
        self.accept()


class BearingOverlay(QWidget):
    """Optional small transparent, click-through readout; never covers the selection ROI intentionally."""
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.WindowTransparentForInput |
                         Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.line1 = "TURRET —"
        self.line2 = "UNVALIDATED"
        self.resize(370, 85)

    def set_lines(self, line1: str, line2: str):
        if (line1, line2) != (self.line1, self.line2):
            self.line1, self.line2 = line1, line2
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(10, 23, 29, 225))
        p.setPen(QColor(66, 189, 202))
        p.drawRoundedRect(self.rect().adjusted(1,1,-1,-1), 8, 8)
        p.setPen(QColor("#dcfafa"))
        f = QFont("Consolas", 21)
        f.setBold(True)
        p.setFont(f)
        p.drawText(14, 38, self.line1)
        p.setPen(QColor("#e9ce91"))
        p.setFont(QFont("Consolas", 10))
        p.drawText(14, 65, self.line2)
        p.end()


class OptionalHotkey:
    """One opt-in Windows RegisterHotKey for the bearing-copy command.

    Installed only on request, and always unregistered at shutdown.
    """
    def __init__(self, callback):
        self.callback = callback
        self.enabled = False
        self.user32 = None
        self.hotkey_id = 0x5248
        self.filter = None

    def enable(self) -> tuple[bool, str]:
        if self.enabled:
            return True, "Already enabled"
        if sys.platform != "win32":
            return False, "Global hotkey works only on Windows"
        try:
            from PySide6.QtCore import QAbstractNativeEventFilter
            outer = self
            class HotkeyEvents(QAbstractNativeEventFilter):
                def nativeEventFilter(self, event_type, message):
                    if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                        msg = wintypes.MSG.from_address(int(message))
                        if msg.message == 0x0312 and msg.wParam == outer.hotkey_id:
                            QTimer.singleShot(0, outer.callback)
                            return True, 0
                    return False, 0
            self.user32 = ctypes.WinDLL("user32", use_last_error=True)
            self.user32.RegisterHotKey.argtypes=(wintypes.HWND,ctypes.c_int,wintypes.UINT,wintypes.UINT)
            self.user32.RegisterHotKey.restype=wintypes.BOOL
            self.user32.UnregisterHotKey.argtypes=(wintypes.HWND,ctypes.c_int)
            self.user32.UnregisterHotKey.restype=wintypes.BOOL
            MOD_CONTROL = 0x0002; MOD_ALT = 0x0001; MOD_NOREPEAT = 0x4000
            ok = self.user32.RegisterHotKey(None, self.hotkey_id,
                                           MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("B"))
            if not ok:
                return False, "Ctrl+Alt+B is unavailable (another app may use it)"
            self.enabled = True  # set before installing, so exceptions reliably unregister the key
            self.filter = HotkeyEvents()
            QApplication.instance().installNativeEventFilter(self.filter)
            return True, "Ctrl+Alt+B enabled (global); use only while the turret is stationary"
        except Exception as exc:
            self.disable()
            return False, f"Could not register hotkey: {type(exc).__name__}"

    def disable(self):
        if self.enabled and self.user32:
            self.user32.UnregisterHotKey(None, self.hotkey_id)
        self.enabled = False
        if self.filter:
            QApplication.instance().removeNativeEventFilter(self.filter)
        self.filter = None


class GameFocus:
    """Recognize the foreground game window by its Windows class name."""
    def __init__(self):
        self.u=None
        if sys.platform=='win32':
            self.u=ctypes.WinDLL('user32',use_last_error=True)
            self.u.GetForegroundWindow.restype=wintypes.HWND
            self.u.GetClassNameW.argtypes=(wintypes.HWND,wintypes.LPWSTR,ctypes.c_int)
    def elite(self):
        if self.u is None:return False
        handle=self.u.GetForegroundWindow();buf=ctypes.create_unicode_buffer(256)
        self.u.GetClassNameW(handle,buf,256)
        return buf.value=='FrontierDevelopmentsAppWinClass'


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('RHINO Turret Compass v0.2.2-beta.2 — experimental, screen-only')
        self.session=Session();self.source_type=None;self.live_screen=None
        self.crop_logical=None;self.screen_signature=None;self.demo_crop=None
        self.last_frame=None;self.last_array=None;self.last_detection=None;self.candidate_ring=None
        self.busy=False;self.focus=GameFocus();self.overlay=BearingOverlay()
        self.hotkey=OptionalHotkey(self.hotkey_copy)
        self.screen_box=QComboBox()
        for i,screen in enumerate(QApplication.screens()):
            g=screen.geometry();self.screen_box.addItem(f'Screen {i+1}: {screen.name()} ({g.width()} x {g.height()})',screen)
        self.source_note=QLabel('No source. Start with Open supplied sample, or choose a LIVE region.');self.source_note.setWordWrap(True)
        self.crop_preview=QLabel('No image');self.crop_preview.setFixedSize(280,280)
        self.crop_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.crop_preview.setStyleSheet('background:#11191d;border:1px solid #597079;')
        self.image_label=QLabel('IMAGE ANGLE: —');self.image_label.setStyleSheet('font-size:19px;font-weight:bold;')
        self.diagnostic=QLabel('No image evaluated');self.diagnostic.setWordWrap(True)
        self.ring_note=QLabel('Ring not fitted');self.ring_note.setWordWrap(True)
        self.mask_box=QCheckBox('Show detected pixels (magenta)');self.mask_box.setChecked(True)
        self.geometry_box=QCheckBox('Show ring, pivot, two edges and centerline');self.geometry_box.setChecked(True)
        self.mask_box.toggled.connect(self.refresh_preview);self.geometry_box.toggled.connect(self.refresh_preview)
        self.hull=QLineEdit();self.hull.setPlaceholderText('e.g. 075 — from the chassis compass before turret view')
        self.hull.textChanged.connect(self.heading_changed)
        self.zero_label=QLabel('Forward: UNSET');self.sign_label=QLabel('Right-turn sign: UNCHECKED')
        self.assume_box=QCheckBox('Confirmed: Rhino stationary, approximately level; turret forward and RIGHT checks correct')
        self.assume_box.toggled.connect(self.assumption_changed)
        self.bearing_text=QLabel('TURRET: UNAVAILABLE');self.bearing_text.setStyleSheet('font-size:23px;font-weight:bold;')
        self.bearing_desc=QLabel('Screen-derived estimate. Real-game error has NOT been established.');self.bearing_desc.setWordWrap(True)
        self.mark_note=QLabel('Nothing copied');self.mark_note.setWordWrap(True)
        self.float_box=QCheckBox('Show floating readout (live only)');self.float_box.toggled.connect(self.update_readout)
        self.hotkey_box=QCheckBox('Enable Ctrl+Alt+B in Elite only (off by default)')
        self.hotkey_box.toggled.connect(self.sync_hotkey)
        self.pause_box=QCheckBox('PAUSE screen capture');self.pause_box.toggled.connect(self.pause_changed)
        self.status=QLabel('Local HUD-image measurement. Save diagnostic images only when requested.');self.status.setWordWrap(True)
        root=QWidget();layout=QVBoxLayout(root)
        intro=QLabel('Experimental beta. Keep this window away from the captured HUD region.\n'
                     'The green line is the CONE BISECTOR, not a colored-pixel centroid.')
        intro.setWordWrap(True);layout.addWidget(intro)
        def button(text,callback):
            b=QPushButton(text);b.clicked.connect(callback);return b
        group=QGroupBox('1 · Source');box=QVBoxLayout(group);box.addWidget(self.screen_box)
        row=QHBoxLayout();row.addWidget(button('Choose LIVE region',self.begin_live_selection));row.addWidget(button('Inspect image file',self.load_test_image));row.addWidget(button('Open supplied sample',self.load_sample));box.addLayout(row);box.addWidget(self.source_note);layout.addWidget(group)
        group=QGroupBox('2 · Fixed ring and cone');box=QVBoxLayout(group);row=QHBoxLayout();row.addWidget(self.crop_preview)
        info=QVBoxLayout();info.addWidget(self.image_label);info.addWidget(self.diagnostic);info.addWidget(self.ring_note);info.addWidget(self.mask_box);info.addWidget(self.geometry_box);row.addLayout(info,1);box.addLayout(row)
        row=QHBoxLayout();row.addWidget(button('Fit / refit ring (resets calibration)',self.refit_ring));row.addWidget(button('Lock ring — center is correct',self.lock_ring));box.addLayout(row);layout.addWidget(group)
        group=QGroupBox('3 · Manual compass calibration');box=QVBoxLayout(group);form=QFormLayout();form.addRow('Chassis heading:',self.hull);box.addLayout(form)
        box.addWidget(button('Set FORWARD reference',self.set_forward));box.addWidget(button('Check RIGHT turn (about 90 degrees)',self.set_right));box.addWidget(self.zero_label);box.addWidget(self.sign_label);box.addWidget(self.assume_box);layout.addWidget(group)
        group=QGroupBox('4 · Bearing and test controls');box=QVBoxLayout(group);box.addWidget(self.bearing_text);box.addWidget(self.bearing_desc)
        box.addWidget(button('Freeze & COPY bearing now',self.copy_bearing));box.addWidget(self.mark_note)
        box.addWidget(self.float_box);box.addWidget(self.hotkey_box);box.addWidget(self.pause_box)
        row=QHBoxLayout();row.addWidget(button('I moved the Rhino — invalidate anchor',self.invalidate_anchor));row.addWidget(button('Save diagnostic snapshot…',self.save_diagnostic));box.addLayout(row);layout.addWidget(group)
        layout.addWidget(self.status)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(root);self.setCentralWidget(scroll)
        self.resize(790,900)
        self.timer=QTimer(self);self.timer.setInterval(250);self.timer.timeout.connect(self.tick);self.timer.start()
        QApplication.instance().screenRemoved.connect(self.screen_removed)

    def screen_removed(self,screen):
        if screen==self.live_screen:
            self.source_type=None;self.live_screen=None;self.session.change_source(None)
            self.candidate_ring=None;self.last_detection=None;self.status.setText('Capture screen removed. Restart and reselect.');self.update_readout()

    def heading_changed(self,text):
        self.session.set_heading(text);self.assume_box.setChecked(False);self.update_readout()
    def assumption_changed(self,yes):
        self.session.confirmed=bool(yes);self.update_readout()
    def pause_changed(self,yes):
        self.session.paused=bool(yes);self.session.confirmed=False;self.assume_box.setChecked(False)
        self.last_detection=None;self.session.observe(None,time.monotonic());self.update_readout();self.sync_hotkey()
    def invalidate_anchor(self):
        self.session.reset_angles();self.assume_box.setChecked(False);self.update_readout()
        self.status.setText('Anchor invalidated. Stop, update chassis heading, then repeat forward / RIGHT.')
    def clear_calibration(self):
        self.session.reset_angles();self.assume_box.setChecked(False);self.update_readout()

    @staticmethod
    def signature(screen):
        g=screen.geometry();return (g.x(),g.y(),g.width(),g.height(),screen.devicePixelRatio())

    def begin_live_selection(self):
        screen=self.screen_box.currentData()
        if screen is None:return
        self.busy=True;self.hotkey.disable();self.overlay.hide();self.hide()
        QTimer.singleShot(650,lambda:self.finish_live_selection(screen))

    def finish_live_selection(self,screen):
        try:
            pix=screen.grabWindow(0)
            if pix.isNull():raise ValueError('No screenshot returned; try Borderless mode')
            # Canvas works in actual image pixels, not device-independent pixels.
            pix.setDevicePixelRatio(1.0)
            dialog=RegionDialog(pix)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            rect=dialog.canvas.selected_rect();g=screen.geometry()
            crop=logical_crop((rect.x(),rect.y(),rect.width(),rect.height()),(pix.width(),pix.height()),(g.width(),g.height()))
            if min(crop[2:])<40:raise ValueError('Select the complete ring and some margin')
            self.source_type='live';self.live_screen=screen;self.crop_logical=crop;self.demo_crop=None
            self.screen_signature=self.signature(screen);self.session.change_source('live');self.candidate_ring=None
            self.source_note.setText(f'LIVE region {crop[2]} x {crop[3]} logical pixels. Keep the HUD unobscured.')
        except Exception as exc:self.status.setText(f'Selection failed: {type(exc).__name__}: {exc}')
        finally:
            self.busy=False;self.show();self.refit_ring()

    def load_sample(self):
        from PySide6.QtCore import QRect
        pix=QPixmap(str(Path(__file__).with_name('SAMPLE_RHINO_SYSTEMS_CROP.jpeg')))
        if pix.isNull():self.status.setText('Sample file is missing/unreadable');return
        self.accept_image(pix.copy(QRect(290,67,110,109)))

    def load_test_image(self):
        self.busy=True
        try:
            file,_=QFileDialog.getOpenFileName(self,'Select screenshot','','Images (*.png *.jpg *.jpeg)')
            if not file:return
            pix=QPixmap(file)
            if pix.isNull():raise ValueError('Image cannot be decoded')
            pix.setDevicePixelRatio(1.0);dialog=RegionDialog(pix,self)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            r=dialog.canvas.selected_rect();from PySide6.QtCore import QRect
            self.accept_image(pix.copy(QRect(int(r.x()),int(r.y()),int(r.width()),int(r.height()))))
        except Exception as exc:self.status.setText(f'Image selection failed: {type(exc).__name__}: {exc}')
        finally:self.busy=False

    def accept_image(self,pix):
        pix.setDevicePixelRatio(1.0);self.demo_crop=pix;self.source_type='image';self.live_screen=None;self.crop_logical=None
        self.session.change_source('image');self.candidate_ring=None
        self.source_note.setText('OFFLINE IMAGE TEST. Angles are image geometry, not a live turret bearing.')
        self.refit_ring()

    def get_frame(self):
        if self.session.paused:return None
        if self.source_type=='image':return self.demo_crop
        if self.source_type!='live' or self.live_screen is None or self.crop_logical is None:return None
        if self.signature(self.live_screen)!=self.screen_signature:
            self.session.unlock();self.candidate_ring=None
            raise ValueError('Screen layout/DPI changed. Reselect source and recalibrate')
        sx,sy,sw,sh=self.crop_logical;g=self.live_screen.geometry();roi=(g.x()+sx,g.y()+sy,sw,sh)
        for window in (self,self.overlay):
            if window.isVisible() and not window.isMinimized():
                wg=window.frameGeometry()
                if rectangles_intersect(roi,(wg.x(),wg.y(),wg.width(),wg.height())):
                    raise ValueError('This tool overlaps the HUD crop. Move/minimize its window')
        pix=self.live_screen.grabWindow(0,*self.crop_logical)
        if pix.isNull():raise ValueError('Capture returned no pixels')
        pix.setDevicePixelRatio(1.0);return pix

    def capture_array(self):
        pix=self.get_frame()
        if pix is None:return None
        image=pix.toImage().convertToFormat(QImage.Format.Format_RGB888)
        arr=rgb_array(image.width(),image.height(),bytes(image.bits()),image.bytesPerLine())
        self.last_frame=pix;self.last_array=arr;return arr

    def refit_ring(self):
        self.session.unlock();self.candidate_ring=None;self.assume_box.setChecked(False)
        try:
            arr=self.capture_array()
            if arr is None:raise ValueError('No source, or capture is paused')
            fit=fit_ring(arr);self.candidate_ring=fit.ring if fit.valid else None
            self.status.setText(fit.reason)
            self.tick(force=True)
        except Exception as exc:
            self.last_detection=None;self.status.setText(f'Ring fit failed: {type(exc).__name__}: {exc}');self.update_readout()

    def lock_ring(self):
        if self.candidate_ring is None:self.status.setText('Fit a plausible complete ring first');return
        self.busy=True
        try:
            answer=QMessageBox.question(self,'Confirm fixed pivot','Does the fitted ring follow the orange outline, and is the green dot at the cone rotation center?\n\nDo not lock a visibly wrong fit.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if answer!=QMessageBox.StandardButton.Yes:return
            self.session.lock(self.candidate_ring);self.assume_box.setChecked(False)
            self.status.setText('Ring LOCKED. It will not follow the cone. Set compass calibration next.')
        finally:self.busy=False
        self.tick()

    def analyze_frame(self):
        try:
            arr=self.capture_array()
            if arr is None:self.last_detection=None;self.last_array=None;self.last_frame=None;self.session.observe(None,time.monotonic());return None
            ring=self.session.ring or self.candidate_ring
            if ring is None:self.last_detection=None;self.session.observe(None,time.monotonic());self.refresh_preview();return None
            if self.session.ring:
                ok,reason,_=verify_ring(arr,ring)
                if not ok:
                    self.session.unlock();self.candidate_ring=None;self.assume_box.setChecked(False)
                    self.last_detection=SectorDetection(False,reason=reason,ring=ring)
                    self.session.observe(self.last_detection,time.monotonic());self.status.setText(reason)
                    self.refresh_preview();return self.last_detection
            d=detect(arr,ring)
            self.last_detection=d;self.session.observe(d,time.monotonic());self.refresh_preview();return d
        except Exception as exc:
            self.last_detection=None;self.last_array=None;self.last_frame=None;self.session.observe(None,time.monotonic())
            self.status.setText(f'Frame unavailable: {type(exc).__name__}: {exc}');return None

    def refresh_preview(self,*_):
        if self.last_array is None:return
        ring=self.session.ring or self.candidate_ring or (self.last_detection.ring if self.last_detection else None)
        arr=render_preview(self.last_array,ring,self.last_detection,self.mask_box.isChecked(),self.geometry_box.isChecked())
        h,w=arr.shape[:2];image=QImage(arr.data,w,h,w*3,QImage.Format.Format_RGB888).copy()
        pix=QPixmap.fromImage(image);pix.setDevicePixelRatio(1.0)
        self.crop_preview.setPixmap(pix.scaled(280,280,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def tick(self,force=False):
        if self.busy and not force:return
        if not self.session.paused:self.analyze_frame()
        d=self.last_detection;ring=self.session.ring or self.candidate_ring
        if d and d.valid:
            self.image_label.setText(f'IMAGE BISECTOR: {d.image_angle:05.1f}°')
            self.diagnostic.setText(f'Edges {d.edge1:.1f}° / {d.edge2:.1f}° · width {d.angular_width:.1f}°\n'
                f'{d.pixels} classified pixels · {d.support_rows}/30 supported radii\n'
                f'Apex discrepancy {d.apex_offset_px:.2f} px · edge spread {d.edge_spread_deg:.2f}°\n'
                f'Radial axis drift {d.radial_axis_drift_deg:.2f}° · {d.quality}\n'
                f'{d.reason}\n'
                'These are fit diagnostics, NOT an accuracy guarantee.')
        else:
            self.image_label.setText('IMAGE BISECTOR: UNAVAILABLE')
            self.diagnostic.setText(d.reason if d else 'No valid frame, ring, or capture is paused')
        if ring:
            state='LOCKED' if self.session.ring else 'PREVIEW — not locked'
            self.ring_note.setText(f'{state}\nPivot ({ring.cx:.2f}, {ring.cy:.2f}) · radii {ring.rx:.2f}, {ring.ry:.2f} px')
        else:self.ring_note.setText('Ring not fitted / invalidated')
        self.update_readout();self.sync_hotkey()

    def set_forward(self):
        d=self.analyze_frame();self.busy=True
        try:
            if not self.session.ring:raise ValueError('Lock the correctly fitted ring first')
            if QMessageBox.question(self,'Confirm forward','Is the turret physically looking straight along the Rhino nose, with the chassis stationary?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
            self.session.forward(d);self.assume_box.setChecked(False);self.status.setText('Forward stored. Now aim the turret about 90° RIGHT.')
        except ValueError as exc:self.status.setText(str(exc))
        finally:self.busy=False;self.update_readout()

    def set_right(self):
        d=self.analyze_frame();self.busy=True
        try:
            if QMessageBox.question(self,'Confirm RIGHT','Did you turn only the turret about 90° toward the Rhino RIGHT?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
            delta=self.session.right(d);self.assume_box.setChecked(False)
            self.status.setText(f'RIGHT check stored ({delta:+.1f}° in image). Tick the stationary/level confirmation.')
        except ValueError as exc:self.status.setText(str(exc))
        finally:self.busy=False;self.update_readout()

    def update_readout(self,*_):
        self.zero_label.setText('Forward: UNSET' if self.session.zero is None else f'Forward image zero: {self.session.zero:.1f}°')
        self.sign_label.setText('Right-turn sign: UNCHECKED' if self.session.sign is None else f'Right-turn sign: {self.session.sign:+d}')
        result,why=self.session.value(time.monotonic())
        if result is None:
            self.bearing_text.setText('TURRET: UNAVAILABLE');self.bearing_desc.setText(why)
            self.overlay.set_lines('TURRET —',why[:48])
        else:
            bearing,relative=result;prefix='OFFLINE TEST' if self.source_type=='image' else 'TURRET'
            caution=bool(self.session.detection and self.session.detection.quality=='APEX_CAUTION')
            self.bearing_text.setText(f'{prefix}: {bearing:05.1f}° EST.'+('  [CAUTION]' if caution else ''))
            self.bearing_desc.setText(f'Chassis {self.session.heading:.1f}° + relative {relative:+.1f}°. Stationary/level image estimate.'+
                                      (' APEX-FIT CAUTION: confirm against known bearing.' if caution else ''))
            self.overlay.set_lines(f'TURRET {bearing:05.1f}° EST',
                                   'APEX-FIT CAUTION · CHECK BEARING' if caution else 'SCREEN-DERIVED · STATIONARY / LEVEL')
        if self.float_box.isChecked() and self.source_type=='live' and self.live_screen and not self.busy and self.focus.elite():
            g=self.live_screen.geometry();self.overlay.move(g.x()+24,g.y()+24);self.overlay.show()
        else:self.overlay.hide()

    def copy_bearing(self):
        self.analyze_frame();result,why=self.session.value(time.monotonic())
        if result is None:
            self.mark_note.setText('NOT COPIED: '+why+'. Previous clipboard content is unchanged.');self.update_readout();return
        bearing,relative=result
        QApplication.clipboard().setText(f'{bearing:.1f}')
        mode='OFFLINE TEST' if self.source_type=='image' else 'LIVE SCREEN'
        caution=bool(self.session.detection and self.session.detection.quality=='APEX_CAUTION')
        self.mark_note.setText(f'Copied {bearing:.1f}° ({mode})'+(' — APEX-FIT CAUTION' if caution else '')+
                               f' at {datetime.now(timezone.utc):%H:%M:%S} UTC. Frozen reading; do not reuse after panning.')
        self.update_readout()

    def hotkey_copy(self):
        if self.focus.elite() and self.source_type=='live' and not self.busy and not self.session.paused:
            self.copy_bearing()

    def sync_hotkey(self,*_):
        wanted=self.hotkey_box.isChecked() and self.source_type=='live' and not self.busy and not self.session.paused and self.focus.elite()
        if wanted and not self.hotkey.enabled:
            ok,why=self.hotkey.enable()
            if not ok:
                self.hotkey_box.setChecked(False);self.status.setText(why)
        elif not wanted:self.hotkey.disable()

    def save_diagnostic(self):
        # Freeze BEFORE opening dialogs, so the diagnostic cannot capture its own dialog.
        self.analyze_frame()
        if self.last_array is None:self.status.setText('No crop to save');return
        raw=self.last_array.copy();d=self.last_detection;r=self.session.ring or self.candidate_ring
        rendered=render_preview(raw,r,d,True,True)
        from dataclasses import asdict
        record={'version':VERSION,'source':self.source_type,'timestamp_utc':datetime.now(timezone.utc).isoformat(),
                'image_width':int(raw.shape[1]),'image_height':int(raw.shape[0]),
                'ring':asdict(r) if r else None,'valid':bool(d and d.valid),
                'image_angle':d.image_angle if d else None,'reason':d.reason if d else 'No detection',
                'edge_angles':[d.edge1,d.edge2] if d else None,'apex_offset_px':d.apex_offset_px if d else None,
                'quality':d.quality if d else 'UNAVAILABLE',
                'radial_axis_drift_deg':d.radial_axis_drift_deg if d else None,
                'angle_units':'degrees clockwise from rectified image top',
                'gameplay_accuracy':'NOT_VALIDATED','privacy':'USER_SELECTED_SCREEN_CROP; REVIEW_BEFORE_SHARING'}
        self.busy=True;self.hotkey.disable()
        try:
            name=f'RHINO_turret_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.png'
            file,_=QFileDialog.getSaveFileName(self,'Save diagnostic crop and JSON',name,'PNG (*.png)')
            if not file:return
            payloads=[]
            for img in (raw,rendered):
                h,w=img.shape[:2];q=QImage(img.data,w,h,w*3,QImage.Format.Format_RGB888).copy()
                encoded=QByteArray();buffer=QBuffer(encoded)
                if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):raise OSError('Cannot create PNG buffer')
                try:
                    if not q.save(buffer,'PNG'):raise OSError('PNG encoding failed')
                finally:buffer.close()
                payloads.append(bytes(encoded))
            metadata=json.dumps(record,indent=2,allow_nan=False).encode('utf-8')
            write_diagnostic(file,payloads[0],payloads[1],metadata)
            self.status.setText('Saved raw crop, annotated preview and JSON locally. Inspect them before sharing.')
        except Exception as exc:self.status.setText(f'Diagnostic save failed: {type(exc).__name__}: {exc}. Any partial files were retained; use a new name.')
        finally:self.busy=False

    def closeEvent(self,event):
        self.timer.stop();self.hotkey.disable();self.overlay.close();super().closeEvent(event)


def main():
    app=QApplication(sys.argv);window=MainWindow();window.show();return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
