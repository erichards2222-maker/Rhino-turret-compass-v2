"""Retest a source ZIP produced from the exact repository checkout.

Run with Python from the declared environment. Writes a new result directory;
existing roundtrip results are never replaced. Only declared source files are
extracted. Runtime tests use a static fixture and fictional calibration.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run_check(command, cwd, log):
    result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                            errors='replace', timeout=300)
    log.write_text(result.stdout, encoding='utf-8', newline='\n')
    print(log.name, 'PASS' if result.returncode == 0 else 'FAIL', flush=True)
    if result.returncode:
        print(result.stdout, flush=True)
        raise RuntimeError('Roundtrip check failed: ' + log.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, default=Path('test-output'))
    args = parser.parse_args()
    output = args.output.resolve() / 'roundtrip'
    output.mkdir(parents=True, exist_ok=False)
    expected = {}
    for line in (ROOT / 'MANIFEST_SHA256.txt').read_text(encoding='utf-8').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match:
            raise ValueError('Invalid source manifest')
        digest, name = match.groups()
        if name in expected:
            raise ValueError('Duplicate source manifest entry')
        expected[name] = digest
    expected['MANIFEST_SHA256.txt'] = hashlib.sha256((ROOT/'MANIFEST_SHA256.txt').read_bytes()).hexdigest()
    commit = os.environ.get('COMPASS_COMMIT')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit is not None and head != commit:
        raise ValueError('Checkout does not match proposed commit')
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')) - {''}
    if tracked != set(expected):
        raise ValueError('Git tracked inventory differs from declared source inventory')
    with tempfile.TemporaryDirectory(prefix='compass-roundtrip-') as temp:
        destination = Path(temp)
        with zipfile.ZipFile(args.archive) as archive:
            names = archive.namelist()
            wanted = {'Rhino-turret-compass/' + name for name in expected}
            if len(names) != len(set(names)) or set(names) != wanted:
                raise ValueError('Source archive inventory mismatch')
            for info in archive.infolist():
                member = PurePosixPath(info.filename)
                if member.is_absolute() or '..' in member.parts or '\\' in info.filename:
                    raise ValueError('Invalid source archive path')
                if info.file_size > 1024 * 1024 or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Unsupported archive member')
                relative = '/'.join(member.parts[1:])
                data = archive.read(info)
                if hashlib.sha256(data).hexdigest() != expected[relative]:
                    raise ValueError('Archive payload mismatch: ' + relative)
                path = destination / member
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        source = destination / 'Rhino-turret-compass'
        python = sys.executable
        run_check([python, '-B', 'tools/verify_package.py'], source, output/'manifest.txt')
        run_check([python, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v'], source, output/'unit.txt')
        run_check([python, '-B', 'tools/gui_smoke.py'], source, output/'qt.txt')
        for suite in ('clean', 'degraded', 'adversarial', 'apex'):
            run_check([python, '-B', 'tools/run_matrix.py', suite, '--output', str(output)], source, output/(suite+'.txt'))
        run_check([python, '-B', 'tools/verify_package.py'], source, output/'manifest_after.txt')
    receipt = {'commit': head, 'python': platform.python_version(),
               'platform': platform.platform(), 'source_files': len(expected),
               'source_archive_sha256': hashlib.sha256(args.archive.read_bytes()).hexdigest(),
               'source_manifest_sha256': expected['MANIFEST_SHA256.txt'],
               'checks': ['inventory', 'manifest', 'unit', 'qt_static', 'clean', 'degraded', 'adversarial', 'apex', 'manifest_after'],
               'result': 'PASS', 'live_gameplay': 'NOT_RUN'}
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
