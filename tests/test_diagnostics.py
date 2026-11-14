import tempfile
import unittest
from pathlib import Path
from diagnostics import output_paths, write_diagnostic


class DiagnosticsTests(unittest.TestCase):
    def test_png_suffix(self):
        self.assertEqual(tuple(p.name for p in output_paths('mark.png')), ('mark.raw.png','mark.preview.png','mark.json'))
    def test_dotted_stem_preserved(self):
        self.assertEqual(output_paths('sweep.001.png')[0].name, 'sweep.001.raw.png')
    def test_uppercase_extension(self):
        self.assertEqual(output_paths('mark.PNG')[2].name, 'mark.json')
    def test_no_extension(self):
        self.assertEqual(output_paths('mark')[2].name, 'mark.json')
    def test_write_exact(self):
        with tempfile.TemporaryDirectory() as d:
            paths=write_diagnostic(Path(d)/'x.png', b'raw', b'preview', b'{}')
            self.assertEqual([p.read_bytes() for p in paths],[b'raw',b'preview',b'{}'])
    def test_existing_file_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            selection=Path(d)/'x.png';existing=output_paths(selection)[1];existing.write_bytes(b'original')
            with self.assertRaises(FileExistsError):write_diagnostic(selection,b'raw',b'preview',b'{}')
            self.assertEqual(existing.read_bytes(),b'original')
            self.assertFalse(output_paths(selection)[0].exists())
    def test_invalid_payload_makes_no_output(self):
        with tempfile.TemporaryDirectory() as d:
            selection=Path(d)/'x.png'
            with self.assertRaises(TypeError):write_diagnostic(selection,b'raw','not bytes',b'{}')
            self.assertFalse(any(Path(d).iterdir()))
    def test_missing_parent_not_created(self):
        with tempfile.TemporaryDirectory() as d:
            selection=Path(d)/'missing'/'x.png'
            with self.assertRaises(FileNotFoundError):write_diagnostic(selection,b'raw',b'preview',b'{}')
            self.assertFalse(selection.parent.exists())
