"""Refresh the declared source inventory after intentional, reviewed edits."""
from pathlib import Path
import hashlib
ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 'test-output', '.test-output', 'diagnostics'}
ALLOWED_SUFFIXES = {'.py', '.md', '.html', '.cmd', '.txt', '.json', '.csv', '.png', '.jpeg', '.rgb', '.yml', '.yaml'}
SPECIAL = {'LICENSE', '.gitignore', '.gitattributes'}
def files():
    for p in sorted(ROOT.rglob('*')):
        rel = p.relative_to(ROOT)
        if any(x in IGNORED_DIRS for x in rel.parts): continue
        if p.name == 'MANIFEST_SHA256.txt' or not p.is_file(): continue
        if p.is_symlink(): raise ValueError('Symlinks are not source inventory members')
        if p.suffix in ALLOWED_SUFFIXES or p.name in SPECIAL: yield p
        else: raise ValueError('Unrecognized source file: ' + rel.as_posix())
def main():
    selected = list(files())
    lines = [hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.relative_to(ROOT).as_posix() for p in selected]
    (ROOT/'MANIFEST_SHA256.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')
    print(f'Updated {len(selected)} source entries. Review the diff before committing.')
if __name__ == '__main__': main()
