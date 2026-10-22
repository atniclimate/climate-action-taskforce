import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from prepare_explorer import bounds, county_context
from prepare_risk_data import HAZARDS


class ExplorerProjectionTests(unittest.TestCase):
    def test_unique_counties_missingness_and_units(self):
        row = {'EAL_VALT': '100', **{h + '_EALT': '' for h in HAZARDS}}
        row['WFIR_EALT'] = '25'
        result = county_context(['00001', '00001', '00002'], {'00001': row})
        self.assertEqual(result['county_count'], 1)
        self.assertEqual(result['expected_counties'], 2)
        self.assertEqual(result['unmatched_county_fips'], ['00002'])
        self.assertEqual(result['climate_county_eal'], 25)
        self.assertEqual(result['county_eal'], 100)
        self.assertIsNone(next(r['value'] for r in result['county_hazards'] if r['hazard_id'] == 'HAIL'))
        self.assertEqual(result['unit'], 'USD/year')

    def test_geographic_bounds_keep_continuous_alaska(self):
        self.assertEqual(bounds([-190, 50, -129, 72]), [[50, -190], [72, -129]])
        with self.assertRaises(AssertionError):
            bounds([170, 50, -170, 72])

    def test_unknown_and_blank_counties_are_not_zero_loss(self):
        unknown = county_context(['99999'], {})
        self.assertIsNone(unknown['climate_county_eal'])
        self.assertEqual(unknown['unmatched_county_fips'], ['99999'])
        blank = {'EAL_VALT': '', **{h + '_EALT': '' for h in HAZARDS}}
        result = county_context(['00001'], {'00001': blank})
        self.assertIsNone(result['climate_county_eal'])
        self.assertEqual(result['climate_county_eal_coverage']['status'], 'unavailable')
        blank['WFIR_EALT'] = '0'
        supported = county_context(['00001'], {'00001': blank})
        self.assertEqual(supported['climate_county_eal'], 0)
        self.assertEqual(supported['climate_county_eal_coverage']['status'], 'partial')

    def test_source_identity_is_carried_to_cohort_output(self):
        identity = {'version': ['December 2025'], 'sha256': 'accepted'}
        result = county_context([], {}, identity)
        self.assertEqual(result['source_sha256'], 'accepted')
        self.assertEqual(result['source_version'], 'FEMA NRI December 2025 v1.20')


if __name__ == '__main__':
    unittest.main()
