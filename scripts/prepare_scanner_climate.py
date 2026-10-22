"""Project the accepted scanner climate bundle into bounded public explorer assets."""
from collections import Counter
import csv
from hashlib import sha256
import json


METADATA_FIELDS = ('schema_version', 'source_product', 'source_commit', 'source_method',
                   'method_version', 'model_weighting', 'quantile_method', 'spread_meaning',
                   'regional_scope', 'realization', 'realization_reason', 'calendar',
                   'calendar_reason', 'license', 'limitations')
AREA_FIELDS = ('area_id', 'name', 'family', 'geometry_area_id', 'geometry', 'geometry_role',
               'ecoregion_ids', 'ecoregion_support_caution', 'projections', 'source')
REGION_FIELDS = ('region_id', 'region_name', 'status', 'missing_reason', 'scope', 'counts',
                 'member_nation_ids', 'nation_area_support', 'source_area_ids', 'projections',
                 )
NATION_FIELDS = ('tribe_id', 'name', 'area_ids', 'geometry_area_ids', 'mapping_status',
                 'mapping_caution', 'mapping_confidence', 'missing_reason', 'proxy', 'shared',
                 'requires_area_selection', 'climate')


def project(record, fields):
    return {key: record[key] for key in fields if key in record}


def compact_projections(record):
    projections = record['projections']
    if projections is None:
        return {**record, 'model_means': None, 'models': []}
    models = projections[0]['models']
    assert all(p['models'] == models for p in projections)
    return {**record, 'models': models,
            'projections': [{key: value for key, value in p.items() if key != 'models'} for p in projections]}


def validate_joins(nations, areas, geography):
    """No parent-GEOID or nearest-area fallback is permitted for modeled agencies."""
    geoareas = {area['area_id']: area for area in geography['areas']}
    canonical = {nation['tribe_id']: nation for nation in geography['nations']}
    assert len(nations) == len(canonical) == 575
    assert {n['tribe_id'] for n in nations} == set(canonical)
    assert len(areas) == len({area['area_id'] for area in areas})
    available = {area['area_id'] for area in areas}
    for nation in nations:
        assert nation['area_ids'] == canonical[nation['tribe_id']]['area_ids'], nation['tribe_id']
        for metric in nation['climate'].values():
            assert set(metric['supported_area_ids']) <= available
    for area in areas:
        key = area['area_id']
        geo = geoareas[key]
        assert area['geometry_area_id'] == key
        assert area['geometry']['provider_hash'] == geo['source_geometry_hash'], key
        assert area['geometry']['vintage'] == geo['geometry_vintage'], key
        epa = {m['cohort_id'] for m in geo['memberships'] if m['taxonomy'] == 'epa-cec-l3-2010'}
        assert set(area['ecoregion_ids']) == epa, key


def prepare_scanner_climate(bundle, verified, geography, site):
    def load(name):
        return json.loads((bundle / name).read_text(encoding='utf-8'))

    manifest = verified['climate_manifest']
    nations = load('climate_nations.json')['nations']
    areas = load('climate_areas.json')['areas']
    validate_joins(nations, areas, geography)
    nation_lookup = {n['tribe_id']: n for n in nations}
    files = {}

    def write(key, relative, value):
        path = site / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')
        files[key] = {'path': relative, 'bytes': path.stat().st_size, 'sha256': sha256(path.read_bytes()).hexdigest()}
        return key

    area_files = {}
    for area in areas:
        key = area['area_id']
        area_files[key] = write('scanner-climate-area-' + key,
                                f'data/explorer/scanner-climate/areas/{key}.json', compact_projections(project(area, AREA_FIELDS)))
    regions = {}
    for group, prefix in [('ecoregions', 'ecoregion'), ('advocacy_regions', 'advocacy')]:
        source = load(f'climate_{group}.json')
        regions[group] = []
        for raw in source['regions']:
            region = compact_projections(project(raw, REGION_FIELDS))
            if region['projections'] is not None:
                region['model_means_status'] = 'not_shipped'
                region['model_means_note'] = 'Per-model source-area means are retained in the accepted local export; public files provide their model-spread summaries and contributor support.'
            region['taxonomy'] = source['taxonomy']
            region['category'] = ('water' if raw['region_id'] == '0.0.0' else 'ecoregion') if group == 'ecoregions' else 'advocacy_region'
            region['counts'] = {**region['counts'], 'shared_nations': sum(bool(nation_lookup[n]['shared']) for n in raw['member_nation_ids'])}
            file_id = write(f"scanner-climate-{prefix}-{raw['region_id']}",
                            f"data/explorer/scanner-climate/{group}/{raw['region_id']}.json", region)
            regions[group].append({**project(region, ('region_id', 'region_name', 'taxonomy', 'category', 'status', 'missing_reason', 'counts')), 'file': file_id})
    support = Counter(n['climate']['temp_mean']['status'] for n in nations)
    counts = {**manifest['counts'], 'associated_supported_nations': sum(not n['proxy'] and bool(n['climate']['temp_mean']['supported_area_ids']) for n in nations),
              'shared_supported_nations': sum(bool(n['shared']) and bool(n['climate']['temp_mean']['supported_area_ids']) for n in nations),
              'ecoregions_excluding_water': len(regions['ecoregions']) - 1, 'water_categories': 1,
              'supported_ecoregions_excluding_water': sum(r['status'] == 'available' and r['category'] == 'ecoregion' for r in regions['ecoregions']),
              'nation_status_counts': dict(support)}
    metadata = {**project(manifest, METADATA_FIELDS), 'counts': counts,
                'accepted_source': {'calculation_revision': verified['handoff']['calculation_revision'],
                                    'export_revision': verified['handoff']['export_revision'],
                                    'climate_manifest_sha256': sha256((bundle / 'climate_manifest.json').read_bytes()).hexdigest()},
                'nations': [project(n, NATION_FIELDS) for n in nations],
                'member_data': 'Area and region files retain model identities and period summaries; full source-member rows and regional per-model means remain outside the public artifact.',
                'csv_contract': 'Public CSV preserves every source numeric/status/proxy field and row. Names and repeated support notes are held here: join nation_source_area rows by tribe_id, EPA rows by region_id, and advocacy rows by region_id. Read mapping_caution for Nations and scope for regions. model_spread_meaning=not_probability describes conditional model spread, not an event probability or confidence interval.',
                **regions}
    metadata_id = write('scanner-climate', 'data/explorer/scanner-climate.json', metadata)
    csv_path = site / 'data/explorer/scanner-climate.csv'
    with (bundle / 'climate_projections.csv').open(encoding='utf-8', newline='') as source, csv_path.open('w', encoding='utf-8', newline='') as target:
        reader = csv.DictReader(source)
        fields = [field for field in reader.fieldnames if field not in {'name', 'support_note'}]
        writer = csv.DictWriter(target, fieldnames=[*fields, 'support_note_ref', 'model_spread_meaning'], lineterminator='\n')
        writer.writeheader()
        for row in reader:
            writer.writerow({**{field: row[field] for field in fields}, 'support_note_ref': 'scanner-climate.json', 'model_spread_meaning': 'not_probability'})
    files['scanner-climate-csv'] = {'path': csv_path.relative_to(site).as_posix(), 'bytes': csv_path.stat().st_size,
                                    'sha256': sha256(csv_path.read_bytes()).hexdigest()}
    return {'metadata_file': metadata_id, 'csv_file': 'scanner-climate-csv', 'counts': counts,
            'area_files': area_files, 'files': files, **regions}
