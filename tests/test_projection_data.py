import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import pyarrow as pa

SPEC = importlib.util.spec_from_file_location('projection', Path(__file__).parents[1] / 'scripts/prepare_projection_data.py')
projection = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(projection)


def annual_rows(metric='temp_mean'):
    rows = []
    for number, model in enumerate(projection.MODELS):
        for scenario in projection.SCENARIOS:
            for year in projection.YEARS:
                base = 32 + number * 18 if metric == 'temp_mean' else 0
                delta = 0 if year < 2015 else 9 if scenario == 'ssp245' else 18
                rows.append({'model': model, 'scenario': scenario, 'Year': year, 'n_days': 365,
                             'metric_id': metric, 'metric_version': 1, 'value': base + delta})
    return rows


class ProjectionTests(unittest.TestCase):
    def derive(self, rows, metric='temp_mean'):
        return projection.derive_metric(rows, metric, {'label': projection.METRICS[metric]['source_label'], 'metric_version': 1})

    def test_member_first_changes_and_units(self):
        result, detail = self.derive(annual_rows())
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['model_count'], 8)
        self.assertEqual(result['windows'][0]['scenarios']['ssp245']['median'], 5)
        self.assertEqual(result['windows'][0]['scenarios']['ssp370']['median'], 10)
        self.assertEqual(result['baseline_level']['median'], 35)
        self.assertEqual(len(detail), 8 * 2 * 3)
        self.assertIsNone(result['calendar'])
        self.assertIsNone(result['provider_fit_status'])

    def test_missing_member_is_excluded_not_zero(self):
        rows = annual_rows()
        rows[0]['value'] = None
        result, _ = self.derive(rows)
        self.assertEqual(result['model_count'], 7)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['windows'][0]['scenarios']['ssp245']['median'], 5)

    def test_missing_metric_and_valid_precipitation_zero(self):
        missing, _ = self.derive([], 'pr_annual')
        self.assertEqual(missing['status'], 'unavailable')
        result, _ = self.derive(annual_rows('pr_annual'), 'pr_annual')
        self.assertEqual(result['baseline_level']['median'], 0)
        self.assertEqual(result['windows'][0]['scenarios']['ssp245']['median'], 228.6)

    def test_duplicate_and_disagreeing_history(self):
        rows = annual_rows()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.derive(rows + [rows[0]])
        rows[0]['value'] += 1
        result, _ = self.derive(rows)
        self.assertEqual(result['excluded_models'][projection.MODELS[0]], 'historical_scenario_copies_disagree')

    def test_quantiles_units_and_fingerprint(self):
        self.assertEqual(projection.quantiles([0, 10]), {'lower': 1, 'median': 5, 'upper': 9})
        self.assertEqual(projection.canonical(32, 'temp_mean'), 0)
        self.assertEqual(projection.canonical(9, 'temp_mean', change=True), 5)
        self.assertNotEqual(projection.fingerprint({'source': 'a'}), projection.fingerprint({'source': 'b'}))

    def test_corrupt_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source').write_bytes(b'changed')
            projection.atomic_json(root / 'source.receipt.json', {'url': 'https://example.org/input', 'sha256': projection.sha_bytes(b'original')})
            with self.assertRaisesRegex(ValueError, 'cached input'):
                projection.acquire(root, 'source', 'https://example.org/input')

    def test_all_id_accounting_shared_proxy_and_unmapped(self):
        registry = {'tribes': [{'tribe_id': t} for t in ('a', 'b', 'c')]}
        links = {'registry_sha256': 'registry', 'nations': [
            {'tribe_id': t, 'area_ids': ['area'] if t != 'c' else [], 'proxy': t == 'b',
             'missing_reason': 'no_match' if t == 'c' else None} for t in ('a', 'b', 'c')]}
        result = projection.account_nations(registry, links, [{'area_id': 'area', 'status': 'available',
            'metric_status': {'temp_mean': 'available', 'pr_annual': 'unavailable'}}])
        self.assertEqual(result['metrics']['temp_mean']['supported_nations'], 2)
        self.assertEqual(result['metrics']['temp_mean']['distinct_supported_areas'], 1)
        self.assertEqual(result['metrics']['temp_mean']['proxy_context_nations'], 1)
        self.assertEqual(result['nations'][2]['climate']['temp_mean']['status'], 'unmapped')
        self.assertEqual(result['metrics']['pr_annual']['supported_nations'], 0)
        with self.assertRaisesRegex(ValueError, 'exact pinned registry'):
            projection.account_nations({'tribes': [{'tribe_id': 'd'}]}, links, [])

    def test_changed_input_failure_replaces_old_success(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            raw = out / 'raw'
            raw.mkdir()
            path = raw / 'demo.annual.parquet'
            projection.pq.write_table(pa.Table.from_pylist(annual_rows() + annual_rows('pr_annual')), path)
            source_path = 'data/annual/land_id=demo/part-0.parquet'
            projection.atomic_json(raw / 'demo.annual.parquet.receipt.json', {
                'url': projection.NATIVE + source_path, 'sha256': projection.sha_bytes(path.read_bytes()), 'bytes': path.stat().st_size})
            land = {'land_id': 'demo', 'name': 'Fixture', 'GEOID': 'demo', 'COMPTYP': 'R', 'census_year': 2025, 'geom_hash': 'geometry'}
            metadata = {m: {'label': spec['source_label'], 'metric_version': 1} for m, spec in projection.METRICS.items()}
            provider = {source_path: {'size': path.stat().st_size}}
            first = projection.prepare_native(land, raw, out, metadata, {'input': 'fixed'}, provider)
            self.assertEqual(first['status'], 'available')
            resumed = projection.prepare_native(land, raw, out, metadata, {'input': 'fixed'}, provider)
            self.assertTrue(resumed['resumed'])
            path.write_bytes(b'changed input')
            failed = projection.prepare_native(land, raw, out, metadata, {'input': 'fixed'}, provider)
            self.assertEqual(failed['status'], 'invalid')
            self.assertNotIn('metrics', projection.read_json(out / 'areas/demo.json'))

    def test_real_schema_regional_source(self):
        path = Path(__file__).parents[1] / 'work/climate/raw/US53073_tas.json.gz'
        if not path.exists():
            self.skipTest('optional frozen real source absent')
        data = json.loads(projection.gzip.decompress(path.read_bytes()))
        result = projection.parse_regional(data, 'Whatcom County, Washington', 'county', {'sha256': 'fixture'})
        metric = result['metrics']['temp_mean']
        self.assertEqual(metric['baseline_id'], '1981-2010')
        self.assertEqual(metric['series']['ssp245']['model_count'], 24)
        self.assertEqual(metric['series']['ssp370']['model_count'], 23)
        self.assertEqual(metric['series']['ssp245']['median'], data['timeseries']['scenarios'][0]['months'][0]['ensemble_anom_middle'])
        self.assertEqual(result['family'], 'usgs-nccv-loca2')


if __name__ == '__main__':
    unittest.main()
