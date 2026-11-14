"""Checks for the declared runtime dependencies and Windows interfaces."""
import ast
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ('sector_core.py', 'compass_state.py', 'preview.py', 'capture_geometry.py', 'diagnostics.py', 'turret_compass_beta.py')
ALLOWED_IMPORTS = {'__future__', 'dataclasses', 'math', 'numpy', 'sector_core', 'pathlib', 'sys', 'time', 'json', 'ctypes', 'datetime', 'PySide6', 'capture_geometry', 'compass_state', 'diagnostics', 'preview'}
WINDOW_APIS = {'RegisterHotKey', 'UnregisterHotKey', 'GetForegroundWindow', 'GetClassNameW'}

class SourceContractTests(unittest.TestCase):
    def test_runtime_ast_compiles(self):
        for name in RUNTIME:
            compile((ROOT/name).read_text(encoding='utf-8'), name, 'exec')
    def test_runtime_dependencies_are_declared(self):
        for name in RUNTIME:
            for node in ast.walk(ast.parse((ROOT/name).read_text(encoding='utf-8'))):
                if isinstance(node, ast.Import): mods = [n.name.split('.')[0] for n in node.names]
                elif isinstance(node, ast.ImportFrom): mods = [(node.module or '').split('.')[0]]
                else: continue
                self.assertTrue(set(mods) <= ALLOWED_IMPORTS, (name, mods))
    def test_windows_interfaces_are_declared(self):
        tree = ast.parse((ROOT/'turret_compass_beta.py').read_text(encoding='utf-8'))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute) and node.value.attr in ('user32', 'u'):
                found.add(node.attr)
        self.assertEqual(found, WINDOW_APIS)
    def test_runtime_calls_are_statically_defined(self):
        for name in RUNTIME:
            for node in ast.walk(ast.parse((ROOT/name).read_text(encoding='utf-8'))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, ('eval', 'exec', 'compile'))
    def test_setup_requires_hashes_and_fixed_index(self):
        s = (ROOT/'Setup_Beta.cmd').read_text()
        for flag in ('--require-hashes', '--only-binary=:all:', '--isolated', '--index-url https://pypi.org/simple'):
            self.assertIn(flag, s)
    def test_setup_rejects_deep_install_path_before_changes(self):
        s=(ROOT/'Setup_Beta.cmd').read_text()
        self.assertIn("n<=70",s)
        self.assertIn('goto path_too_long',s)
        self.assertIn(':path_too_long', s.splitlines())
        self.assertNotIn("':path_too_long", s.splitlines())
        self.assertIn('%USERPROFILE%',s)
        self.assertLess(s.index('goto path_too_long'),s.index(' -m venv .venv'))
        self.assertLess(s.index('goto path_too_long'),s.index(' -m pip '))

    def test_launcher_keeps_errors_visible(self):
        s = (ROOT/'Run_Beta.cmd').read_text()
        self.assertIn('python.exe', s); self.assertNotIn('pythonw.exe', s); self.assertIn('environment_check.py', s)
    def test_commands_use_windows_line_endings(self):
        for f in ROOT.glob('*.cmd'):
            self.assertNotIn(b'\n', f.read_bytes().replace(b'\r\n', b''))
    def test_pins_exact(self):
        s = (ROOT/'requirements.txt').read_text()
        self.assertIn('numpy==2.3.5', s); self.assertEqual(s.count('--hash=sha256:'), 3)
