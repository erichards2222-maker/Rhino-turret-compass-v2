"""Exercise the real native-event filter with synthetic Windows MSG structures.

This tests message routing, not OS hotkey registration or physical key presses.
The nested class is compiled unchanged from the application source and supplied
with a test-only Qt scheduler and callback. No application window is created.
"""
import ast
import ctypes
from ctypes import wintypes
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HotkeyDispatchTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((ROOT / 'turret_compass_beta.py').read_text(encoding='utf-8'))
        optional = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'OptionalHotkey')
        handler = next(n for n in ast.walk(optional) if isinstance(n, ast.ClassDef) and n.name == 'HotkeyEvents')
        module = ast.fix_missing_locations(ast.Module(body=[handler], type_ignores=[]))
        self.pending = []
        self.calls = []
        self.outer = SimpleNamespace(hotkey_id=0x5248, callback=lambda: self.calls.append('copy'))
        scheduler = SimpleNamespace(singleShot=lambda delay, callback: self.pending.append((delay, callback)))
        namespace = {'QAbstractNativeEventFilter': object, 'QTimer': scheduler,
                     'outer': self.outer, 'wintypes': wintypes}
        exec(compile(module, 'application_hotkey_filter', 'exec'), namespace)
        self.handler = namespace['HotkeyEvents']()

    def send(self, event_type, message=0x0312, key_id=0x5248):
        msg = wintypes.MSG()
        msg.message = message
        msg.wParam = key_id
        return self.handler.nativeEventFilter(event_type, ctypes.addressof(msg))

    def test_dispatcher_hotkey_is_handled(self):
        self.assertEqual(self.send(b'windows_dispatcher_MSG'), (True, 0))
        self.assertEqual(len(self.pending), 1)

    def test_window_hotkey_is_handled(self):
        self.assertEqual(self.send(b'windows_generic_MSG'), (True, 0))
        self.assertEqual(len(self.pending), 1)

    def test_dispatch_is_deferred(self):
        self.send(b'windows_dispatcher_MSG')
        self.assertEqual(self.calls, [])
        self.assertEqual(len(self.pending), 1)
        delay, callback = self.pending[0]
        self.assertEqual(delay, 0)
        callback()
        self.assertEqual(self.calls, ['copy'])

    def test_other_hotkey_id_is_ignored(self):
        self.assertEqual(self.send(b'windows_dispatcher_MSG', key_id=0x5249), (False, 0))
        self.assertEqual(self.pending, [])

    def test_other_message_is_ignored(self):
        self.assertEqual(self.send(b'windows_dispatcher_MSG', message=0x0100), (False, 0))
        self.assertEqual(self.pending, [])

    def test_other_platform_event_is_ignored(self):
        self.assertEqual(self.handler.nativeEventFilter(b'xcb_generic_event_t', 0), (False, 0))
        self.assertEqual(self.pending, [])

    def test_unrecognized_event_is_ignored(self):
        self.assertEqual(self.handler.nativeEventFilter(b'other', 0), (False, 0))
        self.assertEqual(self.pending, [])

    def test_each_message_schedules_once(self):
        for _ in range(3):
            self.send(b'windows_dispatcher_MSG')
        self.assertEqual(len(self.pending), 3)
