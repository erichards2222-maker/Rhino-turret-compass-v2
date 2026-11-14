"""Windows cmd.exe smoke check for the installer's early long-path exit.

Only the Python launcher command is rebound to the current interpreter. All
batch labels, branches and path checks are exercised by cmd.exe unchanged.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'win32', 'requires Windows cmd.exe')
class WindowsSetupTests(unittest.TestCase):
    def test_deep_path_exits_before_environment_creation(self):
        with tempfile.TemporaryDirectory(prefix='rtc-setup-') as temp:
            base = Path(temp)
            project = base / ('x' * 35) / ('y' * 25)
            project.mkdir(parents=True)
            self.assertGreater(len(str(project)), 70)
            script = (ROOT / 'Setup_Beta.cmd').read_text(encoding='utf-8')
            # A .cmd launcher shim would transfer control out of Setup_Beta.cmd
            # without CALL. Bind to the actual interpreter executable instead.
            lines = script.splitlines()
            rebound = [f'"{sys.executable}" ' + line[len('py -3.12 '):]
                       if line.startswith('py -3.12 ') else line for line in lines]
            self.assertEqual(sum(line.startswith('py -3.12 ') for line in lines), 3)
            (project / 'Setup_Beta.cmd').write_bytes(('\r\n'.join(rebound) + '\r\n').encode('utf-8'))
            result = subprocess.run(
                [os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', 'Setup_Beta.cmd'],
                cwd=project, input='\n', text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('Installation location is too deep', result.stdout)
            self.assertNotIn('cannot find the batch label', result.stderr.lower())
            self.assertFalse((project / '.venv').exists())
