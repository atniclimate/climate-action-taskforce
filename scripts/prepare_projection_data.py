"""Prepare private, checkpointed CATF climate derivatives from explicit public files.

No scanner imports or browser computation. Public projection is a separate step.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pyarrow.parquet as pq

METHOD = 'catf-paired-annual-v1'
SCHEMA = 'catf-climate-v1'
NATIVE_COMMIT = 'b8b55ca0e172a4694e4212108309621d8873615d'
NATIVE = 'https://data.native-resilience.com/projections/'
NCCV = 'https://apps.usgs.gov/nccv/cmip6_loca2_20260203/json_20231011/'
SCENARIOS = ('ssp245', 'ssp370')
YEARS = list(range(1950, 2101))
BASELINE = (1995, 2014)
WINDOWS = ((2020, 2039), (2040, 2059), (2070, 2089))
MODELS = ('ACCESS-ESM1-5', 'CNRM-ESM2-1', 'EC-Earth3', 'GFDL-ESM4',
          'GISS-E2-1-G', 'MIROC6', 'MPI-ESM1-2-HR', 'MRI-ESM2-0')
METRICS = {
    'temp_mean': {'label': 'Annual mean temperature', 'source_label': 'Average Temperature [degF]',
                  'source_unit': 'degF', 'unit': 'degC', 'definition': 'Mean of provider daily area-mean air temperature.'},
    'pr_annual': {'label': 'Annual precipitation', 'source_label': 'Annual Precipitation [in]',
                  'source_unit': 'in', 'unit': 'mm', 'definition': 'Sum of provider daily area-mean precipitation for each year.'},
}
LIMITATIONS = [
    'Source area is a statistical or administrative climate support, not a statement of sovereign territory.',
    'Approximately 25 km NEX-GDDP-CMIP6 source resolution does not imply local detail for small areas.',
    'Annual tables omit realization IDs and calendar names; these are unknown, not inferred.',
    'Provider annual metrics ignore missing daily values; n_days counts rows, not valid observations. Daily valid-cell/day coverage is not supplied.',
    'Equal-weight model spread is descriptive, not a confidence interval or scenario probability.',
    'Annual pathways retain simulated interannual variability and are not year-specific weather forecasts.',
]


def sha_bytes(body):
    return hashlib.sha256(body).hexdigest()


def fingerprint(value):
    return sha_bytes(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8') + b'\n'
    json.loads(body)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(body)
    temporary.replace(path)
    return sha_bytes(body)


def acquire(raw, name, url, expected=None):
    """A frozen local receipt is reused; corrupt or changed cached bytes fail closed."""
    path = raw / name
    receipt_path = raw / (name + '.receipt.json')
    if path.exists() and receipt_path.exists():
        receipt = read_json(receipt_path)
        body = path.read_bytes()
        if receipt['url'] != url or sha_bytes(body) != receipt['sha256']:
            raise ValueError('cached input does not match its acquisition receipt: ' + name)
    else:
        req = Request(url, headers={'User-Agent': 'CATF-public-climate-source-preparation/1.0'})
        with urlopen(req, timeout=60) as response:
            body = response.read()
            receipt = {'url': url, 'sha256': sha_bytes(body), 'bytes': len(body),
                       'acquired_at': datetime.now(timezone.utc).isoformat(),
                       'last_modified': response.headers.get('Last-Modified')}
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + '.tmp')
        tmp.write_bytes(body)
        tmp.replace(path)
        atomic_json(receipt_path, receipt)
    if expected and (len(body) != expected['size'] or
                     (expected.get('hash') and receipt['sha256'] != expected['hash'])):
        raise ValueError('download differs from pinned provider manifest: ' + name)
    return path, receipt


def quantiles(values):
    """Linear interpolation at (n-1)*p (Hyndman-Fan type 7)."""
    values = sorted(values)
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError('quantile values must be finite and nonempty')
    result = {}
    for key, probability in (('lower', .1), ('median', .5), ('upper', .9)):
        index = (len(values) - 1) * probability
        lo = math.floor(index)
        hi = math.ceil(index)
        result[key] = round(values[lo] + (values[hi] - values[lo]) * (index - lo), 4)
    return result


def canonical(value, metric, *, change=False):
    if metric == 'temp_mean':
        return value * 5 / 9 if change else (value - 32) * 5 / 9
    if metric == 'pr_annual':
        return value * 25.4
    raise ValueError('unsupported metric')


def derive_metric(rows, metric, metadata):
    """Require complete paired member support before calculating any spread."""
    definition = METRICS[metric]
    if metadata['label'] != definition['source_label'] or int(metadata['metric_version']) != 1:
        raise ValueError('unknown source units or metric version')
    selected = [r for r in rows if r['metric_id'] == metric and r['scenario'] in SCENARIOS]
    result = {'metric_id': metric, **definition, 'metric_version': 1,
              'value_kind': 'change', 'baseline_id': '1995-2014', 'baseline': list(BASELINE),
              'statistic': 'median_of_paired_member_changes', 'quantile_method': 'linear_type7',
              'spread': '10th–90th percentile of equal-weight model changes after each model baseline is subtracted',
              'weighting': 'equal_model_weight; equal_year_weight_within_period',
              'provider_fit_status': None, 'provider_fit_status_reason': 'annual member values; no smoothing fit used',
              'calendar': None, 'calendar_reason': 'not retained in provider annual table',
              'realization': None, 'realization_reason': 'not retained in provider annual table',
              'expected_model_count': len(MODELS), 'expected_years': 151}
    if not selected:
        return {**result, 'status': 'unavailable', 'reason': 'metric_not_supplied', 'series': {}, 'windows': []}, []
    cells = {}
    for row in selected:
        key = (row['model'], row['scenario'], int(row['Year']))
        if key in cells:
            raise ValueError('duplicate model/scenario/year')
        if row['model'] not in MODELS or int(row['metric_version']) != 1:
            raise ValueError('unrecognized member or metric version')
        cells[key] = row
    included, excluded, baselines = [], {}, {}
    for model in MODELS:
        support = [cells.get((model, scenario, year)) for scenario in SCENARIOS for year in YEARS]
        if any(r is None or r['value'] is None or not math.isfinite(r['value']) or
               r['n_days'] not in (360, 365, 366) for r in support):
            excluded[model] = 'missing_or_invalid_annual_support'
            continue
        if metric == 'pr_annual' and any(r['value'] < 0 for r in support):
            excluded[model] = 'negative_precipitation'
            continue
        if any(abs(cells[(model, 'ssp245', y)]['value'] - cells[(model, 'ssp370', y)]['value']) > 1e-8
               for y in range(1950, 2015)):
            excluded[model] = 'historical_scenario_copies_disagree'
            continue
        baselines[model] = statistics.fmean(cells[(model, 'ssp245', y)]['value'] for y in range(BASELINE[0], BASELINE[1] + 1))
        included.append(model)
    result.update(model_ids=included, model_count=len(included), excluded_models=excluded,
                  valid_annual_rows=len(included) * len(YEARS) * 2,
                  expected_annual_rows=len(MODELS) * len(YEARS) * 2)
    if not included:
        return {**result, 'status': 'unavailable', 'reason': 'no_complete_paired_members', 'series': {}, 'windows': []}, []
    result['status'] = 'available' if len(included) == len(MODELS) else 'partial'
    result['n_days_observed'] = sorted({int(cells[(m, s, y)]['n_days']) for m in included for s in SCENARIOS for y in YEARS})
    result['baseline_level'] = quantiles([canonical(baselines[m], metric) for m in included])
    result['series'] = {}
    for scenario in SCENARIOS:
        summary = [quantiles([canonical(cells[(m, scenario, y)]['value'] - baselines[m], metric, change=True)
                              for m in included]) for y in YEARS]
        result['series'][scenario] = {'years': YEARS, 'model_count': len(included),
                                     **{k: [q[k] for q in summary] for k in ('lower', 'median', 'upper')}}
    members, windows = [], []
    for start, end in WINDOWS:
        scenarios = {}
        for scenario in SCENARIOS:
            changes = []
            for model in included:
                future = statistics.fmean(cells[(model, scenario, y)]['value'] for y in range(start, end + 1))
                change = canonical(future - baselines[model], metric, change=True)
                changes.append(change)
                members.append({'model': model, 'metric_id': metric, 'scenario': scenario,
                                'period': [start, end], 'baseline': list(BASELINE),
                                'baseline_level': canonical(baselines[model], metric),
                                'period_level': canonical(future, metric), 'change': change,
                                'valid_years': 20, 'expected_years': 20, 'unit': definition['unit']})
            scenarios[scenario] = {**quantiles(changes), 'model_count': len(included), 'valid_years_per_model': 20}
        windows.append({'period_id': f'{start}-{end}', 'period': [start, end], 'scenarios': scenarios})
    result['windows'] = windows
    return result, members


def prepare_native(land, raw, out, metadata, dependencies, manifest_paths):
    area_id = land['land_id']
    checkpoint_path = out / 'checkpoints' / (area_id + '.json')
    area_path = out / 'areas' / (area_id + '.json')
    base_key = {**dependencies, 'land': land, 'parameters': {'metrics': list(METRICS), 'baseline': BASELINE,
                'windows': WINDOWS, 'scenarios': SCENARIOS, 'models': MODELS, 'weighting': 'equal-model-equal-year'}}
    source_path = f'data/annual/land_id={area_id}/part-0.parquet'
    try:
        if source_path not in manifest_paths:
            result = {'status': 'missing', 'reason': 'annual_file_absent_from_provider_manifest'}
            cache_key = fingerprint(base_key)
        else:
            path, receipt = acquire(raw, area_id + '.annual.parquet', NATIVE + source_path, manifest_paths[source_path])
            cache_key = fingerprint({**base_key, 'input_sha256': receipt['sha256']})
            if checkpoint_path.exists() and area_path.exists():
                old = read_json(checkpoint_path)
                if (old.get('cache_key') == cache_key and old['status'] in ('available', 'partial', 'invalid', 'missing', 'unavailable')
                        and sha_bytes(area_path.read_bytes()) == old.get('output_sha256')):
                    return {**old, 'resumed': True}
            rows = pq.read_table(path, filters=[('metric_id', 'in', list(METRICS)),
                                               ('scenario', 'in', list(SCENARIOS))]).to_pylist()
            metrics, members = {}, []
            for metric in METRICS:
                try:
                    metrics[metric], detail = derive_metric(rows, metric, metadata[metric])
                    members.extend(detail)
                except (ValueError, KeyError, TypeError) as error:
                    metrics[metric] = {'metric_id': metric, 'status': 'invalid', 'reason': str(error)}
            states = [m['status'] for m in metrics.values()]
            status = 'available' if all(s == 'available' for s in states) else 'partial' if any(s in ('available', 'partial') for s in states) else 'invalid'
            result = {'schema_version': SCHEMA, 'method_version': METHOD, 'area_id': area_id,
                      'name': land['name'], 'family': 'native-nex', 'status': status,
                      'geometry': {'GEOID': land['GEOID'], 'COMPTYP': land['COMPTYP'],
                                   'vintage': land['census_year'], 'provider_hash': land['geom_hash']},
                      'source': receipt, 'dependency_hashes': dependencies, 'cache_key': cache_key,
                      'metrics': metrics, 'limitations': LIMITATIONS}
            atomic_json(out / 'members' / (area_id + '.json'), {'area_id': area_id, 'input_sha256': receipt['sha256'], 'rows': members})
        result.update(area_id=area_id, cache_key=cache_key)
        output_hash = atomic_json(area_path, result)
        checkpoint = {'area_id': area_id, 'status': result['status'], 'cache_key': cache_key,
                      'output_sha256': output_hash, 'bytes': area_path.stat().st_size,
                      'metric_status': {m: v['status'] for m, v in result.get('metrics', {}).items()}}
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        status = 'blocked' if isinstance(error, (HTTPError, URLError, TimeoutError, OSError)) else 'invalid'
        cache_key = fingerprint(base_key)
        # Replace old success with an absence, so changed-input failure cannot publish stale values.
        failure = {'area_id': area_id, 'status': status, 'reason': str(error), 'cache_key': cache_key}
        output_hash = atomic_json(area_path, failure)
        checkpoint = {**failure, 'output_sha256': output_hash, 'bytes': area_path.stat().st_size, 'metric_status': {}}
    atomic_json(checkpoint_path, checkpoint)
    return checkpoint


def parse_regional(data, name, kind, receipt):
    if data['variable_id'] != 'tas' or data['variable_units'] != 'deg_C':
        raise ValueError('regional adapter requires provider mean temperature in deg_C')
    if data['timeseries']['years'] != YEARS:
        raise ValueError('regional annual years differ from 1950-2100')
    series = {}
    for scenario in data['timeseries']['scenarios']:
        sid = scenario['scenario_id']
        if sid not in SCENARIOS:
            continue
        annual = next(m for m in scenario['months'] if m['month_id'] == 'ann')
        if (annual['base_period_label'] != '1981-2010' or scenario['mid_label'] != 'median'
                or scenario['lower_upper_label'] != '10th to 90th percentile'):
            raise ValueError('unrecognized provider baseline/statistic')
        members = [m['model_id'] for m in next(s for s in data['climatology'][0]['scenarios'] if s['scenario_id'] == sid)['model_data'] if not m['is_mean_model']]
        arrays = {k: annual['ensemble_anom_' + field] for k, field in [('lower', 'lower'), ('median', 'middle'), ('upper', 'upper')]}
        for k, values in arrays.items():
            if len(values) != 151:
                raise ValueError('wrong regional array length')
            arrays[k] = [None if v is None or v == -9999 else v for v in values]
        for values in zip(arrays['lower'], arrays['median'], arrays['upper']):
            if all(v is not None for v in values) and not (all(math.isfinite(v) for v in values) and values[0] <= values[1] <= values[2]):
                raise ValueError('invalid regional bounds')
        series[sid] = {'years': YEARS, **arrays, 'model_count': len(members), 'model_ids': members,
                       'missing_years': sum(any(v is None for v in x) for x in zip(*arrays.values()))}
    if set(series) != set(SCENARIOS):
        raise ValueError('regional paired SSPs absent')
    return {'schema_version': SCHEMA, 'family': 'usgs-nccv-loca2', 'area_id': data['geo_id'],
            'name': name, 'kind': kind, 'status': 'available', 'source': receipt,
            'metrics': {'temp_mean': {'metric_id': 'temp_mean', 'label': 'Annual mean temperature',
                        'unit': 'degC', 'value_kind': 'change', 'baseline_id': '1981-2010', 'baseline': [1981, 2010],
                        'status': 'available', 'statistic': 'provider_annual_model_median', 'series': series,
                        'spread': 'Provider 10th–90th percentile of annual model temperature anomalies',
                        'windows': [], 'provider_fit_status': None,
                        'provider_fit_status_reason': 'provider annual series; no CATF fit'}},
            'limitations': ['County/watershed context is not a Nation or ecological-cohort climate average.',
                            'Scenario model memberships differ (24 SSP245; 23 SSP370); difference is not solely a controlled scenario effect.',
                            'Served summary revision October 2023; directory date 2026 is not evidence of corrected 2024 precipitation.',
                            'LOCA2 regional coverage is CONUS; Alaska and Hawaii are outside this product.']}


def prepare_regional(raw, out):
    contexts = [('county', 'US53073'), ('huc4', 'HUC1707'), ('huc4', 'HUC1501'), ('huc4', 'HUC0102')]
    records = []
    for kind, geo_id in contexts:
        config = read_json(raw / ('county-config.json' if kind == 'county' else 'watershed-config.json'))
        regions = config['level2_region_conf']['regions']
        if kind == 'county':
            name = next(f"{r['name']} County, {state['name']}" for state in regions for r in state['sub_regions'] if r['geo_id'] == geo_id)
        else:
            name = next(r['name'] for r in regions if r['geo_id'] == geo_id)
        try:
            path, receipt = acquire(raw, geo_id + '_tas.json.gz', NCCV + f'{kind}/charts/{geo_id}/{geo_id}_tas_chart_metric.json.gz')
            result = parse_regional(json.loads(gzip.decompress(path.read_bytes())), name, kind, receipt)
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
            result = {'area_id': geo_id, 'name': name, 'kind': kind, 'family': 'usgs-nccv-loca2', 'status': 'blocked', 'reason': str(error)}
        path = out / 'regional' / (geo_id + '.json')
        output_hash = atomic_json(path, result)
        records.append({'area_id': geo_id, 'name': name, 'kind': kind, 'status': result['status'], 'sha256': output_hash, 'bytes': path.stat().st_size})
    return records


def account_nations(registry, links, results):
    roster = registry['tribes']
    ids = {r['tribe_id'] for r in roster}
    mapped = {n['tribe_id']: n for n in links['nations']}
    if len(ids) != len(roster) or len(mapped) != len(links['nations']) or set(mapped) != ids:
        raise ValueError('Nation crosswalk must account for the exact pinned registry IDs once')
    areas = {r['area_id']: r for r in results}
    records = []
    for nation in roster:
        link = mapped[nation['tribe_id']]
        area_ids = sorted(set(link['area_ids']))
        metrics = {}
        for metric in METRICS:
            states = {a: areas.get(a, {}).get('metric_status', {}).get(metric, areas.get(a, {}).get('status', 'unavailable')) for a in area_ids}
            good = [a for a, state in states.items() if state in ('available', 'partial')]
            status = 'unmapped' if not area_ids else 'available' if all(s == 'available' for s in states.values()) else 'partial' if good else 'blocked' if 'blocked' in states.values() else 'unavailable'
            metrics[metric] = {'status': status, 'area_status': states, 'supported_area_ids': good,
                               'scope': 'proxy_source_area_context' if link['proxy'] else 'associated_source_area',
                               'missing_reason': link['missing_reason'] if not area_ids else None}
        records.append({**link, 'climate': metrics, 'requires_area_selection': len(area_ids) > 1})
    totals = {}
    for metric in METRICS:
        supported = [n for n in records if n['climate'][metric]['supported_area_ids']]
        totals[metric] = {'nation_status': dict(Counter(n['climate'][metric]['status'] for n in records)),
                          'supported_nations': len(supported),
                          'associated_nations': sum(not n['proxy'] for n in supported),
                          'proxy_context_nations': sum(n['proxy'] for n in supported),
                          'distinct_supported_areas': len({a for n in supported for a in n['climate'][metric]['supported_area_ids']})}
    return {'schema_version': SCHEMA, 'registry_sha256': links['registry_sha256'],
            'nation_count': len(records), 'nations': records, 'metrics': totals,
            'counting_note': 'Nation counts and distinct climate areas are different denominators; shared areas are processed once; proxy context is not Nation-mean climate.'}


def write_summary(out, results, coverage):
    counts = Counter(a for n in coverage['nations'] for a in set(n['area_ids']))
    path = out / 'summary.csv'
    with path.with_suffix('.csv.tmp').open('w', encoding='utf-8', newline='') as stream:
        fields = ['area_id', 'area_name', 'family', 'metric_id', 'unit', 'baseline', 'period', 'scenario',
                  'median_change', 'p10_change', 'p90_change', 'model_count', 'status', 'linked_nations', 'input_sha256']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for entry in sorted(results, key=lambda r: r['area_id']):
            area = read_json(out / 'areas' / (entry['area_id'] + '.json'))
            for metric_id, metric in area.get('metrics', {}).items():
                for window in metric.get('windows', []):
                    for scenario, summary in window['scenarios'].items():
                        writer.writerow(dict(zip(fields, [area['area_id'], area['name'], area['family'], metric_id,
                            metric['unit'], metric['baseline_id'], window['period_id'], scenario, summary['median'],
                            summary['lower'], summary['upper'], summary['model_count'], metric['status'], counts[area['area_id']], area['source']['sha256']])))
    path.with_suffix('.csv.tmp').replace(path)
    return {'sha256': sha_bytes(path.read_bytes()), 'bytes': path.stat().st_size}


def prepare(args):
    start = time.monotonic()
    out, raw = args.output, args.output / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    inputs = [('lands.parquet', NATIVE + 'data/lands.parquet'),
              ('variables.parquet', NATIVE + 'data/variables.parquet'),
              ('projections-manifest.json', NATIVE + 'projections-manifest.json'),
              ('native-readme.md', f'https://raw.githubusercontent.com/native-resilience/projections/{NATIVE_COMMIT}/README.md'),
              ('native-metrics.R', f'https://raw.githubusercontent.com/native-resilience/projections/{NATIVE_COMMIT}/R/metrics.R'),
              ('county-config.json', 'https://apps.usgs.gov/nccv/loca2/nccv2_loca2_counties_20260210.json'),
              ('watershed-config.json', 'https://apps.usgs.gov/nccv/loca2/nccv2_loca2_watersheds_20260210.json')]
    receipts = {name: acquire(raw, name, url)[1] for name, url in inputs}
    lands = pq.ParquetFile(raw / 'lands.parquet').read().to_pylist()
    if len({l['land_id'] for l in lands}) != len(lands):
        raise ValueError('duplicate current land IDs')
    metadata = {v['variable']: v for v in pq.ParquetFile(raw / 'variables.parquet').read().to_pylist()}
    manifest_paths = {r['path']: r for r in read_json(raw / 'projections-manifest.json')}
    dependencies = {name: r['sha256'] for name, r in receipts.items() if not name.endswith('config.json')}
    dependencies.update(registry=sha_bytes(args.registry.read_bytes()), producer=sha_bytes(Path(__file__).read_bytes()), method=METHOD, schema=SCHEMA)
    links = read_json(args.links) if args.links else None
    if links:
        if links['registry_sha256'] != dependencies['registry']:
            raise ValueError('crosswalk registry hash differs from supplied registry')
        dependencies['nation_area_crosswalk'] = sha_bytes(args.links.read_bytes())
        dependencies['geography'] = fingerprint(links['dependency_hashes'])
    targets = [l for l in lands if l['modeled'] and (args.mode != 'pilot' or l['land_id'] == '2070R')]
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = [pool.submit(prepare_native, land, raw, out, metadata, dependencies, manifest_paths) for land in targets]
        for future in as_completed(tasks):
            results.append(future.result())
            if len(results) % 25 == 0 or len(results) == len(targets):
                print(json.dumps({'processed': len(results), 'eligible': len(targets), 'states': dict(Counter(r['status'] for r in results)),
                                  'seconds': round(time.monotonic() - start, 1)}), flush=True)
    regional = prepare_regional(raw, out)
    coverage = account_nations(read_json(args.registry), links, results) if links and args.mode == 'national' else None
    if coverage:
        coverage['dependency_hashes'] = dependencies
        atomic_json(out / 'coverage.json', coverage)
        summary = write_summary(out, results, coverage)
    manifest = {'schema_version': SCHEMA, 'method_version': METHOD, 'generated_at': datetime.now(timezone.utc).isoformat(),
                'data_as_of': None, 'data_as_of_reason': 'Modeled historical/future years, not an observed current-condition snapshot.',
                'native_source_commit': NATIVE_COMMIT, 'native_product': 'NEX-GDDP-CMIP6 v2.0 (2025), Native annual metric version 1',
                'geometry_vintage': 2025, 'license': 'CC0 for Native and USGS prepared products',
                'input_manifest_sha256': fingerprint(receipts), 'inputs': receipts, 'dependencies': dependencies,
                'areas': sorted(results, key=lambda r: r['area_id']), 'regional': regional,
                'coverage': {'current_land_metadata': len(lands), 'provider_modeled_areas': sum(l['modeled'] for l in lands),
                             'processed_areas': len(results), 'area_status': dict(Counter(r['status'] for r in results)),
                             'metric_areas': {m: dict(Counter(r['metric_status'].get(m, r['status']) for r in results)) for m in METRICS}},
                'limitations': LIMITATIONS, 'elapsed_seconds': round(time.monotonic() - start, 1)}
    if coverage:
        manifest['coverage']['nations'] = coverage['metrics']
        manifest['coverage']['accounted_nations'] = coverage['nation_count']
        manifest['summary_csv'] = summary
    atomic_json(out / ('pilot-manifest.json' if args.mode == 'pilot' else 'manifest.json'), manifest)
    print(json.dumps({'manifest': str(out), 'coverage': manifest['coverage'], 'regional': regional}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('pilot', 'national'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--links', type=Path)
    prepare(parser.parse_args())
