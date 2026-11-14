"""One-time import of a checksummed source snapshot into a new feature branch.

This creates immutable Git objects and one new branch only. Existing refs,
repository settings, tags and releases are not changed.
"""
from pathlib import Path, PurePosixPath
import base64
import hashlib
import io
import json
import lzma
import os
import re
import tarfile
import urllib.error
import urllib.request

REPO = 'erichards2222-maker/Rhino-turret-compass-v2'
TRIGGER = 'refs/heads/maintenance/source-import'
BASE = 'ed60e177557bb1b3e2c9f7b1c61b3733b792ff06'
BRANCH = 'release/v0.2.2-beta.1'
ARCHIVE_SHA = '8092762afea489f77a3e32cce49ad6ce3cdea4c8c5aa2c513ed82a77b55b2093'
MANIFEST_SHA = 'f6709aba7cf71cdeec418f135cdadc96547e1fd27ba4cc541ddc02bd72f60dea'
RGB_SHA = '3d471e5e1223fe8373f032bd370dd2d70c7d22d42e3c57b7019530cad1b77e7c'


def load_sources():
    folder = Path(__file__).resolve().parent
    encoded = ''.join((folder / f'part_{n:02d}.b64').read_text(encoding='ascii') for n in range(17))
    if len(encoded) != 132272:
        raise ValueError('Transport length mismatch')
    packed = base64.b64decode(encoded, validate=True)
    if len(packed) != 99204 or hashlib.sha256(packed).hexdigest() != ARCHIVE_SHA:
        raise ValueError('Transport checksum mismatch')
    decoder = lzma.LZMADecompressor(memlimit=128 * 1024 * 1024)
    raw = decoder.decompress(packed, max_length=1024 * 1024)
    if not decoder.eof or decoder.unused_data or len(raw) != 266240:
        raise ValueError('Invalid bounded archive stream')
    sources = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for entry in archive:
            name = entry.name
            path = PurePosixPath(name)
            if not entry.isfile() or path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('Invalid archive member')
            if name in sources or entry.size > 1024 * 1024:
                raise ValueError('Duplicate or oversized member')
            stream = archive.extractfile(entry)
            data = stream.read(entry.size + 1)
            if len(data) != entry.size:
                raise ValueError('Archive member length mismatch')
            sources[name] = data
    if len(sources) != 51:
        raise ValueError('Unexpected archived source count')
    return sources


def derive_rgb(sources):
    from PySide6.QtGui import QImage
    image = QImage.fromData(sources['SAMPLE_RHINO_SYSTEMS_CROP.jpeg'])
    if image.isNull() or (image.width(), image.height()) != (423, 253):
        raise ValueError('Unexpected sample dimensions')
    crop = image.copy(290, 67, 110, 109).convertToFormat(QImage.Format.Format_RGB888)
    buffer = bytes(crop.constBits())
    stride = crop.bytesPerLine()
    data = b''.join(buffer[y*stride:y*stride+330] for y in range(109))
    if len(data) != 35970 or hashlib.sha256(data).hexdigest() != RGB_SHA:
        raise ValueError('Pixel fixture mismatch')
    sources['tests/data/screenshot_crop.rgb'] = data


def validate(sources):
    manifest = sources['MANIFEST_SHA256.txt']
    if hashlib.sha256(manifest).hexdigest() != MANIFEST_SHA:
        raise ValueError('Source manifest mismatch')
    names = set()
    for line in manifest.decode('utf-8').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match:
            raise ValueError('Invalid manifest line')
        digest, name = match.groups()
        if name in names or name not in sources or hashlib.sha256(sources[name]).hexdigest() != digest:
            raise ValueError('Payload mismatch: ' + name)
        names.add(name)
    if names | {'MANIFEST_SHA256.txt'} != set(sources) or len(sources) != 52:
        raise ValueError('Source inventory mismatch')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('API redirects are not permitted')


def api(path, method='GET', payload=None, missing_ok=False):
    if not path.startswith('/') or '..' in path or '?' in path:
        raise ValueError('Invalid API path')
    url = 'https://api.github.com/repos/' + REPO + path
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
        'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Rhino-Turret-Compass-source-import'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404 and missing_ok:
            return None
        raise RuntimeError('GitHub API rejected operation: HTTP ' + str(error.code)) from None


def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF') != TRIGGER:
        raise RuntimeError('Wrong import repository or branch')
    sources = load_sources()
    derive_rgb(sources)
    validate(sources)
    print('Verified 52 source files and pinned manifest', MANIFEST_SHA, flush=True)
    if api('/git/ref/heads/main')['object']['sha'] != BASE:
        raise RuntimeError('Initial main changed; reconcile before importing')
    if api('/git/ref/heads/' + BRANCH, missing_ok=True) is not None:
        raise RuntimeError('Source branch already exists; nothing was changed')
    entries = []
    for name, data in sorted(sources.items()):
        expected = hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()
        blob = api('/git/blobs', 'POST', {'content': base64.b64encode(data).decode('ascii'), 'encoding': 'base64'})
        if blob.get('sha') != expected:
            raise RuntimeError('Created blob identity mismatch: ' + name)
        entries.append({'path': name, 'mode': '100644', 'type': 'blob', 'sha': expected})
    tree = api('/git/trees', 'POST', {'tree': entries})['sha']
    identity = {'name': 'CMDR Rhino', 'email': '327219850+erichards2222-maker@users.noreply.github.com'}
    commit = api('/git/commits', 'POST', {'message': 'Import Rhino Turret Compass public beta source',
        'tree': tree, 'parents': [BASE], 'author': identity, 'committer': identity})['sha']
    if api('/git/ref/heads/main')['object']['sha'] != BASE:
        raise RuntimeError('Main changed during import; no source ref created')
    result = api('/git/refs', 'POST', {'ref': 'refs/heads/' + BRANCH, 'sha': commit})
    if result.get('object', {}).get('sha') != commit:
        raise RuntimeError('New source reference mismatch')
    print(json.dumps({'branch': BRANCH, 'commit': commit, 'tree': tree,
                      'source_files': len(sources), 'manifest_sha256': MANIFEST_SHA}), flush=True)


if __name__ == '__main__':
    main()
