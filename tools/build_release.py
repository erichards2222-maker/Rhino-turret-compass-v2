"""Build source-only beta assets from the verified checkout."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.2.2-beta.1'
REPOSITORY = 'erichards2222-maker/Rhino-turret-compass-v2'


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python tools/build_release.py NEW_OUTPUT_DIRECTORY')
    output = Path(sys.argv[1]).resolve()
    if output.exists() or output.is_relative_to(ROOT):
        raise ValueError('Use a new output directory outside the checkout')
    subprocess.run([sys.executable, '-B', str(ROOT/'tools/verify_package.py')], check=True, cwd=ROOT)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
    output.mkdir(parents=True)
    archive = output/f'Rhino_Turret_Compass_v{VERSION}_Beta_SOURCE.zip'
    subprocess.run([sys.executable, '-B', str(ROOT/'tools/source_snapshot.py'), str(archive)], check=True, cwd=ROOT)
    (output/'RELEASE_NOTES.md').write_bytes((ROOT/'RELEASE_NOTES.md').read_bytes())
    metadata = {'repository': REPOSITORY, 'version': VERSION, 'commit': commit, 'tree': tree,
                'source_zip': archive.name, 'source_zip_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'manifest_sha256': hashlib.sha256((ROOT/'MANIFEST_SHA256.txt').read_bytes()).hexdigest(),
                'distribution': 'Python source; Windows x64; Python 3.12',
                'accuracy': 'Experimental navigation estimate; no universal error bound'}
    (output/'SOURCE_PROVENANCE.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8', newline='\n')
    assets = sorted(p for p in output.iterdir() if p.is_file())
    (output/'CHECKSUMS.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in assets), encoding='ascii', newline='\n')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
