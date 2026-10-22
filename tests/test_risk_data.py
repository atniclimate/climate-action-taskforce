import importlib.util
import json
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('risk_data', ROOT / 'scripts/prepare_risk_data.py')
risk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(risk)


class RiskTransformTests(unittest.TestCase):
    def test_assessment_gate_preserves_missing_and_supported_zero(self):
        profile = {'assessment': {'assessed': ['wildfire', 'flooding']},
                   'primary_cpri': {'hazard_scores': {'wildfire': 0, 'flooding': .6, 'drought': .99}}}
        rows = {r['hazard_id']: r for r in risk.hazard_rows('n1', profile)}
        self.assertEqual(rows['wildfire']['value'], 0)
        self.assertEqual(rows['wildfire']['status'], 'modeled')
        self.assertIsNone(rows['drought']['value'])
        self.assertIsNone(rows['extreme_heat']['value'])
        self.assertEqual(len(rows), 9)

    def test_nonfinite_values_and_placeholder_are_not_supported(self):
        profile = {'assessment': {'assessed': ['wildfire', 'flooding', 'drought']},
                   'primary_cpri': {'hazard_scores': {'wildfire': .5, 'flooding': .5, 'drought': math.nan}}}
        self.assertIsNone(next(r for r in risk.hazard_rows('n', profile) if r['hazard_id']=='drought')['value'])
        profile['primary_cpri']['hazard_scores']['drought'] = .16
        profile['eal_absent'] = [{'hazard': 'drought', 'engine_score': {'interpretation': 'legacy_placeholder_floor'}}]
        row = next(r for r in risk.hazard_rows('n', profile) if r['hazard_id']=='drought')
        self.assertEqual((row['status'], row['value'], row['raw_value']), ('placeholder', None, .16))

    def test_typed_module_absence(self):
        profile = {'modules_failed':['wildfire'], 'modules_stubbed':['drought'], 'modules_skipped':['permafrost'],
                   'assessment': {'not_assessed':[{'name':'extreme_heat','status':'data_pending'}]}}
        rows = {h['hazard_id']:h for h in risk.hazard_rows('n',profile)}
        for hazard,status in [('wildfire','failed'),('drought','stub'),('permafrost','not_applicable'),('extreme_heat','data_pending')]:
            self.assertEqual(rows[hazard]['status'],status)
            self.assertIsNone(rows[hazard]['value'])

    def test_temporal_support_gates_raw_fallback_and_accepts_evaluated_no_change(self):
        record = {'profile':{'temporal':{'grid':{'2080':{'ssp370':{'cpri_physical':.2}},'2030':{'ssp245':{'cpri_physical':.2}}}}},
                  'temporal_support':[{'horizon':'2080','scenario':'ssp370','status':'forward_supported'},
                                      {'horizon':'2030','scenario':'ssp245','status':'cell_support_unverified'}]}
        future, fallback = risk.temporal_rows(record)
        self.assertEqual(future['physical_score'],.2)
        self.assertIsNone(fallback['physical_score'])
        self.assertEqual(fallback['raw_physical_score'],.2)

    def test_empty_missing_zero_partial_and_invalid_county_totals(self):
        aggregate=lambda _,cs:(None,None,None,sum(c.vulnerability_profile['nri']['eal_total'] for c in cs))
        missing=dict(EAL_VALT='', **{h+'_EALT':'' for h in risk.HAZARDS})
        for rows in [[],[missing]]:
            total=risk.aggregate_counties(rows,aggregate)
            self.assertIsNone(total['climate_county_eal'])
            self.assertEqual(total['climate_county_eal_coverage']['status'],'unavailable')
        zero=dict(missing, IFLD_EALT='0')
        total=risk.aggregate_counties([zero],aggregate)
        self.assertEqual(total['climate_county_eal'],0)
        self.assertEqual(total['climate_county_eal_coverage']['status'],'partial')
        with self.assertRaises(ValueError): risk.aggregate_counties([dict(missing,IFLD_EALT='nan')],aggregate)
        with self.assertRaises(ValueError): risk.aggregate_counties([dict(missing,EAL_VALT='-1')],aggregate)

    def test_county_missingness_and_existing_sum_interface(self):
        rows = [dict(EAL_VALT='10.25', **{h + '_EALT': '2' for h in risk.HAZARDS}),
                dict(EAL_VALT='', **{h + '_EALT': '' for h in risk.HAZARDS})]
        def aggregate(_, contexts):
            self.assertEqual(len(contexts), 1)
            return None, None, None, 10.25
        actual = risk.aggregate_counties(rows, aggregate)
        self.assertEqual(actual['county_eal'], 10.25)
        self.assertEqual(actual['county_eal_coverage'], 1)
        self.assertEqual(actual['county_hazards'][0]['contributing_counties'], 1)

    def test_award_duplicates_adjustments_and_conflicts(self):
        row = dict(award_id='a', tribe_id='t', recipient_name_raw='Nation', obligation=-50.,
                   start_date='2020-01-01', end_date='2026-01-01')
        rows, coverage = risk.deduplicate_awards([row, row.copy()])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['obligation'], -50)
        self.assertEqual(coverage['duplicate_records_removed'], 1)
        rows, coverage = risk.deduplicate_awards([row, dict(row, obligation=100.)])
        self.assertEqual(rows, [])
        self.assertEqual(coverage['conflicting_ids_excluded'], ['a'])
        with self.assertRaises(ValueError):
            risk.deduplicate_awards([dict(row, obligation=math.inf)])

    def test_exact_match_and_legacy_name_reconciliation(self):
        award = dict(award_id='a', recipient_name_raw='FORMER NATION', obligation=12.,
                     start_date='2012-01-01', end_date='2030-01-01', program_id='p', cfda='1', awarding_agency='Agency')
        cached = [{'tribe_id': 't', 'awards': [award, dict(award, award_id='b', recipient_name_raw='Nation Housing Authority')]}]
        output = risk.funding_data(cached, [{'tribe_id': 't', 'name': 'New Nation', 'states': ['WA']}],
                                   [{'tribe_id': 't', 'name': 'Former Nation'}], {'WA': 'pnw'}, [])
        self.assertEqual(output['national']['amount'], 12)
        self.assertEqual(output['coverage']['excluded']['recipient_match_unverified']['award_count'], 1)
        self.assertEqual(output['eligibility']['status'], 'not_determined')

    def test_event_dedup_and_begin_year(self):
        event = dict(event_id='e', begin_date='2020-12-31', end_date='2021-01-02', cpi_adjusted_cost='100.10')
        events, annual = risk.ncei_summary([event, event.copy()])
        self.assertEqual(len(events), 1)
        self.assertEqual(annual[0]['year'], 2020)
        self.assertEqual(annual[0]['amount'], 100.10)
        with self.assertRaises(ValueError):
            risk.ncei_summary([event, dict(event, cpi_adjusted_cost='200')])
        with self.assertRaises(ValueError):
            risk.ncei_summary([dict(event, begin_date='not a date')])
        with self.assertRaises(ValueError):
            risk.ncei_summary([dict(event, cpi_adjusted_cost='-1')])


class FrozenArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.risk = risk.load(ROOT / 'site/data/risk.json')
        cls.funding = risk.load(ROOT / 'site/data/funding.json')

    def test_pinned_cohort_and_exclusive_regions(self):
        data = self.risk
        self.assertEqual(len({n['tribe_id'] for n in data['nations']}), 575)
        self.assertEqual(sum(r['nation_count'] for r in data['regions']), 575)
        self.assertEqual(risk.money(r['county_eal'] or 0 for r in data['regions']), data['national']['county_eal'])
        self.assertAlmostEqual(risk.money(r['climate_county_eal'] for r in data['regions']), data['national']['climate_county_eal'], delta=.05)
        self.assertEqual(sum(r['county_count'] for r in data['regions']), data['national']['county_count'])
        self.assertEqual(len(data['reconciliation']['removed_legacy_ids']), 18)
        self.assertEqual(len(data['reconciliation']['added_current_ids']), 1)
        self.assertEqual(data['input_manifest_sha256'], risk.digest(ROOT / 'work/risk/accepted-input-manifest.json'))

    def test_no_padding_unknowns_or_untraceable_rows(self):
        sources = {s['id'] for s in self.risk['sources']}
        for nation in self.risk['nations']:
            self.assertNotIn('top_hazards', nation)
            self.assertEqual(len(nation['hazards']), 9)
            self.assertEqual(nation['high_risk'], nation['percentile_rank'] >= 80 and nation['coverage_status'] == 'evaluated')
            self.assertEqual(nation['assessment_uncertainty']['basis'], 'cpri_physical')
            self.assertLessEqual(nation['assessment_uncertainty']['score_range_low'], nation['assessment_uncertainty']['score_range_high'])
            for hazard in nation['hazards']:
                self.assertIn(hazard['source_ref'], sources)
                if hazard['status'] != 'modeled':
                    self.assertIsNone(hazard['value'])
        self.assertEqual(self.risk['coverage']['placeholder_hazard_rows'],37)
        for aggregate in [self.risk['national'],*self.risk['regions']]:
            self.assertNotIn('top_hazards', aggregate)
            for hazard in aggregate['hazard_statuses']:
                self.assertEqual(sum(hazard['status_counts'].values()),aggregate['nation_count'])

    def test_frozen_priority_and_adjacent_data_unchanged(self):
        previous=risk.load(ROOT/'work/risk/previous-risk.json')
        for key in ('frozen_manifest_sha256','frozen_at_head'):
            self.assertNotIn(key,self.risk)
            self.assertEqual(self.risk['previous_snapshot'][key],previous[key])
        self.assertEqual([(n['tribe_id'],n['percentile_rank'],n['high_risk']) for n in previous['nations']],
                         [(n['tribe_id'],n['percentile_rank'],n['high_risk']) for n in self.risk['nations']])
        self.assertEqual(risk.digest(ROOT/'site/data/funding.json'),'527f856037f7a081e5eaa58287a609e91b848f0dd99db1901eb397bf5cc5bdd2')
        self.assertEqual(risk.digest(ROOT/'site/data/plans.json'),'1426c98ddfa84064aac46016c481220cdc9f6c3412e803035c90365ad3ba6f0f')
        for old,new in zip([previous['national'],*previous['regions']], [self.risk['national'],*self.risk['regions']]):
            self.assertEqual(old['county_hazards'],new['county_hazards'])
            self.assertEqual(old['county_eal'],new['county_eal'])
            if new['climate_county_eal'] is not None:
                self.assertEqual(old['climate_county_eal'],new['climate_county_eal'])

    def test_temporal_and_water_semantics(self):
        for nation in self.risk['nations']:
            for cell in nation['temporal']:
                if cell['status'] not in ['baseline_assessed','forward_supported']:
                    self.assertIsNone(cell['physical_score'])
                    self.assertIsNone(cell['monte_carlo'])
        water=next(r for r in self.risk['ecoregions']['regions'] if r['region_id']=='0.0.0')
        self.assertEqual(water['source_category'],'water')

    def test_award_regions_and_annual_events_reconcile(self):
        data = self.funding
        self.assertEqual(len({a['award_id'] for a in data['awards']}), len(data['awards']))
        self.assertEqual(risk.money(a['amount'] for a in data['awards']), data['national']['amount'])
        self.assertEqual(risk.money(r['amount'] for r in data['regions']), data['national']['amount'])
        self.assertEqual(risk.money(y['amount'] for y in self.risk['ncei_annual_series']), self.risk['national']['costs'][1]['amount'])
        self.assertIsNone(data['data_as_of'])
        self.assertTrue(all(p['eligibility']['status'] == 'unknown' for p in data['opportunities']))

    def test_public_projection_has_no_local_paths_or_private_profile_fields(self):
        for data in [self.risk, self.funding]:
            serialized = json.dumps(data)
            self.assertIsNone(re.search(r'(?<![A-Za-z])[A-Za-z]:[\\/]', serialized))
            for private in ['tek_audit', 'processing_history', 'source_path', 'recipient_name_raw']:
                self.assertNotIn('"' + private + '"', serialized)


if __name__ == '__main__':
    unittest.main()
