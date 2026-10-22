"""Focused accepted-climate joins, paired arithmetic and public projection checks."""
from collections import defaultdict
from copy import deepcopy
import csv
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_scanner_climate import validate_joins

BUNDLE = Path('I:/data/tcr-policy-scanner/output/integrations/climate-action-taskforce')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def quantile(values, p):
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    low = int(index)
    return ordered[low] + (index - low) * (ordered[min(low + 1, len(ordered) - 1)] - ordered[low])


class ScannerClimateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geography = read(ROOT / 'work/geography/geography.json')
        cls.nations = read(BUNDLE / 'climate_nations.json')['nations']
        cls.areas = read(BUNDLE / 'climate_areas.json')['areas']
        cls.members = read(BUNDLE / 'climate_members.json')['rows']
        cls.catalog = read(ROOT / 'site/data/explorer/catalog.json')

    def asset(self, key):
        return read(ROOT / 'site' / self.catalog['files'][key]['path'])

    def assert_summary(self, summary, values):
        for key, value in [('min', min(values)), ('p10', quantile(values, .1)),
                           ('p50', statistics.median(values)), ('p90', quantile(values, .9)), ('max', max(values))]:
            self.assertAlmostEqual(summary[key], value, places=10)

    def test_exact_agency_geometry_and_no_parent_fallback(self):
        validate_joins(self.nations, self.areas, self.geography)
        navajo = next(n for n in self.nations if len(n['area_ids']) > 1)
        self.assertEqual(len(navajo['area_ids']), 5)
        self.assertTrue(all(key.startswith('2430R-') for key in navajo['area_ids']))
        bad = deepcopy(next(a for a in self.areas if a['area_id'] in navajo['area_ids']))
        bad['geometry_area_id'] = '2430R'
        with self.assertRaises(AssertionError):
            validate_joins(self.nations, [bad if a['area_id'] == bad['area_id'] else a for a in self.areas], self.geography)
        bad = deepcopy(self.areas[0])
        bad['geometry']['provider_hash'] = 'wrong'
        with self.assertRaises(AssertionError):
            validate_joins(self.nations, [bad, *self.areas[1:]], self.geography)

    def test_area_ranges_are_paired_member_changes(self):
        area = self.asset(self.catalog['areas']['0010R']['scanner_climate_file'])
        rows = [r for r in self.members if r['area_id'] == '0010R']
        self.assertEqual(len(rows), 96)
        for projection in area['projections']:
            matched = [r for r in rows if all(r[k] == projection[k] for k in ('metric_id', 'scenario', 'period', 'baseline', 'unit'))]
            self.assertEqual({r['model'] for r in matched}, set(area['models']))
            self.assertEqual(len(matched), 8)
            for row in matched:
                self.assertAlmostEqual(row['change'], row['period_level'] - row['baseline_level'], places=12)
            for value in ('baseline_level', 'period_level', 'change'):
                self.assert_summary(projection[value], [r[value] for r in matched])

    def test_regional_equal_source_area_means_then_quantiles(self):
        for group, selected in [('ecoregions', '10.1.2'), ('advocacy_regions', 'alaska')]:
            index = next(r for r in self.catalog['scanner_climate'][group] if r['region_id'] == selected)
            region = self.asset(index['file'])
            ids = set(region['source_area_ids'])
            self.assertEqual(len(ids), region['counts']['distinct_source_areas'])
            rows = [r for r in self.members if r['area_id'] in ids]
            for projection in region['projections']:
                matched = [r for r in rows if all(r[k] == projection[k] for k in ('metric_id', 'scenario', 'period', 'baseline', 'unit'))]
                by_model = defaultdict(list)
                for row in matched:
                    by_model[row['model']].append(row)
                self.assertEqual(len(by_model), 8)
                for value in ('baseline_level', 'period_level', 'change'):
                    means = [statistics.mean(r[value] for r in members) for members in by_model.values()]
                    self.assert_summary(projection[value], means)
                self.assertTrue(all(len(members) == len(ids) for members in by_model.values()))

    def test_absence_proxy_shared_and_water_are_explicit(self):
        scanner = self.catalog['scanner_climate']
        metadata = self.asset(scanner['metadata_file'])
        self.assertEqual(metadata['counts']['supported_nations'], 547)
        self.assertEqual(metadata['counts']['unsupported_nations'], 28)
        self.assertEqual(metadata['counts']['proxy_context_nations'], 34)
        self.assertEqual(metadata['counts']['source_areas'], 526)
        self.assertEqual(metadata['counts']['ecoregions_excluding_water'], 96)
        self.assertEqual(metadata['counts']['supported_ecoregions_excluding_water'], 88)
        self.assertEqual(len(metadata['nations']), 575)
        water = next(r for r in scanner['ecoregions'] if r['region_id'] == '0.0.0')
        self.assertEqual(water['category'], 'water')
        empty = [self.asset(r['file']) for r in scanner['ecoregions'] if r['status'] != 'available']
        self.assertEqual(len(empty), 8)
        self.assertTrue(all(r['projections'] is None and r['model_means'] is None and r['missing_reason'] for r in empty))

    def test_public_projection_and_hashes(self):
        for key, descriptor in self.catalog['files'].items():
            if not key.startswith('scanner-climate'):
                continue
            content = (ROOT / 'site' / descriptor['path']).read_bytes()
            self.assertEqual(len(content), descriptor['bytes'])
            self.assertEqual(sha256(content).hexdigest(), descriptor['sha256'])
            text = content.decode('utf-8')
            self.assertNotRegex(text, r'(?<![A-Za-z])[A-Za-z]:[/\\]|canonical_profile_path|output/integrations|cpri_profiles')
        csv_descriptor = self.catalog['files']['scanner-climate-csv']
        with (ROOT / 'site' / csv_descriptor['path']).open(encoding='utf-8', newline='') as public, (BUNDLE / 'climate_projections.csv').open(encoding='utf-8', newline='') as source:
            projected = list(csv.DictReader(public))
            accepted = list(csv.DictReader(source))
        self.assertEqual(len(projected), len(accepted))
        for actual, expected in zip(projected, accepted):
            self.assertEqual({k: v for k, v in actual.items() if k in expected}, {k: v for k, v in expected.items() if k not in {'name', 'support_note'}})
            self.assertEqual(actual['model_spread_meaning'], 'not_probability')
            self.assertEqual(actual['support_note_ref'], 'scanner-climate.json')
        self.assertLess(sum(f['bytes'] for f in self.catalog['files'].values()), 16 * 1024 * 1024)
        incremental = [p for p in (ROOT / 'site').rglob('*') if p.is_file() and
                       ('/explorer/' in p.as_posix() or '/leaflet-1.9.4/' in p.as_posix() or
                        p.parent.name in {'components', 'state'} or p.name in {'explorer.js', 'catalog.js'})]
        self.assertLess(sum(p.stat().st_size for p in incremental), 16 * 1024 * 1024)

    def test_previous_native_and_usgs_products_remain_separate(self):
        previous = read(ROOT / 'work/climate/public-manifest.json')
        for key, descriptor in previous['files'].items():
            self.assertEqual(self.catalog['files'][key], descriptor)
        self.assertEqual(self.catalog['areas']['0010R']['family'], 'native-nex')
        self.assertEqual(self.catalog['areas']['HUC1707']['family'], 'usgs-nccv-loca2')
        self.assertNotIn('scanner_climate_file', self.catalog['areas']['HUC1707'])
        self.assertEqual(self.asset('climate-HUC1707')['baseline_id'], '1981-2010')


if __name__ == '__main__':
    unittest.main()
