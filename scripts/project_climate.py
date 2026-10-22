"""Allowlist accepted climate summaries into compact static participant files."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

SAFE_ID = re.compile(r'^[A-Za-z0-9_-]+$')
LOCAL_PATH = re.compile(r'(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|file://|(?:^|[\s"\'])work[\\/]|/Users/|/home/)')
SCENARIOS = ('ssp245', 'ssp370')
METRICS = ('temp_mean', 'pr_annual')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_public(value):
    if isinstance(value, str) and LOCAL_PATH.search(value):
        raise ValueError('local path in public climate projection')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('non-finite public value')
    if isinstance(value, dict):
        for key, item in value.items():
            check_public(key)
            check_public(item)
    elif isinstance(value, list):
        for item in value:
            check_public(item)


def write(path, value):
    check_public(value)
    body = (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(body)
    temporary.replace(path)
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def check_bounds(lower, median, upper):
    values = (lower, median, upper)
    if all(v is None for v in values):
        return
    if any(v is None or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError('incomplete or non-finite summary bounds')
    if not lower <= median <= upper:
        raise ValueError('unordered summary bounds')


def project_area(area, manifest):
    area_id = area['area_id']
    if not SAFE_ID.fullmatch(area_id):
        raise ValueError('invalid source-area ID')
    family = area['family']
    if family not in ('native-nex', 'usgs-nccv-loca2') or area['status'] not in ('available', 'partial'):
        raise ValueError('area source family/status is not accepted')
    native = family == 'native-nex'
    receipt = area['source']
    if not receipt['url'].startswith('https://'):
        raise ValueError('source must have a public HTTPS URL')
    source = {key: receipt[key] for key in ('url', 'sha256', 'acquired_at', 'acquisition_date', 'acquisition_date_basis', 'last_modified') if key in receipt}
    source.update(label='Native Resilience / NASA NEX-GDDP-CMIP6' if native else 'USGS NCCV / LOCA2',
                  license='CC0-1.0',
                  license_url='https://data.native-resilience.com/projections/' if native else 'https://www.usgs.gov/data/cmip6-loca2-monthly-water-balance-model-projections-1950-2100-contiguous-united-states')
    if native:
        source.update(release=manifest['native_product'], upstream_commit=manifest['native_source_commit'],
                      variable_metadata_sha256=manifest['inputs']['variables.parquet']['sha256'],
                      geometry_vintage=area['geometry']['vintage'], geometry_provider_hash=area['geometry']['provider_hash'],
                      method_version=manifest['method_version'], realization=None, calendar=None,
                      member_lineage_note='Realization IDs and calendar names are not supplied by the annual member table.')
    else:
        source.update(release='USGS NCCV LOCA2 prepared annual summaries', summary_revision='October 2023',
                      publication_path_revision='2026-02-03',
                      revision_note='The 2026 directory does not establish incorporation of corrected 2024 precipitation.')
    baseline = '1995-2014' if native else '1981-2010'
    result = {'id': area_id, 'name': area['name'], 'family': family, 'baseline_id': baseline,
              'geometry_role': 'native_land_area' if native else area['kind'], 'status': area['status'],
              'value_kind': 'change', 'source': source, 'limitations': list(area['limitations']), 'metrics': {}}
    for metric_id in METRICS:
        if metric_id not in area['metrics']:
            continue
        metric = area['metrics'][metric_id]
        if metric['status'] not in ('available', 'partial'):
            result['metrics'][metric_id] = {'status': metric['status'], 'reason': metric.get('reason'), 'windows': {}}
            continue
        if metric['baseline_id'] != baseline or metric['value_kind'] != 'change':
            raise ValueError('mixed baseline or value kind')
        if metric['unit'] != ('degC' if metric_id == 'temp_mean' else 'mm'):
            raise ValueError('unrecognized canonical physical unit')
        definition = ('Change in annual mean temperature relative to each model’s 1995–2014 mean.' if metric_id == 'temp_mean'
                      else 'Change in mean annual precipitation total relative to each model’s 1995–2014 mean; millimetres per year.') if native else 'Provider annual mean-temperature change relative to 1981–2010.'
        public = {'label': metric['label'], 'unit': '°C' if metric_id == 'temp_mean' else 'mm/year',
                  'source_summary_unit': metric['unit'], 'definition': definition, 'status': metric['status'],
                  'value_kind': 'change', 'baseline_id': baseline, 'statistic': metric['statistic'],
                  'spread': metric['spread'], 'provider_fit_status': metric['provider_fit_status'],
                  'provider_fit_status_reason': metric['provider_fit_status_reason'], 'windows': {}}
        if native:
            public.update(source_unit=metric['source_unit'], model_ids=metric['model_ids'],
                          expected_models=metric['expected_model_count'], model_count=metric['model_count'],
                          quantile_method=metric['quantile_method'], weighting=metric['weighting'])
            for window in metric['windows']:
                values = {}
                for scenario in SCENARIOS:
                    summary = window['scenarios'][scenario]
                    check_bounds(summary['lower'], summary['median'], summary['upper'])
                    values[scenario] = {key: summary[key] for key in ('lower', 'median', 'upper')}
                    values[scenario].update(models=summary['model_count'], status=metric['status'],
                                            valid_years_per_model=summary['valid_years_per_model'], expected_years_per_model=20)
                public['windows'][window['period_id']] = values
            if set(public['windows']) != {'2020-2039', '2040-2059', '2070-2089'}:
                raise ValueError('required Native future windows missing')
        else:
            public['series'] = {}
            for scenario in SCENARIOS:
                series = metric['series'][scenario]
                if series['years'] != list(range(1950, 2101)):
                    raise ValueError('regional source years changed')
                if any(len(series[key]) != 151 for key in ('lower', 'median', 'upper')):
                    raise ValueError('regional array length mismatch')
                for values in zip(series['lower'], series['median'], series['upper']):
                    check_bounds(*values)
                public['series'][scenario] = {key: series[key] for key in ('years', 'lower', 'median', 'upper', 'model_ids', 'missing_years')}
                public['series'][scenario].update(models=series['model_count'], status=metric['status'])
        result['metrics'][metric_id] = public
    result['spread'] = ('the 10th–90th percentile of paired model changes, with equal model weights' if native
                        else 'the provider’s 10th–90th percentile of annual model anomalies; scenario memberships differ')
    check_public(result)
    return result


def project(work, links_path, output, manifest_path):
    manifest = read(work / 'manifest.json')
    links = read(links_path)
    if digest(links_path) != manifest['dependencies']['nation_area_crosswalk']:
        raise ValueError('current crosswalk differs from accepted climate dependency')
    ids = {area_id for n in links['nations'] for area_id in n['area_ids']}
    native = {row['area_id']: row for row in manifest['areas']}
    if not ids <= native.keys():
        raise ValueError('referenced source area absent from climate manifest')
    chosen = [(area_id, work / 'areas' / (area_id + '.json'), native[area_id]['output_sha256']) for area_id in sorted(ids)]
    chosen += [(r['area_id'], work / 'regional' / (r['area_id'] + '.json'), r['sha256']) for r in manifest['regional']]
    public_manifest = {'schema_version': 'catf-public-climate-v1', 'method_version': 'allowlist-physical-summaries-v1',
                       'source_manifest_sha256': digest(work / 'manifest.json'), 'crosswalk_sha256': digest(links_path),
                       'areas': {}, 'files': {}, 'coverage': manifest['coverage']['nations'],
                       'accounted_nations': manifest['coverage']['accounted_nations'],
                       'sources': [
                           {'id': 'native-nex', 'label': 'Native Resilience / NASA NEX-GDDP-CMIP6',
                            'url': 'https://data.native-resilience.com/projections/', 'release': manifest['native_product'],
                            'upstream_commit': manifest['native_source_commit'], 'license': 'CC0-1.0'},
                           {'id': 'usgs-nccv-loca2', 'label': 'USGS NCCV / LOCA2',
                            'url': 'https://apps.usgs.gov/nccv/loca2/nccv2_documentation_v2.pdf',
                            'summary_revision': 'October 2023', 'license': 'CC0-1.0'}],
                       'limitations': ['Supported Nation counts include associated and explicitly labeled proxy source-area context; they are not independently validated Nation-mean climates.',
                                       'Native annual member curves remain private to meet the shipped-data budget; public Native values are supported 20-year window changes.',
                                       'Regional annual series retain source geography and baseline; no model quantile bands are averaged into multi-year change windows.']}
    for area_id, path, expected in chosen:
        if digest(path) != expected:
            raise ValueError('area summary no longer matches accepted input manifest: ' + area_id)
        public = project_area(read(path), manifest)
        record = write(output / (area_id + '.json'), public)
        file_id = 'climate-' + area_id
        public_manifest['areas'][area_id] = {key: public[key] for key in ('id', 'name', 'family', 'baseline_id', 'geometry_role', 'status')}
        public_manifest['areas'][area_id]['file_id'] = file_id
        public_manifest['files'][file_id] = {'path': 'data/explorer/areas/' + area_id + '.json', **record}
    public_manifest['total_bytes'] = sum(f['bytes'] for f in public_manifest['files'].values())
    public_manifest['native_area_count'] = len(ids)
    public_manifest['regional_area_count'] = len(manifest['regional'])
    write(manifest_path, public_manifest)
    return public_manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--links', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    result = project(args.work, args.links, args.output, args.manifest)
    print(json.dumps({key: result[key] for key in ('native_area_count', 'regional_area_count', 'accounted_nations', 'total_bytes')}))
