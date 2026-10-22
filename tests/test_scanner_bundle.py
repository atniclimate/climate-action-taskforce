import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('scanner_bundle',ROOT/'scripts/scanner_bundle.py')
bundle=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class AcceptanceTests(unittest.TestCase):
    def test_pins_and_projection_comparison(self):
        self.assertTrue(all(len(v)==64 for v in [bundle.COUNTY_HASH,bundle.ROSTER_HASH,*bundle.PINS.values()]))
        self.assertTrue(bundle.projection_matches({'a':{'b':1,'private':2}}, {'a':{'b':1}}))
        self.assertFalse(bundle.projection_matches({'a':[1,2]}, {'a':[1]}))
        self.assertFalse(bundle.projection_matches({'a':1},{'a':2}))

    def test_missing_and_mismatched_bundle_fail_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(FileNotFoundError): bundle.verify_bundle(root,root)
            (root/'handoff-manifest.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'hash mismatch'): bundle.verify_bundle(root,root)

    def test_county_drift_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'county.csv'
            path.write_text('STCOFIPS,NRI_VER,EAL_VALT\n01001,December 2025,0\n')
            with self.assertRaisesRegex(ValueError,'hash mismatch'): bundle.accept_county_snapshot(path)

    def test_county_version_duplicate_and_invalid_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(bundle,'require_hash'):
            path=Path(directory)/'county.csv'
            for text,error in [('STCOFIPS,NRI_VER,EAL_VALT\n01001,older,0\n','version'),
                               ('STCOFIPS,NRI_VER,EAL_VALT\n01001,December 2025,0\n01001,December 2025,1\n','duplicate'),
                               ('STCOFIPS,NRI_VER,EAL_VALT\n01001,December 2025,nan\n','Invalid')]:
                path.write_text(text)
                with self.assertRaisesRegex(ValueError,error): bundle.accept_county_snapshot(path)


if __name__=='__main__': unittest.main()
