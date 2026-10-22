"""Project public scanner caches into static presentation data; never run a model."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
import tomllib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
ROSTER_HASH = '5db8f52cf44d3a3853f8403cd6dc845a59088f07f42b40a3488575b5cbe7cece'
PROFILE_HAZARDS = {
    'wildfire': 'Wildfire', 'flooding': 'Flooding (coastal and inland)', 'drought': 'Drought',
    'severe_weather': 'Severe weather', 'extreme_heat': 'Extreme heat', 'landslide': 'Landslide',
    'sea_level_rise': 'Sea-level rise', 'coastal_erosion': 'Coastal erosion', 'permafrost': 'Permafrost thaw',
}
HAZARD_BASIS = {
    'wildfire': 'Wildfire NRI risk percentile / 100; source-specific override may apply.',
    'flooding': 'Maximum of coastal and inland NRI risk percentiles / 100; not inland flood alone.',
    'drought': 'Drought exposure blend: 0.6 raw + 0.2 water + 0.2 agriculture; current defaults yield 0.6 raw + 0.16.',
    'extreme_heat': 'Heat exposure blend; current defaults yield 0.7 raw + 0.09.',
    'severe_weather': 'Mean of selected positive severe-weather hazard scores; different inclusion from other indexes.',
    'landslide': 'Nonlinear landslide screening transform; not comparable to percentile/blended indexes.',
}
HAZARDS = {
    'AVLN': 'Avalanche', 'CFLD': 'Coastal flooding', 'CWAV': 'Cold wave',
    'DRGT': 'Drought', 'HAIL': 'Hail', 'HWAV': 'Heat wave', 'HRCN': 'Hurricane',
    'ISTM': 'Ice storm', 'IFLD': 'Inland flooding', 'LNDS': 'Landslide',
    'LTNG': 'Lightning', 'SWND': 'Strong wind', 'TRND': 'Tornado',
    'WFIR': 'Wildfire', 'WNTW': 'Winter weather',
}
SOURCES = [
    {'id': 'fema-nri', 'title': 'FEMA National Risk Index, December 2025 v1.20',
     'url': 'https://www.fema.gov/flood-maps/products-tools/national-risk-index',
     'method_url': 'https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_technical-documentation.pdf',
     'rights': 'U.S. federal public data; retain FEMA attribution.'},
    {'id': 'ncei-bdd', 'title': 'NOAA NCEI Billion-Dollar Weather and Climate Disasters, cached 1980–2024 series',
     'url': 'https://www.ncei.noaa.gov/access/billions/',
     'rights': 'NOAA/NCEI public data; retain attribution.'},
    {'id': 'usaspending', 'title': 'USAspending award data, historical scanner cache',
     'url': 'https://www.usaspending.gov/search',
     'rights': 'U.S. federal public award data; retain attribution.'},
    {'id': 'bia-roster', 'title': 'BIA federally recognized Tribal entities, January 30, 2026',
     'url': 'https://www.govinfo.gov/content/pkg/FR-2026-01-30/html/2026-01899.htm',
     'rights': 'U.S. federal public notice; EPA stable identifiers retained.'},
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def money(values):
    return float(sum((Decimal(str(v)) for v in values), Decimal(0)).quantize(Decimal('.01')))


def top_five(rows):
    return sorted((r for r in rows if r['status'] == 'modeled' and numeric(r['value'])),
                  key=lambda r: (-r['value'], r['hazard_id']))[:5]


def hazard_rows(tribe_id, profile):
    rows = []
    assessed = set(profile.get('assessment', {}).get('assessed', []))
    values = profile.get('primary_cpri', {}).get('hazard_scores', {})
    absence = {r['hazard']: r for r in profile.get('eal_absent', [])}
    not_assessed = {r['name']: r['status'] for r in profile.get('assessment', {}).get('not_assessed', [])}
    for code, name in PROFILE_HAZARDS.items():
        value = values.get(code)
        evidence = absence.get(code, {})
        interpretation = evidence.get('engine_score', {}).get('interpretation')
        supported = code in assessed and numeric(value) and 0 <= value <= 1
        status = 'modeled' if supported else not_assessed.get(code, 'unavailable')
        if code in profile.get('modules_skipped', []):
            status = 'not_applicable'
        if code in profile.get('modules_stubbed', []):
            status = 'stub'
        if code in profile.get('modules_failed', []):
            status = 'failed'
        if interpretation == 'legacy_placeholder_floor':
            status = 'placeholder'
        supported = supported and status == 'modeled'
        rows.append({
            'tribe_id': tribe_id, 'hazard_id': code, 'hazard_name': name,
            'metric': 'cpri_hazard_exposure_score', 'value': value if supported else None,
            'raw_value': value if numeric(value) else None,
            'unit': 'index (0–1)', 'status': status, 'source_ref': 'scanner-cpri',
            'coverage': 'assessed' if supported else 'not_assessed',
            'source_basis': evidence.get('engine_score', {}).get('basis', HAZARD_BASIS.get(code, 'No supported quantitative method in this snapshot.')),
            'comparison_context': {'formula_version': '3.2.0', 'channel': 'exposure_score', 'horizon': 'baseline',
                                   'scenario': 'ssp245', 'boundary_source': profile.get('boundary_source'),
                                   'comparability': 'No cross-hazard severity comparison; within-hazard comparison requires matching source support.'},
            'source_interpretation': interpretation,
            'uncertainty': evidence or None,
            'missing_reason': None if supported else evidence.get('disclosure_text', f'Source status: {status}; not a supported physical zero.'),
        })
    return rows


def make_regions(config):
    regions = {k: {'region_id': k, 'name': v['short_name'], 'states': v['states']}
               for k, v in config['regions'].items() if k != 'crosscutting'}
    # The scanner's geographic groups omit California; its crosscutting row is not a region.
    regions['california'] = {'region_id': 'california', 'name': 'California', 'states': ['CA']}
    regions['other'] = {'region_id': 'other', 'name': 'Other / unassigned', 'states': ['HI', 'KY', 'PR', 'VI', 'GU', 'AS', 'MP']}
    state_regions = {}
    for key, region in regions.items():
        for state in region['states']:
            if state in state_regions:
                raise ValueError(f'Overlapping state taxonomy: {state}')
            state_regions[state] = key
    return regions, state_regions


def frequency_rows(nations):
    counts = Counter(h['hazard_id'] for n in nations for h in n['top_hazards'])
    supported = Counter(h['hazard_id'] for n in nations for h in n['hazards'] if h['status'] == 'modeled')
    return sorted([{'hazard_id': code, 'hazard_name': PROFILE_HAZARDS[code],
                    'metric': 'nations_with_hazard_in_top_five', 'value': count, 'unit': 'Nations',
                    'status': 'modeled', 'contributing_nations': supported[code],
                    'denominator': len(nations), 'source_ref': 'scanner-cpri'}
                   for code, count in counts.items()], key=lambda r: (-r['value'], r['hazard_id']))[:5]


def aggregate_counties(rows, aggregate_vulnerability):
    if any(r['EAL_VALT'].strip() and (not math.isfinite(float(r['EAL_VALT'])) or float(r['EAL_VALT']) < 0) for r in rows):
        raise ValueError('Invalid county EAL')
    contexts = [SimpleNamespace(vulnerability_profile={'nri': {'eal_total': float(r['EAL_VALT'])}})
                for r in rows if r['EAL_VALT'].strip()]
    # Reuse the scanner's existing EAL summation with one context per unique county.
    scanner_total = aggregate_vulnerability(None, contexts)[3]
    total = money(float(r['EAL_VALT']) for r in rows if r['EAL_VALT'].strip())
    if not math.isclose(scanner_total, total, rel_tol=1e-12, abs_tol=.02):
        raise ValueError('Scanner aggregate disagrees with decimal county reconciliation')
    hazards = []
    for code, name in HAZARDS.items():
        values = [float(r[code + '_EALT']) for r in rows if r[code + '_EALT'].strip()]
        if any(not math.isfinite(v) or v < 0 for v in values):
            raise ValueError('Invalid per-hazard county EAL')
        hazards.append({'hazard_id': code, 'hazard_name': name, 'metric': 'county_eal',
                        'value': money(values) if values else None, 'unit': 'USD/year',
                        'status': 'modeled' if values else 'unavailable', 'source_ref': 'fema-nri',
                        'contributing_counties': len(values), 'denominator': len(rows)})
    available = [h['value'] for h in hazards if h['value'] is not None]
    cell_count = sum(h['contributing_counties'] for h in hazards)
    return {'county_count': len(rows), 'county_eal': total if contexts else None,
            'climate_county_eal': money(float(r[h + '_EALT']) for r in rows for h in HAZARDS if r[h + '_EALT'].strip()) if available else None,
            'climate_county_eal_coverage': {'supported_cells': cell_count, 'possible_cells': len(rows) * len(HAZARDS),
                                            'status': 'unavailable' if not available else 'complete' if cell_count == len(rows) * len(HAZARDS) else 'partial'},
            'county_eal_coverage': len(contexts), 'county_top_hazards': top_five(hazards),
            'county_hazards': hazards}


def ncei_summary(events):
    unique = {}
    for row in events:
        identity = row['event_id']
        if not identity or (identity in unique and unique[identity] != row):
            raise ValueError('Missing/conflicting NCEI event ID')
        datetime.fromisoformat(row['begin_date'])
        datetime.fromisoformat(row['end_date'])
        if not math.isfinite(float(row['cpi_adjusted_cost'])) or float(row['cpi_adjusted_cost']) < 0:
            raise ValueError('Invalid NCEI cost')
        unique[identity] = row
    events = list(unique.values())
    by_year = defaultdict(list)
    for row in events:
        by_year[int(row['begin_date'][:4])].append(row)
    annual = [{'year': y, 'event_count': len(rs), 'amount': money(r['cpi_adjusted_cost'] for r in rs),
               'currency': 'USD', 'price_year': None, 'source_ref': 'ncei-bdd'} for y, rs in sorted(by_year.items())]
    return events, annual


def normalize_name(name):
    return ' '.join(re.findall(r'[a-z0-9]+', name.casefold()))


def deduplicate_awards(records):
    groups = defaultdict(list)
    for row in records:
        if not row.get('award_id'):
            raise ValueError('An award lacks a source ID')
        if not numeric(row.get('obligation')):
            raise ValueError('Invalid obligation')
        groups[row['award_id']].append(row)
    accepted, conflicts = [], []
    for award_id, group in sorted(groups.items()):
        signatures = {(r['tribe_id'], r['recipient_name_raw'], r['obligation'], r['start_date'], r['end_date']) for r in group}
        if len(signatures) != 1:
            conflicts.append(award_id)
        else:
            accepted.append(group[0])
    return accepted, {'input_records': len(records), 'unique_ids': len(groups),
                      'duplicate_records_removed': len(records) - len(groups),
                      'conflicting_ids_excluded': conflicts}


def funding_data(caches, registry, legacy, state_regions, programs):
    roster = {r['tribe_id']: r for r in registry}
    old = {r['tribe_id']: r for r in legacy}
    records = [dict(a, tribe_id=c['tribe_id']) for c in caches for a in c['awards']]
    awards, dedup = deduplicate_awards(records)
    published, excluded = [], defaultdict(list)
    for row in awards:
        tribe = roster.get(row['tribe_id'])
        if not tribe:
            excluded['outside_current_cohort'].append(row)
            continue
        names = [tribe['name'], *tribe.get('alternate_names', [])]
        if row['tribe_id'] in old:
            names += [old[row['tribe_id']]['name'], *old[row['tribe_id']].get('alternate_names', [])]
        matches = [name for name in names if normalize_name(row['recipient_name_raw']) == normalize_name(name)]
        if not matches:
            excluded['recipient_match_unverified'].append(row)
            continue
        published.append({
            'award_id': row['award_id'], 'tribe_id': row['tribe_id'],
            'recipient_name': row['recipient_name_raw'], 'recipient_match': 'exact_normalized_registry_name_or_alias',
            'match_evidence': matches[0], 'region_id': state_regions.get(tribe.get('states', [''])[0], 'other'),
            'amount': row['obligation'], 'currency': 'USD',
            'period_start': row['start_date'] or None, 'period_end': row['end_date'] or None,
            'program_id': row['program_id'], 'assistance_listing': row['cfda'],
            'awarding_agency': row['awarding_agency'], 'source_ref': 'usaspending', 'retrieved_at': None,
        })
    def totals(rows):
        return {'metric': 'recorded_award_level_obligations', 'amount': money(r['amount'] for r in rows),
                'currency': 'USD', 'award_count': len(rows), 'recipient_nation_count': len({r['tribe_id'] for r in rows}),
                'negative_adjustment_count': sum(r['amount'] < 0 for r in rows), 'source_ref': 'usaspending'}
    opportunities = [{
        'program_id': p['id'], 'name': p['name'], 'agency': p['agency'],
        'assistance_listing': p.get('cfda'), 'description': p.get('description'),
        'status': 'archived_program_context', 'budget_amount': None, 'notice_id': None,
        'deadline': None, 'current_open_status': 'unverified',
        'data_as_of': p.get('hot_sheets_status', {}).get('last_updated'),
        'source_ref': 'scanner-program-inventory',
        'official_search_url': 'https://www.grants.gov/search-grants',
        'eligibility': {'status': 'unknown', 'criteria': None,
                        'reason': 'Archived inventory does not establish current notice criteria or Nation eligibility.'},
    } for p in programs]
    cache_ids = {c['tribe_id'] for c in caches}
    return {
        'national': totals(published),
        'regions': [dict(region_id=key, **totals([a for a in published if a['region_id'] == key]))
                    for key in sorted(set(state_regions.values()))],
        'awards': published, 'opportunities': opportunities,
        'eligibility': {'status': 'not_determined', 'nation_count': len(registry),
                        'reason': 'No current notice or applicant-specific eligibility review was performed.'},
        'deduplication': dedup,
        'coverage': {'cache_recipient_files': len(caches), 'baseline_nations': len(registry),
                     'current_cohort_cache_matches': len(cache_ids & roster.keys()),
                     'cohort_ids_without_cache': sorted(roster.keys() - cache_ids),
                     'cache_ids_outside_cohort': sorted(cache_ids - roster.keys()),
                     'published_exact_match_awards': len(published),
                     'excluded': {reason: {'award_count': len(rows), 'amount': money(r['obligation'] for r in rows)}
                                  for reason, rows in excluded.items()},
                     'unmatched_source_awards': None, 'consortium_source_awards': None},
        'limitations': [
            'Historical award-level obligations are not available balances, annual spending, climate-only funding, or future awards.',
            'The cache query covers FY 2022–2026, but amounts are award-level totals and performance dates can lie outside that range.',
            'The cache does not preserve retrieval timestamps or transaction histories; no fiscal-year spending totals are reported.',
            'Only exact normalized formal-name or historical-alias matches are published. Housing authorities and other ambiguous relationships remain excluded pending review.',
            'Negative amounts are retained. Identical award IDs count once; conflicting IDs are excluded rather than chosen arbitrarily.',
            'Unmatched and consortium awards were excluded upstream; their totals are unavailable, not zero.',
            'Archived program entries are leads for current notice review. Budget, open status and eligibility remain unverified.',
        ],
    }


def build(source, data_root):
    sys.path.insert(0, str(source / 'src'))
    from tcr_downstream.packets.regional import RegionalAggregator
    from tcr_downstream.parity.oracle import sha256_of
    inputs = []
    def git(*args):
        return subprocess.run(['git', '-C', str(source), *args], check=True, capture_output=True,
                              text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0).stdout.strip()
    source_commit = git('rev-parse', 'HEAD')
    source_dirty = bool(git('status', '--porcelain=v1', '--untracked-files=normal'))
    package = tomllib.loads((source / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']

    def read(path):
        inputs.append(path)
        return load(path)

    reference = data_root / 'reference/data'
    output = data_root / 'output'
    frozen = data_root / 'frozen-corpus'
    registry_path = reference / 'tribal_registry.json'
    if digest(registry_path) != ROSTER_HASH:
        raise ValueError('Canonical roster changed; explicit reconciliation required')
    registry = read(registry_path)['tribes']
    old_registry = read(frozen / 'data/tribal_registry.json')['tribes']
    pin = read(source / 'data/manifests/cpri-frozen-baseline-manifest.json')
    manifest_path = frozen / 'data/cpre/parity/baseline-manifest.json'
    manifest = read(manifest_path)
    if digest(manifest_path) != pin['legacy_manifest_sha256']:
        raise ValueError('Frozen manifest disagrees with tracked source pin')
    dashboard = read(output / 'outputs/cpri_dashboard.json')
    if sha256_of(dashboard) != pin['dashboard_sha256']:
        raise ValueError('Dashboard differs from frozen baseline')
    roster_ids = {r['tribe_id'] for r in registry}
    if len(roster_ids) != len(registry) or {r['tribe_id'] for r in dashboard} != roster_ids:
        raise ValueError('Duplicate or mismatched cohort IDs')
    regions, state_regions = make_regions(read(reference / 'regional_config.json'))
    areas = read(reference / 'cpre/aiannh_geoid_crosswalk.json')['crosswalk']
    if digest(reference / 'cpre/aiannh_geoid_crosswalk.json') != pin['fixtures']['data/cpre/aiannh_geoid_crosswalk.json']:
        raise ValueError('Boundary crosswalk differs from frozen baseline')
    by_id = {r['tribe_id']: r for r in dashboard}
    nations, raw_hazards, profile_dates, profile_versions, formulas = [], {}, [], set(), set()
    for tribe in sorted(registry, key=lambda r: r['tribe_id']):
        identity = tribe['tribe_id']
        profile = read(output / 'data/cpre/cpri_profiles' / (identity + '.json'))
        if sha256_of(profile) != manifest['profiles'][identity]['sha256']:
            raise ValueError(f'Profile differs from frozen baseline: {identity}')
        hazard = read(reference / 'hazard_profiles' / (identity + '.json'))
        if profile['tribe_id'] != identity or hazard['tribe_id'] != identity:
            raise ValueError('Input identity mismatch')
        nri = hazard['sources']['fema_nri']
        raw_hazards[identity] = nri
        rows = hazard_rows(identity, profile)
        entry = by_id[identity]
        percentile = entry.get('percentile_rank')
        assessed = profile.get('assessment', {})
        nations.append({
            'tribe_id': identity, 'display_name': tribe['name'], 'states': tribe['states'],
            'region_id': state_regions.get(tribe['states'][0], 'other') if tribe['states'] else 'other',
            'percentile_rank': percentile, 'high_risk': bool(numeric(percentile) and percentile >= 80 and entry['coverage_status'] == 'evaluated'),
            'coverage_status': entry['coverage_status'], 'assessment_share': assessed.get('assessed_share'),
            'assessment_uncertainty': {
                'basis': assessed.get('basis'),
                'score_range_low': assessed.get('score_range_low'), 'score_range_high': assessed.get('score_range_high'),
                'tier_low': assessed.get('tier_low'), 'tier_high': assessed.get('tier_high'),
                'assessed_band': assessed.get('assessed_band'),
                'note': 'Source assessment ranges and simulation band are on the physical-score scale, not the percentile or individual hazard scale.',
            },
            'unassessed_hazards': assessed.get('not_assessed', []),
            'boundary_source': entry.get('boundary_source'), 'source_ref': 'scanner-cpri',
            'nri_resolution': nri.get('resolution'),
            'hazard_snapshot_at': hazard.get('generated_at'), 'hazards': rows, 'top_hazards': top_five(rows),
        })
        profile_dates.append(profile['computed_at'])
        profile_versions.add(profile['version'])
        formulas.add(profile['formula_spec']['formula_version'])

    county_path = reference / 'nri/NRI_Table_Counties.csv'
    inputs.append(county_path)
    from scanner_bundle import accept_county_snapshot
    counties, _county_snapshot = accept_county_snapshot(county_path)
    county_versions = sorted({r['NRI_VER'] for r in counties})
    if len({r['STCOFIPS'] for r in counties}) != len(counties):
        raise ValueError('Duplicate county records would double count costs')
    if any(r['EAL_VALT'].strip() and (not math.isfinite(float(r['EAL_VALT'])) or float(r['EAL_VALT']) < 0) for r in counties):
        raise ValueError('Invalid county EAL')

    def summary(key, ns, cs):
        result = {'region_id': key, 'nation_count': len(ns), 'top_hazards': frequency_rows(ns),
                  'high_risk_nations': sum(n['high_risk'] for n in ns),
                  **aggregate_counties(cs, RegionalAggregator._aggregate_vulnerability)}
        context_by_place = {}
        for nation in sorted(ns, key=lambda n: (n['boundary_source'].endswith('_proxy'), n['tribe_id'])):
            identity = nation['tribe_id']
            context_by_place.setdefault(areas[identity]['geoid'], SimpleNamespace(
                vulnerability_profile={'nri': raw_hazards[identity].get('composite', {})}))
        context_sum = RegionalAggregator._aggregate_vulnerability(None, list(context_by_place.values()))[3]
        result['scanner_context_eal'] = round(context_sum, 2) if context_by_place else None
        result['scanner_context_places'] = len(context_by_place)
        result['costs'] = [{
            'metric': 'county_expected_annual_loss_all_hazards', 'amount': result['county_eal'],
            'currency': 'USD', 'price_year': None, 'period_start': None, 'period_end': None,
            'source_version': county_versions, 'data_as_of': '2025-12',
            'price_year_reason': 'No common dollar price-year label is preserved in this cached table.',
            'period_reason': 'Annualized model expectation; hazard source observation periods differ. See FEMA technical documentation.',
            'geography': key, 'scope': 'All people, buildings and agriculture in the included counties; not Tribal losses.',
            'method': 'Each source county EAL_VALT counted once; existing scanner vulnerability aggregation; exclusive state regions.',
            'source_ref': 'fema-nri', 'uncertainty': None,
        }]
        return result

    national = summary('national', nations, counties)
    region_rows = []
    for key, region in regions.items():
        ns = [n for n in nations if n['region_id'] == key]
        cs = [c for c in counties if state_regions.get(c['STATEABBRV'], 'other') == key]
        if ns or cs:
            region_rows.append(dict(region, **summary(key, ns, cs)))
    if money(r['county_eal'] or 0 for r in region_rows) != national['county_eal']:
        raise ValueError('Exclusive regional county costs do not reconcile')
    national['climate_eal_regional_rounding_difference'] = money([
        national['climate_county_eal'], -money(r['climate_county_eal'] for r in region_rows)])
    ncei_dir = reference / 'reference/ncei_bdd'
    acquisition = read(ncei_dir / 'acquisition_manifest.json')
    event_path = ncei_dir / 'events.csv'
    inputs.append(event_path)
    if digest(event_path) != acquisition['checksums']['events.csv']:
        raise ValueError('NCEI cache checksum mismatch')
    with event_path.open(encoding='utf-8-sig', newline='') as handle:
        events, annual = ncei_summary(list(csv.DictReader(handle)))
    national['costs'].append({
        'metric': 'ncei_historical_event_loss', 'amount': money(e['cpi_adjusted_cost'] for e in events),
        'currency': 'USD', 'price_year': None,
        'price_basis': 'CPI-adjusted dollars as stored; cache does not retain the CPI base-year label.',
        'period_start': min(e['begin_date'] for e in events), 'period_end': max(e['end_date'] for e in events),
        'geography': 'United States', 'scope': 'All-U.S. billion-dollar weather/climate disasters; not Tribal losses.',
        'method': 'Sum one CPI-adjusted cost per unique event ID; not allocated to regions.',
        'source_ref': 'ncei-bdd', 'event_count': len(events), 'retrieved_at': acquisition['acquisition_timestamp'],
        'uncertainty': None,
    })
    for aggregate in [national, *region_rows]:
        aggregate['costs'].append({
            'metric': 'county_expected_annual_loss_climate_sensitive_hazards',
            'amount': aggregate['climate_county_eal'], 'currency': 'USD', 'price_year': None,
            'period_start': None, 'period_end': None, 'geography': aggregate['region_id'],
            'scope': 'Available EAL for 15 climate-sensitive hazards across all county residents/assets; not Tribal losses.',
            'method': 'Sum numeric per-hazard county EALT fields once per county; exclude earthquake, tsunami and volcano. Missing hazard cells remain outside coverage.',
            'source_version': county_versions, 'data_as_of': '2025-12', 'source_ref': 'fema-nri', 'uncertainty': None,
        })
    cache_paths = sorted((output / 'data/award_cache').glob('*.json'))
    caches = [read(p) for p in cache_paths]
    inventory = read(reference / 'program_inventory.json')['programs']
    funding = funding_data(caches, registry, old_registry, state_regions, inventory)
    inputs += [source / 'pyproject.toml', source / 'src/tcr_downstream/packets/regional.py', source / 'src/tcr_downstream/packets/context.py',
               source / 'src/tcr_downstream/packets/hazards.py', source / 'src/tcr_downstream/packets/awards.py',
               source / 'src/tcr_downstream/parity/oracle.py', Path(__file__)]
    private_manifest = [{'path': str(p), 'sha256': digest(p)} for p in sorted(set(inputs))]
    save(ROOT / 'work/risk/input-manifest.json', private_manifest)
    metadata = {
        'schema_version': '1.0.0', 'generated_at': datetime.now(timezone.utc).isoformat(),
        'data_as_of': max(profile_dates), 'source_tool': 'TCR policy scanner', 'package_version': package,
        'source_commit': source_commit, 'source_dirty': source_dirty,
        'input_manifest_sha256': digest(ROOT / 'work/risk/input-manifest.json'),
        'method_version': 'catf-risk-1.0', 'profile_schema_versions': sorted(profile_versions),
        'formula_versions': sorted(formulas), 'roster_sha256': ROSTER_HASH,
        'frozen_manifest_sha256': digest(manifest_path), 'frozen_at_head': pin['frozen_at_head'],
        'profile_generated_at_range': [min(profile_dates), max(profile_dates)],
        'source_snapshots': {
            'nri_counties': {'version': county_versions, 'sha256': digest(county_path)},
            'ncei_events': {'sha256': digest(event_path), 'retrieved_at': acquisition['acquisition_timestamp']},
            'cpri_dashboard': {'canonical_sha256': pin['dashboard_sha256'], 'profile_count': pin['profile_count']},
        },
    }
    risk_sources = SOURCES + [{'id': 'scanner-cpri', 'title': 'TCR scanner CPRI profiles, frozen formula 3.2.0',
                              'url': 'https://www.fema.gov/flood-maps/products-tools/national-risk-index',
                              'note': 'Derived scanner exposure indices using FEMA NRI and other public hazard inputs; this link describes the primary source, not the scanner formula.',
                              'rights': 'Public-source derived summary; TCR scanner methodology and source citations retained.'}]
    risk = dict(metadata, regions=region_rows, national=national, nations=nations, ncei_annual_series=annual,
                sources=risk_sources,
                coverage={'baseline_nations': len(nations), 'profile_count': len(nations),
                          'profile_pin_verified': True, 'dashboard_pin_verified': True,
                          'nations_with_five_hazards': sum(len(n['top_hazards']) == 5 for n in nations),
                          'nations_with_fewer_than_five': sum(len(n['top_hazards']) < 5 for n in nations),
                          'hazard_resolution_counts': dict(Counter(n['nri_resolution'] for n in nations)),
                          'source_counties': len(counties), 'ncei_events_with_state_lists': sum(bool(e['states_affected']) for e in events)},
                methods={
                    'nation_ranking': 'Descending supported CPRI hazard exposure score (0–1) from full profiles, with the assessment.assessed list as the availability gate; stable hazard-ID tie order; at most five. Missing is null, never zero.',
                    'excluded_hazards': ['ERQK: Earthquake', 'TSUN: Tsunami', 'VLCN: Volcanic activity'],
                    'aggregate_ranking': 'Count of Nations whose supported CPRI hazard score is in their top five; not a sum of scores or dollar estimates. County dollar ranking is a separate all-geography view.',
                    'regions': 'catf-scanner-regions-1: seven scanner geographic state groups plus California and Other. Assign each Nation once by first recorded registry state; counties once by state. This is a presentation grouping, not BIA/NCAI/ATNI jurisdiction.',
                    'high_risk': {'metric': 'scanner CPRI physical percentile_rank', 'threshold': 80, 'operator': '>=',
                                  'required_coverage': 'evaluated', 'meaning': 'Upper cohort quintile for research follow-up; not a probability or eligibility decision.'},
                    'scanner_context_eal': 'Existing scanner sum of NRI composite EAL, one representative per boundary GEOID, proxy last. County/tract source contexts can overlap: this is an index-like sum of place contexts, not aggregate Tribal loss, and regional sums must not be added.',
                    'county_eal': 'Sum FEMA EAL_VALT once per unique county using the existing scanner aggregation function. All 18 hazards included in this cost total; 15 climate-sensitive hazards in county ranking. Regions reconcile to national.',
                    'ncei_annual_series': 'Group by event begin year, count unique IDs once; preserve source CPI-adjusted amounts. No regional event allocation.',
                },
                reconciliation={'legacy_registry_count': len(old_registry), 'current_registry_count': len(registry),
                                'removed_legacy_ids': sorted({r['tribe_id'] for r in old_registry} - roster_ids),
                                'added_current_ids': sorted(roster_ids - {r['tribe_id'] for r in old_registry}),
                                'economic_allocation_profiles_used': False},
                limitations=[
                    'Development snapshot, not a certified risk assessment. Review source coverage and local knowledge before decisions.',
                    'Nation hazard values are modeled exposure indices, not probabilities, measured damages or monetary losses.',
                    'EAL is an annualized expectation, not a prediction of next year, historical damage, or a climate-change attribution estimate.',
                    'Dollar totals from all counties describe all residents and assets. They must never be labeled Tribal losses.',
                    'Missing EAL cells and unassessed hazards remain gaps; supported zero values remain zero.',
                    'Avalanche and landslide are climate-sensitive hazards with multiple causes; inclusion does not attribute all loss to climate change.',
                    'CPRI ranks are cohort-relative and use differing assessment coverage. Coastal change, sea-level rise and permafrost remain unassessed in this snapshot.',
                    'The cached NCEI record ends in 2024. Only 55 event rows have state lists; regional event-cost allocation is unsupported.',
                    'The cached dollar series does not preserve its inflation base-year label; price_year is null rather than inferred.',
                ])
    funding = dict(metadata, **funding, sources=SOURCES + [{
        'id': 'scanner-program-inventory', 'title': 'Archived scanner program inventory',
        'url': 'https://www.grants.gov/search-grants', 'rights': 'Public program descriptions; current notices must be checked.'}])
    funding['data_as_of'] = None
    funding['method_version'] = 'catf-funding-1.0'
    funding['data_as_of_reason'] = 'Award cache omits retrieval dates; archived program dates are recorded per entry.'
    save(ROOT / 'site/data/risk.json', risk)
    save(ROOT / 'site/data/funding.json', funding)
    print(json.dumps({'nations': len(nations), 'five_hazards': risk['coverage']['nations_with_five_hazards'],
                      'county_eal': national['county_eal'], 'ncei_cost': national['costs'][1]['amount'],
                      'funding': funding['national'], 'input_manifest_sha256': metadata['input_manifest_sha256']}))


def status_summary(nations):
    return [{'hazard_id': code, 'hazard_name': name, 'denominator': len(nations),
             'contributing_nations': sum(h['status'] == 'modeled' for n in nations for h in n['hazards'] if h['hazard_id'] == code),
             'status_counts': dict(Counter(h['status'] for n in nations for h in n['hazards'] if h['hazard_id'] == code))}
            for code, name in PROFILE_HAZARDS.items()]


MC_NOTE = ('10,000 deterministic-seed Latin hypercube samples of triangular hazard inputs: mode=score, '
           'limits=max(0,0.7*score), min(1,1.3*score). Hazard sensitivity only; CEM/IIG are not sampled '
           'despite the raw layers_sampled label. No cross-hazard correlation model. Not event probabilities, '
           'climate-model spread, or complete uncertainty for the final index.')


def temporal_rows(record):
    grid = record['profile'].get('temporal', {}).get('grid', {})
    rows = []
    for support in record['temporal_support']:
        cell = grid.get(support['horizon'], {}).get(support['scenario'], {})
        raw = cell.get('cpri_physical')
        supported = support['status'] in ('baseline_assessed', 'forward_supported')
        rows.append(dict(support, physical_score=raw if supported and numeric(raw) else None,
                         raw_physical_score=raw if numeric(raw) else None,
                         source_basis='baseline_assessment' if support['horizon'] == 'baseline' else 'forward_change_factors_2080_ssp370',
                         reason=('At least one evaluated forward factor; not every hazard is projected.' if support['status'] == 'forward_supported'
                                 else 'Baseline assessment.' if supported else 'Retained cell-level support is insufficient; raw values may be baseline fallbacks.'),
                         monte_carlo=cell.get('monte_carlo') if supported else None,
                         raw_monte_carlo_present=bool(cell.get('monte_carlo'))))
    return rows


def integrate_bundle(bundle, data_root):
    from scanner_bundle import accept_county_snapshot, verify_bundle
    accepted = verify_bundle(bundle, data_root)
    previous_path = ROOT / 'work/risk/previous-risk.json'
    previous_hash = '1c534f25a71615b51393d5c015816a2f5cbaa4a9da4b3f1cb87a4b64d046c475'
    if not previous_path.exists():
        original = ROOT / 'site/data/risk.json'
        if digest(original) != previous_hash:
            raise ValueError('Previous public snapshot identity differs; explicit reconciliation needed')
        previous_path.write_bytes(original.read_bytes())
    if digest(previous_path) != previous_hash:
        raise ValueError('Previous accepted snapshot backup changed')
    previous = load(previous_path)
    result = load(previous_path)
    counties, county_snapshot = accept_county_snapshot(data_root / 'reference/data/nri/NRI_Table_Counties.csv')
    nations_by_id = {n['tribe_id']: n for n in result['nations']}
    for record in accepted['nations']:
        identity = record['tribe_id']
        profile = accepted['profiles'][identity]
        nation = nations_by_id[identity]
        primary = profile['primary_cpri']
        # Frozen priority stays fixed; a numerically different rerun needs a separate decision.
        if nation['percentile_rank'] != primary['percentile_rank']:
            raise ValueError('Frozen planning percentile changed')
        nation.pop('top_hazards', None)
        nation['hazards'] = hazard_rows(identity, profile)
        nation['source_profile_sha256'] = record['source']['sha256']
        nation['source_provenance'] = {k: profile['provenance'].get(k) for k in ('origin', 'license', 'coverage_status', 'confidence')}
        nation['source_provenance']['confidence_meaning'] = 'Source coverage/proxy label, not calibrated confidence.'
        nation['computed_at'] = profile['computed_at']
        nation['temporal'] = temporal_rows(record)
        nation['module_statuses'] = {k: profile.get(k, []) for k in ('modules_failed', 'modules_stubbed', 'modules_skipped')}
        nation['forward_change_factors'] = profile.get('forward_change_factors', {})
        nation['assessment_uncertainty'].update({
            'missing_data_bounds_meaning': 'Source physical-score coverage bounds under unassessed-hazard extremes; not a probability interval.',
            'monte_carlo_meaning': MC_NOTE,
            'frozen_composite_includes_placeholder': any(h['status'] == 'placeholder' for h in nation['hazards']),
        })
        for hazard in nation['hazards']:
            hazard['source_profile_sha256'] = record['source']['sha256']
    aggregate = lambda _, contexts: (None, None, None, sum(c.vulnerability_profile['nri']['eal_total'] for c in contexts))
    for summary in [result['national'], *result['regions']]:
        key = summary['region_id']
        ns = result['nations'] if key == 'national' else [n for n in result['nations'] if n['region_id'] == key]
        cs = counties if key == 'national' else [c for c in counties if c['STATEABBRV'] in summary['states']]
        summary.pop('top_hazards', None)
        summary['hazard_statuses'] = status_summary(ns)
        summary.update(aggregate_counties(cs, aggregate))
        for cost in summary['costs']:
            if cost['source_ref'] == 'fema-nri':
                cost['source_sha256'] = county_snapshot['sha256']
                cost['source_version'] = county_snapshot['version']
                if 'climate_sensitive' in cost['metric']:
                    cost['amount'] = summary['climate_county_eal']
                    cost['coverage'] = summary['climate_county_eal_coverage']
    result['previous_snapshot'] = {k: previous[k] for k in ('source_commit', 'source_dirty', 'input_manifest_sha256', 'frozen_manifest_sha256', 'frozen_at_head', 'data_as_of', 'method_version', 'source_snapshots')}
    result['previous_snapshot']['public_risk_sha256'] = previous_hash
    for historical_key in ('frozen_manifest_sha256', 'frozen_at_head'):
        result.pop(historical_key, None)
    handoff = accepted['handoff']
    result.update(schema_version='2.0.0', method_version='catf-risk-2.0',
                  generated_at=datetime.now(timezone.utc).isoformat(),
                  data_as_of=max(n['computed_at'] for n in result['nations']),
                  source_commit=handoff['calculation_revision'], source_dirty=None,
                  calculation_revision=handoff['calculation_revision'], export_revision=handoff['export_revision'])
    result['profile_generated_at_range'] = [min(n['computed_at'] for n in result['nations']), result['data_as_of']]
    result['accepted_bundle'] = {'schema_version': accepted['manifest']['schema_version'], 'accepted_at': handoff['verified_at'],
                               'hashes': accepted['files'], 'calculation_revision': handoff['calculation_revision'],
                               'export_revision': handoff['export_revision'], 'manifest_source_head': accepted['manifest']['source_head'],
                               'formula_and_exporter_hashes': [{'component': r['path'].split('/')[-1], 'sha256': r['sha256']} for r in accepted['manifest']['formula_and_exporter_hashes']],
                               'comparison': {'numerically_changed_nations': 0, 'changed_numeric_fields': 0, 'added_ids': 0, 'removed_ids': 0}}
    result['source_snapshots']['nri_counties'] = county_snapshot
    result['source_snapshots']['cpri_dashboard'] = {'sha256': accepted['files']['canonical_dashboard'], 'profile_count': 575}
    result['source_dirty_reason'] = 'Accepted calculation receipt records the revision but not historical dirty state; exact formula/exporter hashes are retained separately.'
    result['coverage'].pop('nations_with_five_hazards', None)
    result['coverage'].pop('nations_with_fewer_than_five', None)
    result['coverage']['placeholder_hazard_rows'] = sum(h['status'] == 'placeholder' for n in result['nations'] for h in n['hazards'])
    result['coverage']['temporal_status_counts'] = dict(Counter(t['status'] for n in result['nations'] for t in n['temporal']))
    result['methods'].pop('nation_ranking', None)
    result['methods'].pop('aggregate_ranking', None)
    result['methods'].update(hazard_status='All nine hazard states; unlike hazard indexes are not severity-comparable. Counts describe coverage only.',
                             monte_carlo=MC_NOTE, temporal_support='Only baseline_assessed and forward_supported cells contribute. Future support applies only to 2080/SSP3-7.0 with at least one evaluated factor; 1.0 is valid no-change support.',
                             frozen_priority='Composite percentiles/high_risk and dependent planning queue remain frozen, including source placeholder effects; no incidental reranking.',
                             composite='Final percentile-normalized CPRI is ordinal screening position, not probability, money or ratio scale.')
    result['limitations'] += ['Explicit drought placeholder floors are excluded from supported hazard values/counts but remain in the unchanged source composites.',
                              'Hawaii has no Nation entry in the canonical cohort; county context does not establish a Nation risk or climate projection.',
                              'Alaska county-equivalent contexts do not measure community, access, subsistence, ice, erosion or permafrost consequences completely. Missing hazard support is not low risk.']
    for key, filename in [('ecoregions', 'ecoregions.json'), ('advocacy_regions', 'advocacy_regions.json')]:
        source = load(bundle / filename)
        public = {'scheme': source['scheme'], 'interpretation': source['interpretation'], 'regions': []}
        for region in source['regions']:
            # Regional raw hazard medians include placeholders; publish corrected coverage only.
            row = {k: v for k, v in region.items() if k not in ('hazards',)}
            row['hazard_statuses'] = status_summary([nations_by_id[i] for i in row['member_nation_ids']])
            row['source_category'] = 'water' if row['region_id'] == '0.0.0' and key == 'ecoregions' else 'ecoregion' if key == 'ecoregions' else 'scanner_advocacy_region'
            public['regions'].append(row)
        result[key] = public
    private_manifest = {'bundle': str(bundle), 'accepted_files': accepted['files'],
                        'profiles': {n['tribe_id']: n['source']['sha256'] for n in accepted['nations']},
                        'previous_public_sha256': previous_hash, 'county_snapshot': county_snapshot,
                        'adapter_sha256': digest(Path(__file__)), 'verifier_sha256': digest(ROOT / 'scripts/scanner_bundle.py')}
    save(ROOT / 'work/risk/accepted-input-manifest.json', private_manifest)
    result['input_manifest_sha256'] = digest(ROOT / 'work/risk/accepted-input-manifest.json')
    serialized = json.dumps(result)
    if re.search(r'(?<![A-Za-z])[A-Za-z]:[\\/]', serialized) or any('"' + key + '"' in serialized for key in ('tek_audit', 'processing_history', 'source_path')):
        raise ValueError('Private field/path in public projection')
    save(ROOT / 'site/data/risk.json', result)
    print(json.dumps({'nations': len(result['nations']), 'placeholder_rows': result['coverage']['placeholder_hazard_rows'],
                      'temporal_status_counts': result['coverage']['temporal_status_counts'], 'input_manifest_sha256': result['input_manifest_sha256']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('I:/tcr-policy-scanner'))
    parser.add_argument('--data-root', type=Path, default=Path('I:/data/tcr-policy-scanner'))
    parser.add_argument('--accepted-bundle', type=Path, help='Deliberate accepted-schema risk-only import; funding/plans unchanged.')
    args = parser.parse_args()
    if args.accepted_bundle:
        integrate_bundle(args.accepted_bundle, args.data_root)
    else:
        build(args.source, args.data_root)
