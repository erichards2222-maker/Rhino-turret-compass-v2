"""Execute the long-path installer exit on Windows without installing anything."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform=='win32','Windows batch execution only')
class WindowsSetupTests(unittest.TestCase):
    def test_deep_path_exits_before_environment_creation(self):
        with tempfile.TemporaryDirectory(prefix='rtc-setup-test-') as tmp:
            base=Path(tmp)
            target=base/('nested-'+'x'*52)
            target.mkdir()
            shutil.copyfile(ROOT/'Setup_Beta.cmd',target/'Setup_Beta.cmd')
            wrapper=base/'launcher';wrapper.mkdir()
            # A test-only launcher delegates only the existing preflight -c calls.
            # Any attempt to create/install an environment exits before doing so.
            script="""import pathlib,subprocess,sys
args=sys.argv[1:]
if args and args[0]=='-3.12':args=args[1:]
if not args or args[0]!='-c':
    pathlib.Path(__file__).with_name('unexpected.txt').write_text('unexpected install')
    raise SystemExit(77)
raise SystemExit(subprocess.call([sys.executable]+args))
"""
            (wrapper/'launcher.py').write_text(script,encoding='utf-8')
            (wrapper/'py.cmd').write_text('@echo off\r\n"'+sys.executable+'" "%~dp0launcher.py" %*\r\n',encoding='utf-8',newline='')
            env=dict(os.environ);env['PATH']=str(wrapper)+os.pathsep+env['PATH']
            result=subprocess.run(['cmd.exe','/d','/c','Setup_Beta.cmd'],cwd=target,env=env,input='\n',text=True,capture_output=True,timeout=30)
            self.assertEqual(result.returncode,1,result.stdout+result.stderr)
            self.assertIn('Installation location is too deep',result.stdout)
            self.assertNotIn('cannot find the batch label',(result.stdout+result.stderr).lower())
            self.assertFalse((target/'.venv').exists())
            self.assertFalse((wrapper/'unexpected.txt').exists())
