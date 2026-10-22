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


if __name__ == '__main__':
    unittest.main()
