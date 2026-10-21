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
        self.assertEqual([r['hazard_id'] for r in risk.top_five(rows.values())], ['flooding', 'wildfire'])

    def test_tie_order_and_nonfinite_values(self):
        profile = {'assessment': {'assessed': ['wildfire', 'flooding', 'drought']},
                   'primary_cpri': {'hazard_scores': {'wildfire': .5, 'flooding': .5, 'drought': math.nan}}}
        self.assertEqual([r['hazard_id'] for r in risk.top_five(risk.hazard_rows('n', profile))], ['flooding', 'wildfire'])

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
        self.assertEqual(data['input_manifest_sha256'], risk.digest(ROOT / 'work/risk/input-manifest.json'))

    def test_no_padding_unknowns_or_untraceable_rows(self):
        sources = {s['id'] for s in self.risk['sources']}
        for nation in self.risk['nations']:
            self.assertEqual(nation['top_hazards'], risk.top_five(nation['hazards']))
            self.assertLessEqual(len(nation['top_hazards']), 5)
            self.assertEqual(nation['high_risk'], nation['percentile_rank'] >= 80 and nation['coverage_status'] == 'evaluated')
            self.assertEqual(nation['assessment_uncertainty']['basis'], 'cpri_physical')
            self.assertLessEqual(nation['assessment_uncertainty']['score_range_low'], nation['assessment_uncertainty']['score_range_high'])
            for hazard in nation['hazards']:
                self.assertIn(hazard['source_ref'], sources)
                if hazard['status'] == 'unavailable':
                    self.assertIsNone(hazard['value'])
        self.assertGreater(self.risk['coverage']['nations_with_fewer_than_five'], 0)

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
