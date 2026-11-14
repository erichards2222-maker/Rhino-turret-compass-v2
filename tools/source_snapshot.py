"""Create a reproducible source ZIP from the verified inventory."""
from pathlib import Path
import argparse, hashlib, re, zipfile
ROOT = Path(__file__).resolve().parents[1]
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError('Choose a new source snapshot path')
    entries = []
    for line in (ROOT/'MANIFEST_SHA256.txt').read_text(encoding='utf-8').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match: raise ValueError('Invalid manifest line')
        digest, name = match.groups(); p = ROOT/name
        if p.is_symlink() or not p.resolve().is_relative_to(ROOT) or not p.is_file(): raise ValueError('Invalid source path')
        data = p.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest: raise ValueError('Source hash mismatch: '+name)
        entries.append((name, data))
    if len({name for name, _ in entries}) != len(entries): raise ValueError('Repeated source name')
    entries.append(('MANIFEST_SHA256.txt', (ROOT/'MANIFEST_SHA256.txt').read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(entries):
            info = zipfile.ZipInfo('Rhino-turret-compass/'+name, (2026, 11, 13, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    print('Snapshot SHA256:', hashlib.sha256(args.output.read_bytes()).hexdigest())
    print('Source files:', len(entries))
if __name__ == '__main__': main()
