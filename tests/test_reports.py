import importlib.util
import csv
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).parents[1]
SPEC=importlib.util.spec_from_file_location('build_reports',ROOT/'scripts/build_reports.py')
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ReportTests(unittest.TestCase):
    def test_plan_relationship_csv_matches_public_update_with_unknowns(self):
        update=module.load('plan-update')
        with (ROOT/'site/literature/plan-update-relationships.csv').open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream);actual=list(reader)
            self.assertEqual(reader.fieldnames,module.PLAN_RELATIONSHIP_FIELDS)
        self.assertEqual(len(actual),3)
        expected=module.plan_relationship_rows(update)
        for row,values in zip(actual,expected):
            for key,value in zip(module.PLAN_RELATIONSHIP_FIELDS,values):
                serialized=json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else '' if value is None else str(value)
                self.assertEqual(row[key],serialized,(row['id'],key))
            for key in ('catf_tribe_id','award_id','award_amount'):
                self.assertEqual(row[key],'')
            self.assertEqual(row['adoption_status'],'unknown')
            self.assertEqual(row['current_edition_status'],'unknown')
            self.assertTrue(json.loads(row['citations'])[0]['physical_pdf_pages'])

    def test_plan_report_separates_inventory_reviewed_subset_and_old_search(self):
        update=module.load('plan-update');plans=module.load('plans')
        report=(ROOT/'site/literature/plan-discovery.html').read_text(encoding='utf-8')
        self.assertIn(update['data_as_of'],report)
        self.assertIn(plans['data_as_of'],report)
        self.assertIn('Earlier bounded public search: dated snapshot',report)
        self.assertIn('No per-Nation joins or national prevalence fraction are supported',report)
        self.assertIn('storage metric does not establish shared planning participation',report)
        self.assertIn('Two inherited files remain format-unvalidated',report)
        self.assertIn(update['provenance']['metrics_sha256'],report)
        self.assertIsNone(update['identity']['national_prevalence'])
        self.assertIn('not a representative sample',report)
        self.assertIn('Unknown support is not zero support',report)
        self.assertEqual(len(update['plan_types']),6)
        for item in update['plan_types']:
            self.assertIn(f"<td>{module.h(item['label'])}</td><td>{item['byte_distinct_files']}</td><td>{item['operational_profiles_with_label']}</td>",report)
        for relationship in update['relationships']:
            self.assertIn(module.h(relationship['source_profile_name']),report)
            for citation in relationship['citations']:
                self.assertIn(module.h(citation['url']),report)
                self.assertIn(citation['object_sha256'],report)
        for filename in ('plan-candidates.csv','nation-searches.csv','plan-update-relationships.csv'):
            self.assertIn('href="'+filename+'"',report)

    def test_public_hazard_csv_matches_every_public_json_row(self):
        risk=module.load('risk')
        with (ROOT/'site/literature/nation-hazards.csv').open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream);actual=list(reader)
            self.assertEqual(reader.fieldnames,module.HAZARD_FIELDS)
        expected=module.hazard_rows(risk)
        self.assertEqual(len(actual),len(expected))
        for row,values in zip(actual,expected):
            for key,value in zip(module.HAZARD_FIELDS,values):
                serialized=json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else '' if value is None else str(value)
                self.assertEqual(row[key],serialized,(row['tribe_id'],row['hazard_id'],key))

    def test_public_regional_cost_csv_preserves_json_totals_and_coverage(self):
        risk=module.load('risk')
        with (ROOT/'site/literature/regional-costs.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
        lookup={(row['geography'],row['metric']):row for row in rows}
        for region in [risk['national'],*risk['regions']]:
            for cost in region['costs']:
                row=lookup[cost['geography'],cost['metric']]
                self.assertEqual(row['amount'],'' if cost['amount'] is None else str(cost['amount']))
                if cost['source_ref']=='fema-nri':
                    self.assertEqual(row['source_sha256'],risk['source_snapshots']['nri_counties']['sha256'])
                    self.assertEqual(row['climate_supported_cells'],str(region['climate_county_eal_coverage']['supported_cells']))

    def test_assessment_report_keeps_source_and_semantic_cautions(self):
        report=(ROOT/'site/literature/catf-assessment.html').read_text(encoding='utf-8')
        risk=module.load('risk')
        self.assertIn('Per-Nation complete hazard-status table',report)
        self.assertIn('0 changed numeric fields',report)
        self.assertIn(risk['calculation_revision'],report)
        self.assertIn(risk['export_revision'],report)
        self.assertIn(risk['previous_snapshot']['frozen_manifest_sha256'],report)
        self.assertIn('Previous snapshot profile manifest',report)
        self.assertIn('Frozen composites still include source drought placeholders',report)
        self.assertIn(module.money(risk['national']['climate_county_eal']),report)
        self.assertNotIn('top_five_rank',report)

    def test_hazard_export_preserves_zero_placeholder_and_absence_without_ranks(self):
        hazards=[dict(hazard_id=kind,hazard_name=kind,metric='index',value=value,raw_value=raw,unit='index',status=status,coverage=coverage,missing_reason=reason,uncertainty={'basis':'source'},source_ref='pinned') for kind,value,raw,status,coverage,reason in [('zero',0,0,'modeled',1,None),('placeholder',None,.16,'placeholder',0,'legacy floor'),('absent',None,None,'unavailable',0,'No source')]]
        risk={'nations':[{'tribe_id':'a','display_name':'A','region_id':'r','percentile_rank':80,'coverage_status':'partial','hazards':hazards}]}
        rows=[dict(zip(module.HAZARD_FIELDS,row)) for row in module.hazard_rows(risk)]
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]['value'],0)
        self.assertIsNone(rows[1]['value'])
        self.assertEqual(rows[1]['raw_value'],.16)
        self.assertEqual(rows[1]['missing_reason'],'legacy floor')
        self.assertEqual(rows[2]['status'],'unavailable')
        self.assertEqual(rows[2]['source_ref'],'pinned')
        self.assertNotIn('top_five_rank',module.HAZARD_FIELDS)
        self.assertIn('(0.000)',module.hazard_cell(hazards[0]))
        self.assertIn('excluded raw 0.160',module.hazard_cell(hazards[1]))

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
        costs={'climate_county_eal':20,'climate_county_eal_coverage':{'supported_cells':1,'possible_cells':30,'status':'partial'},'county_eal':30,'unit':'USD/year','county_count':2,'expected_counties':3,'county_eal_coverage':1,'unmatched_county_fips':['99999'],'scope':'whole counties','period':'annualized','price_year':None,'source_version':'pinned','source_sha256':'accepted','county_hazards':[{'hazard_id':'X','hazard_name':'X','value':None,'contributing_counties':0}]}
        catalog={'cohorts':[{'id':'a','label':'A','costs':costs},{'id':'b','label':'B','costs':costs}]}
        rows=[dict(zip(module.COST_FIELDS,row)) for row in module.cohort_cost_rows(catalog)]
        self.assertEqual(len(rows),6)
        self.assertEqual(rows[0]['amount'],20)
        self.assertIsNone(rows[0]['available_counties'])
        self.assertEqual(rows[0]['climate_supported_cells'],1)
        self.assertEqual(rows[0]['climate_coverage_status'],'partial')
        self.assertEqual(rows[0]['source_sha256'],'accepted')
        self.assertIsNone(rows[2]['amount'])
        self.assertEqual(rows[2]['available_counties'],0)
        self.assertEqual(rows[2]['unmatched_county_fips'],['99999'])
        costs['climate_county_eal']=None;costs['climate_county_eal_coverage']={'supported_cells':0,'possible_cells':30,'status':'unavailable'}
        missing=dict(zip(module.COST_FIELDS,module.cohort_cost_rows(catalog)[0]))
        self.assertIsNone(missing['amount'])
        self.assertEqual(missing['climate_supported_cells'],0)
        self.assertIn('0 / 30 hazard cells (unavailable)',module.climate_coverage(costs))

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
