"""Verify declared source/data bytes. Hash checking is not a digital signature."""
from pathlib import Path
import hashlib,re,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    manifest=ROOT/'MANIFEST_SHA256.txt'
    if not manifest.exists():print('Manifest missing');return 1
    checked=0;seen=set()
    for line in manifest.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):continue
        match=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
        if not match:print('Invalid manifest line');return 1
        expected,name=match.groups();path=ROOT/name
        if name in seen or path.is_symlink() or not path.resolve().is_relative_to(ROOT) or not path.is_file():
            print('Invalid/missing path:',name);return 1
        seen.add(name)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:print('HASH MISMATCH:',name);return 1
        checked+=1
    print(f'PASS: {checked} declared files match the manifest. This does not certify runtime safety or game accuracy.')
    return 0
if __name__=='__main__':raise SystemExit(main())
