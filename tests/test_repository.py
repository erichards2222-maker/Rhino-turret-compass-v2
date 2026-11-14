"""Project inventory and distribution regression checks."""
import hashlib, json, re, struct, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class RepositoryTests(unittest.TestCase):
    def entries(self):
        rows = []
        for line in (ROOT/'MANIFEST_SHA256.txt').read_text(encoding='utf-8').splitlines():
            match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
            self.assertIsNotNone(match)
            rows.append(match.groups())
        return rows
    def test_manifest_paths_are_unique(self):
        paths = [name for _, name in self.entries()]
        self.assertEqual(len(paths), len(set(paths)))
    def test_manifest_members_are_regular_contained_files(self):
        for _, name in self.entries():
            p = ROOT/name
            self.assertTrue(p.is_file()); self.assertFalse(p.is_symlink())
            self.assertTrue(p.resolve().is_relative_to(ROOT))
    def test_manifest_digests_match(self):
        for digest, name in self.entries():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest, name)
    def test_preview_png_has_only_image_chunks(self):
        data = (ROOT/'DETECTION_PREVIEW_v0.2.png').read_bytes()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n'); pos = 8; seen = []
        while pos < len(data):
            n = struct.unpack('>I', data[pos:pos+4])[0]; kind = data[pos+4:pos+8]
            self.assertIn(kind, {b'IHDR', b'PLTE', b'tRNS', b'IDAT', b'IEND'})
            seen.append(kind); pos += n+12
        self.assertEqual(pos, len(data)); self.assertEqual(seen[-1], b'IEND')
    def test_sample_jpeg_application_segments_are_minimal(self):
        data = (ROOT/'SAMPLE_RHINO_SYSTEMS_CROP.jpeg').read_bytes()
        self.assertEqual(data[:2], b'\xff\xd8'); pos = 2
        while pos < len(data):
            self.assertEqual(data[pos], 255); pos += 1
            while data[pos] == 255: pos += 1
            code = data[pos]; pos += 1
            if code == 0xDA: break
            if code in (0xD8, 0xD9) or 0xD0 <= code <= 0xD7: continue
            self.assertFalse(0xE1 <= code <= 0xEF or code == 0xFE)
            n = int.from_bytes(data[pos:pos+2], 'big'); pos += n
    def test_fixture_metadata_matches_sample(self):
        d = json.loads((ROOT/'tests/data/screenshot_crop.json').read_text())
        self.assertEqual(hashlib.sha256((ROOT/d['parent']).read_bytes()).hexdigest(), d['parent_sha256'])
        self.assertEqual((ROOT/'tests/data/screenshot_crop.rgb').stat().st_size, 110*109*3)
    def test_correct_commander_attribution(self):
        for name in ('README.md', 'NOTICE.md', 'RELEASE_NOTES.md', 'COMMUNITY_BETA.md'):
            text = (ROOT/name).read_text(encoding='utf-8')
            self.assertIn('CMDR Dunn Actual', text, name)
            self.assertNotIn('CMDR ' + 'Rhino', text, name)

    def test_license_and_notices_present(self):
        self.assertTrue((ROOT/'LICENSE').read_text().startswith('MIT License'))
        self.assertIn('Frontier', (ROOT/'NOTICE.md').read_text())
    def test_checkout_rules_cover_command_and_binary_files(self):
        s = (ROOT/'.gitattributes').read_text()
        self.assertIn('*.cmd text eol=crlf', s); self.assertIn('*.rgb binary', s)
    def test_actions_use_exact_commit_pins(self):
        s = (ROOT/'.github/workflows/tests.yml').read_text()
        uses = re.findall(r'uses:\s+(\S+)', s)
        self.assertEqual(len(uses), 4)
        for ref in uses: self.assertRegex(ref, r'^actions/[a-z-]+@[a-f0-9]{40}$')
    def test_ci_is_read_only_and_head_bound(self):
        s = (ROOT/'.github/workflows/tests.yml').read_text()
        self.assertIn('contents: read', s); self.assertIn('persist-credentials: false', s)
        self.assertIn('github.event.pull_request.head.sha || github.sha', s)
        self.assertNotIn('pull_request_target', s); self.assertNotIn('secrets.', s)
    def test_generated_results_are_ignored(self):
        s = (ROOT/'.gitignore').read_text()
        for name in ('test-output/', '.venv/', 'diagnostics/', '__pycache__/'): self.assertIn(name, s)
