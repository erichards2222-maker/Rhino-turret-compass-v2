"""Release tooling guard tests. No service calls or publication occur here."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('publish_beta', ROOT/'tools/publish_beta.py')
PUB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PUB)


class ReleaseGuardTests(unittest.TestCase):
    def test_wrong_repository_rejected_before_io(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY':'unrelated/repo', 'GITHUB_REF':'refs/heads/publish/'+PUB.TAG}):
            with patch.object(PUB, 'request') as network:
                with self.assertRaisesRegex(ValueError, 'Wrong publication'):
                    PUB.main()
                network.assert_not_called()

    def test_wrong_branch_rejected_before_io(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY':PUB.REPO, 'GITHUB_REF':'refs/heads/main'}):
            with patch.object(PUB, 'request') as network:
                with self.assertRaisesRegex(ValueError, 'Wrong publication'):
                    PUB.main()
                network.assert_not_called()

    def test_unexpected_api_host_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected API'):
            PUB.request('https://example.invalid/test')

    def test_credential_redirect_is_disabled(self):
        self.assertIsNone(PUB.NoRedirect().redirect_request(None,None,302,'',{},'https://example.invalid/'))

    def test_asset_inventory_is_exact(self):
        self.assertEqual(len(PUB.FILES), 4)
        self.assertEqual(len(set(PUB.FILES)), 4)
        self.assertIn('CHECKSUMS.sha256', PUB.FILES)

    def test_unexpected_file_prevents_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'extra.txt').write_text('test')
            env={'GITHUB_REPOSITORY':PUB.REPO,'GITHUB_REF':'refs/heads/publish/'+PUB.TAG,'RELEASE_ASSETS':tmp}
            with patch.dict(os.environ,env), patch.object(PUB,'request') as network:
                with self.assertRaisesRegex(ValueError,'inventory'):
                    PUB.main()
                network.assert_not_called()

    def test_workflow_publish_permissions_are_bounded(self):
        text=(ROOT/'.github/workflows/release.yml').read_text()
        self.assertIn('branches: [publish/'+PUB.TAG+']',text)
        self.assertIn('      contents: write\n      actions: read',text)
        self.assertNotIn('pull_request_target',text)
        self.assertNotIn('secrets.',text)
        self.assertIn('needs: prepare',text)

    def test_release_version_matches_detector(self):
        from sector_core import VERSION
        self.assertEqual(PUB.TAG,'v'+VERSION)
