import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).parents[1]
SPEC=importlib.util.spec_from_file_location('build_reports',ROOT/'scripts/build_reports.py')
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ReportTests(unittest.TestCase):
    def test_native_window_values_are_copied_once_per_source_area(self):
        native=json.loads((ROOT/'site/data/explorer/areas/2070R.json').read_text(encoding='utf-8'))
        regional=json.loads((ROOT/'site/data/explorer/areas/US53073.json').read_text(encoding='utf-8'))
        rows=module.climate_rows({'2070R':native,'US53073':regional})
        self.assertEqual(len(rows),12)
        first=dict(zip(module.CLIMATE_FIELDS,rows[0]))
        expected=native['metrics'][first['metric']]['windows'][first['period']][first['scenario']]
        self.assertEqual(first['median'],expected['median'])
        self.assertEqual(first['models'],8)
        self.assertEqual(first['baseline'],'1995-2014')

    def test_missing_and_shared_mapping_survive(self):
        catalog={'places':[{'kind':'nation','tribe_id':'a','name':'A','mapping_status':'associated','area_ids':['1'],'shared':True},{'kind':'nation','tribe_id':'b','name':'B','mapping_status':'unmapped','area_ids':[],'missing_reason':'No supported match'},{'kind':'region','name':'Regional'}]}
        rows=[dict(zip(module.GEO_FIELDS,row)) for row in module.geography_rows(catalog)]
        self.assertEqual(len(rows),2)
        self.assertTrue(rows[0]['shared_source'])
        self.assertEqual(rows[1]['source_area_count'],0)
        self.assertEqual(rows[1]['missing_reason'],'No supported match')

    def test_costs_preserve_missingness_without_summing_cohorts(self):
        costs={'climate_county_eal':20,'county_eal':30,'unit':'USD/year','county_count':2,'expected_counties':3,'county_eal_coverage':1,'unmatched_county_fips':['99999'],'scope':'whole counties','period':'annualized','price_year':None,'source_version':'pinned','county_hazards':[{'hazard_id':'X','hazard_name':'X','value':None,'contributing_counties':0}]}
        catalog={'cohorts':[{'id':'a','label':'A','costs':costs},{'id':'b','label':'B','costs':costs}]}
        rows=[dict(zip(module.COST_FIELDS,row)) for row in module.cohort_cost_rows(catalog)]
        self.assertEqual(len(rows),6)
        self.assertEqual(rows[0]['amount'],20)
        self.assertIsNone(rows[0]['available_counties'])
        self.assertIsNone(rows[2]['amount'])
        self.assertEqual(rows[2]['available_counties'],0)
        self.assertEqual(rows[2]['unmatched_county_fips'],['99999'])

    def test_baseline_copy_is_never_overwritten(self):
        old=(module.ROOT,module.OUT,module.PUBLIC)
        try:
            with tempfile.TemporaryDirectory() as directory:
                module.ROOT=Path(directory);module.OUT=module.ROOT/'literature';module.PUBLIC=module.ROOT/'site/literature'
                module.OUT.mkdir();(module.OUT/'report.pdf').write_bytes(b'original')
                module.preserve_reports(['report.pdf'])
                (module.OUT/'report.pdf').write_bytes(b'new')
                module.preserve_reports(['report.pdf'])
                self.assertEqual((module.ROOT/'work/baseline-2026-10-22/literature/report.pdf').read_bytes(),b'original')
        finally:module.ROOT,module.OUT,module.PUBLIC=old


if __name__=='__main__':unittest.main()
