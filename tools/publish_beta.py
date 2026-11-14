"""Publish one explicitly selected, tested source-only prerelease.

Called only by the release workflow on the named publication branch. Existing
release assets and tags are never replaced. A failed upload leaves a draft.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

REPO = 'erichards2222-maker/Rhino-turret-compass-v2'
TAG = 'v0.2.2-beta.2'
API = 'https://api.github.com/repos/' + REPO
FILES = ('Rhino_Turret_Compass_v0.2.2-beta.2_Beta_SOURCE.zip', 'CHECKSUMS.sha256',
         'RELEASE_NOTES.md', 'SOURCE_PROVENANCE.json')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, method='GET', body=None, mime='application/json', missing_ok=False):
    if urllib.parse.urlparse(url).hostname not in ('api.github.com', 'uploads.github.com'):
        raise ValueError('Unexpected API destination')
    data = json.dumps(body).encode('utf-8') if isinstance(body, dict) else body
    req = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json',
        'Content-Type': mime, 'X-GitHub-Api-Version': '2022-11-28'})
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=90) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if missing_ok and exc.code == 404:
            return None
        raise RuntimeError(f'GitHub API request failed with HTTP {exc.code}') from None


def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF') != 'refs/heads/publish/'+TAG:
        raise ValueError('Wrong publication repository or branch')
    folder = Path(os.environ['RELEASE_ASSETS'])
    if {p.name for p in folder.iterdir()} != set(FILES):
        raise ValueError('Unexpected release asset inventory')
    meta = json.loads((folder/'SOURCE_PROVENANCE.json').read_text(encoding='utf-8'))
    commit = os.environ['RELEASE_COMMIT']
    if not re.fullmatch('[0-9a-f]{40}', commit) or meta['commit'] != commit or meta['repository'] != REPO or 'v'+meta['version'] != TAG:
        raise ValueError('Release provenance mismatch')
    main_ref = request(API+'/git/ref/heads/main')
    if main_ref['object']['sha'] != commit:
        raise ValueError('Main changed after testing; no release written')
    tag = request(API+'/git/ref/tags/'+TAG, missing_ok=True)
    if tag and (tag['object']['type'] != 'commit' or tag['object']['sha'] != commit):
        raise ValueError('Existing tag is not the selected commit')
    payloads = {name:(folder/name).read_bytes() for name in FILES}
    for line in payloads['CHECKSUMS.sha256'].decode('ascii').splitlines():
        digest, name = line.split('  ', 1)
        if name not in payloads or hashlib.sha256(payloads[name]).hexdigest() != digest:
            raise ValueError('Asset checksum mismatch')
    checks = [line.split('  ',1)[1] for line in payloads['CHECKSUMS.sha256'].decode('ascii').splitlines()]
    if sorted(checks) != sorted(set(FILES)-{'CHECKSUMS.sha256'}):
        raise ValueError('Checksum inventory mismatch')
    release = request(API+'/releases/tags/'+TAG, missing_ok=True)
    notes = payloads['RELEASE_NOTES.md'].decode('utf-8')
    if release is None:
        release = request(API+'/releases', 'POST', {'tag_name': TAG, 'target_commitish': commit,
            'name': 'Rhino Turret Compass '+TAG+' — Community Beta', 'body': notes,
            'draft': True, 'prerelease': True, 'make_latest': 'false'})
    elif not release['draft']:
        raise ValueError('Release is already published; leave it unchanged')
    elif release.get('target_commitish') != commit or release.get('body') != notes or not release.get('prerelease'):
        raise ValueError('Existing draft differs; leave it unchanged')
    release_id = release['id']
    existing = {a['name']:a for a in request(API+f'/releases/{release_id}/assets')}
    if set(existing)-set(FILES):
        raise ValueError('Unexpected draft assets; no deletion performed')
    upload = release['upload_url'].split('{',1)[0]
    for name, data in payloads.items():
        expected = 'sha256:'+hashlib.sha256(data).hexdigest()
        asset = existing.get(name)
        if asset is None:
            mime = 'application/zip' if name.endswith('.zip') else 'application/octet-stream'
            asset = request(upload+'?'+urllib.parse.urlencode({'name':name}), 'POST', data, mime)
        if asset.get('size') != len(data) or asset.get('digest') != expected or asset.get('state') != 'uploaded':
            raise ValueError('Uploaded asset identity mismatch; draft retained')
    # Recheck immediately before publication; never move an existing tag.
    if request(API+'/git/ref/heads/main')['object']['sha'] != commit:
        raise ValueError('Main changed during upload; draft retained')
    tag = request(API+'/git/ref/tags/'+TAG, missing_ok=True)
    if tag and (tag['object']['type'] != 'commit' or tag['object']['sha'] != commit):
        raise ValueError('Tag changed during upload; draft retained')
    published = request(API+f'/releases/{release_id}', 'PATCH', {'draft':False, 'prerelease':True, 'make_latest':'false'})
    if published['draft'] or not published['prerelease']:
        raise RuntimeError('Unexpected release state')
    print('Published prerelease:', published['html_url'])
    print('Commit:', commit)
    for name, data in payloads.items():
        print(hashlib.sha256(data).hexdigest(), name)


if __name__ == '__main__':
    main()
