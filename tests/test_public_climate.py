import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location('public_climate', ROOT / 'scripts/project_climate.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class PublicClimateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = ROOT / 'work/climate/manifest.json'
        if not manifest.exists():
            raise unittest.SkipTest('accepted private climate snapshot absent')
        cls.manifest = module.read(manifest)
        cls.native = module.read(ROOT / 'work/climate/areas/2070R.json')
        cls.regional = module.read(ROOT / 'work/climate/regional/US53073.json')

    def test_native_windows_preserved_without_curves(self):
        result = module.project_area(self.native, self.manifest)
        self.assertEqual(result['baseline_id'], '1995-2014')
        for metric_id in ('temp_mean', 'pr_annual'):
            metric = result['metrics'][metric_id]
            self.assertNotIn('series', metric)
            for window in self.native['metrics'][metric_id]['windows']:
                for scenario, expected in window['scenarios'].items():
                    actual = metric['windows'][window['period_id']][scenario]
                    for key in ('lower', 'median', 'upper'):
                        self.assertEqual(actual[key], expected[key])
                    self.assertEqual(actual['models'], expected['model_count'])
        self.assertEqual(result['metrics']['pr_annual']['unit'], 'mm/year')

    def test_regional_series_not_averaged_or_rebased(self):
        result = module.project_area(self.regional, self.manifest)
        self.assertEqual(result['family'], 'usgs-nccv-loca2')
        self.assertEqual(result['baseline_id'], '1981-2010')
        metric = result['metrics']['temp_mean']
        self.assertEqual(metric['windows'], {})
        for scenario in ('ssp245', 'ssp370'):
            self.assertEqual(metric['series'][scenario]['median'], self.regional['metrics']['temp_mean']['series'][scenario]['median'])

    def test_allowlist_drops_private_fields_and_rejects_paths(self):
        source = copy.deepcopy(self.native)
        source['private_cache'] = 'I:/private/cache'
        source['source']['private_path'] = 'I:/private/source'
        result = module.project_area(source, self.manifest)
        self.assertNotIn('private_cache', result)
        self.assertNotIn('private_path', result['source'])
        self.assertNotIn('dependency_hashes', result)
        with self.assertRaisesRegex(ValueError, 'local path'):
            module.check_public({'label': 'I:/private/data'})
        module.check_public({'url': 'https://data.native-resilience.com/projections/'})

    def test_bad_physical_bounds_rejected(self):
        with self.assertRaises(ValueError):
            module.check_bounds(3, 2, 4)
        with self.assertRaises(ValueError):
            module.check_bounds(0, float('nan'), 2)
        with self.assertRaises(ValueError):
            module.check_bounds(None, 1, 2)

    def test_all_projected_files_match_manifests(self):
        path = ROOT / 'work/climate/public-manifest.json'
        if not path.exists():
            self.skipTest('public projection not yet produced')
        manifest = module.read(path)
        self.assertEqual(manifest['native_area_count'], 526)
        self.assertEqual(manifest['regional_area_count'], 4)
        self.assertEqual(len(manifest['areas']), 530)
        self.assertLess(manifest['total_bytes'], 6 * 1024 * 1024)
        for record in manifest['files'].values():
            file = ROOT / 'site' / record['path']
            self.assertEqual(module.digest(file), record['sha256'])
            self.assertEqual(file.stat().st_size, record['bytes'])
            module.check_public(json.loads(file.read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
