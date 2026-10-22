"""Join accepted climate/geography derivatives into the deliberate static artifact."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
from urllib.request import urlopen

from prepare_risk_data import aggregate_counties
from prepare_scanner_climate import prepare_scanner_climate

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
GEO = ROOT / 'work/geography'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')


def descriptor(path):
    return {'path': path.relative_to(SITE).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha256(path.read_bytes()).hexdigest()}


def bounds(value):
    west, south, east, north = value
    assert west < east and south < north
    return [[south, west], [north, east]]


def county_context(fips, counties, source_identity=None):
    selected = sorted(set(fips))
    rows = [counties[key] for key in selected if key in counties]
    # Reuse the accepted county aggregation without initializing the scanner.
    total = aggregate_counties(rows, lambda _, contexts: (None, None, None, sum(c.vulnerability_profile['nri']['eal_total'] for c in contexts)))
    total.update(expected_counties=len(selected), unmatched_county_fips=[key for key in selected if key not in counties],
                 period='Annualized model expectation', unit='USD/year', price_year=None,
                 scope='Whole counties intersecting the story footprint; all county assets, not Tribal losses or funding need.',
                 source_version='FEMA NRI ' + ', '.join((source_identity or {'version': ['December 2025']})['version']) + ' v1.20')
    if source_identity:
        total['source_sha256'] = source_identity['sha256']
    return total


def vendor_leaflet():
    folder = SITE / 'assets/vendor/leaflet-1.9.4'
    files = ['leaflet.js', 'leaflet.css', 'images/layers.png', 'images/layers-2x.png', 'images/marker-icon.png', 'images/marker-icon-2x.png', 'images/marker-shadow.png']
    receipts = []
    for name in files + ['LICENSE.txt']:
        path = folder / name
        url = ('https://raw.githubusercontent.com/Leaflet/Leaflet/v1.9.4/LICENSE' if name == 'LICENSE.txt' else 'https://unpkg.com/leaflet@1.9.4/dist/' + name)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with urlopen(url, timeout=45) as response:
                payload = response.read()
            assert payload
            path.write_bytes(payload)
        receipts.append({**descriptor(path), 'url': url})
    save(ROOT / 'work/geography/leaflet-manifest.json', {'version': '1.9.4', 'license': 'BSD-2-Clause', 'files': receipts})


def bundle_explorer_styles():
    leaflet = (SITE / 'assets/vendor/leaflet-1.9.4/leaflet.css').read_text(encoding='utf-8')
    leaflet = leaflet.replace('url(images/', 'url(../assets/vendor/leaflet-1.9.4/images/')
    component_styles = [(SITE / 'components' / name).read_text(encoding='utf-8')
                        for name in ('place-explorer.css', 'pathway-chart.css')]
    (SITE / 'components/explorer.css').write_text('\n'.join([leaflet, *component_styles]).rstrip() + '\n', encoding='utf-8', newline='\n')


def main():
    from scanner_bundle import accept_county_snapshot, verify_bundle
    bundle = Path('I:/data/tcr-policy-scanner/output/integrations/climate-action-taskforce')
    verified = verify_bundle(bundle, Path('I:/data/tcr-policy-scanner'))
    county_path = Path('I:/data/tcr-policy-scanner/reference/data/nri/NRI_Table_Counties.csv')
    rows, county_identity = accept_county_snapshot(county_path)
    risk = load(SITE / 'data/risk.json')
    assert risk['source_snapshots']['nri_counties'] == county_identity, 'Risk/explorer county snapshot mismatch'
    for filename in ('geography.json', 'nation-area-crosswalk.json'):
        assert sha256((GEO / filename).read_bytes()).hexdigest() == verified['climate_manifest']['inputs']['geography/' + filename], 'Accepted climate geography input mismatch'
    geography = load(GEO / 'geography.json')
    climate = load(ROOT / 'work/climate/public-manifest.json')
    crosswalk = geography['nations']
    assert len(crosswalk) == len({n['tribe_id'] for n in crosswalk}) == 575
    files = dict(climate['files'])
    areas = dict(climate['areas'])
    geoareas = {area['area_id']: area for area in geography['areas']}
    scanner_climate = prepare_scanner_climate(bundle, verified, geography, SITE)
    files.update(scanner_climate.pop('files'))
    for area_id, file_id in scanner_climate.pop('area_files').items():
        areas[area_id]['scanner_climate_file'] = file_id
    copied = {}

    def copy_asset(relative):
        if relative in copied:
            return copied[relative]
        assert relative.startswith('display/') and '..' not in relative.split('/')
        path = SITE / 'assets/explorer' / relative.removeprefix('display/')
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(GEO / relative, path)
        key = 'geo-' + relative.removeprefix('display/').replace('/', '-').rsplit('.', 1)[0]
        files[key] = descriptor(path)
        copied[relative] = key
        return key

    views = {}
    for view, extent in geography['extents'].items():
        views[view] = {'bounds': bounds(extent), 'geometry_file': copy_asset(f'display/land-{view}.json'),
                       'relief_file': copy_asset(f'display/relief-{view}.jpg'),
                       'attribution': 'Made with Natural Earth · EPA/CEC 2010 · USGS WBD 2025 · Native Resilience/Census 2025. Public source areas are not comprehensive Nation territories.'}
    hawaii_divisions = [geoareas[key] for key in sorted(geoareas) if key.startswith('HI-')]
    assert len(hawaii_divisions) == 12 and all(area['view'] == 'hawaii' for area in hawaii_divisions)
    hawaii_features = [feature for area in hawaii_divisions for feature in load(GEO / area['display_asset'])['features']]
    assert {feature['properties']['id'] for feature in hawaii_features} == {area['area_id'] for area in hawaii_divisions}
    hawaii_path = SITE / 'assets/explorer/reference-hawaii.json'
    save(hawaii_path, {'type': 'FeatureCollection', 'features': hawaii_features})
    files['geo-reference-hawaii'] = descriptor(hawaii_path)
    views['hawaii']['reference_geometry_file'] = 'geo-reference-hawaii'
    lens_cache = {}
    for area_id, area in areas.items():
        if area_id not in geoareas:
            continue
        geo = geoareas[area_id]
        area.update(point=[geo['point'][1], geo['point'][0] - 360 if geo['view'] == 'alaska' and geo['point'][0] > 0 else geo['point'][0]],
                    bounds=bounds(geo['bounds']), view=geo['view'], geometry_role=geo['geometry_role'], geometry_caution=geo['geometry_caution'],
                    ecology_status=geo['ecology_status'], basin_status=geo['basin_status'], geometry_file=copy_asset(geo['display_asset']))
        area['memberships'] = {}
        area['lens_files'] = {}
        for lens, prefix in [('ecology', 'epa'), ('basin', 'wbd')]:
            members = [m for m in geo['memberships'] if m['taxonomy'].startswith(prefix)]
            area['memberships'][lens] = [m['cohort_id'] + ' · ' + m['name'] for m in members]
            # Membership references select the Alaska-unwrapped display variant
            # where needed. Each source unit is fetched from its bounded shard.
            paths = tuple(sorted({m['display_asset'] for m in members}))
            features = [f for path in paths for f in load(GEO / path)['features']]
            assert {f['properties']['id'] for f in features} == {m['cohort_id'] for m in members}
            if features:
                if paths not in lens_cache:
                    content = {'type': 'FeatureCollection', 'features': features}
                    fingerprint = sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:20]
                    relative = f'data/explorer/lenses/{lens}-{fingerprint}.json'
                    save(SITE / relative, content)
                    key = f'lens-{lens}-{fingerprint}'
                    files[key] = descriptor(SITE / relative)
                    lens_cache[paths] = key
                area['lens_files'][lens] = lens_cache[paths]
    places = [{'id': 'nation:' + n['tribe_id'], 'kind': 'nation', **{k: n[k] for k in ['tribe_id', 'name', 'area_ids', 'mapping_status', 'mapping_caution', 'mapping_confidence', 'proxy', 'shared', 'missing_reason']}} for n in crosswalk]
    places.append({'id': 'reference:hawaii', 'kind': 'reference', 'name': 'Hawaii climate divisions — reference geography',
                   'view': 'hawaii', 'area_ids': [],
                   'missing_reason': 'Reference geography only; no Nation association or climate projection is supplied for this view.'})
    for region in geography['regions']:
        aid = ('US' if region['kind'] == 'county' else 'HUC') + region['id']
        if aid not in areas:
            continue
        box = bounds(region['bounds'])
        areas[aid].update(view='conus', bounds=box, point=[sum(p[0] for p in box) / 2, sum(p[1] for p in box) / 2], geometry_file=copy_asset(region['geometry_asset']), memberships={},
                          geometry_role=region.get('role', 'Independent county context; not Nation land or the authored story climate mean'))
        places.append({'id': 'region:' + aid, 'kind': 'region', 'name': region['name'], 'area_ids': [aid], 'mapping_status': 'regional_context'})
    counties = {row['STCOFIPS'].zfill(5): row for row in rows}
    assert len(counties) == len(rows)
    cohorts = []
    preferred = {'columbia-us': 'Yakama', 'desert-southwest': 'Gila River', 'northeast-forest': 'Penobscot'}
    for raw in geography['cohorts']:
        assert raw['status'] == 'supported', raw['id']
        candidates = [p for p in places if p.get('tribe_id') in raw['tribe_ids'] and len(p['area_ids']) == 1 and not p.get('proxy')]
        selected = next((p for p in candidates if preferred[raw['id']].lower() in p['name'].lower()), candidates[0])
        cohorts.append({**{k: raw[k] for k in ['id', 'label', 'source_unit_ids', 'rule', 'county_fips', 'area_ids', 'tribe_ids']},
                        'view': 'conus', 'scope': raw['county_relation'], 'bounds': bounds(raw['bounds']),
                        'geometry_file': copy_asset(raw['geometry_asset']), 'default_place': selected['id'], 'default_area': selected['area_ids'][0],
                        'costs': county_context(raw['county_fips'], counties, county_identity)})
    release = 'catf-place-2026-10-22-v1'
    catalog = {'schema_version': 'catf-explorer.v1', 'release_id': release,
               'default_selection': {'release': release, 'place': cohorts[0]['default_place'], 'area': cohorts[0]['default_area'], 'family': 'native-nex', 'metric': 'temp_mean', 'baseline': '1995-2014', 'period': '2040-2059', 'lens': 'basin', 'story': cohorts[0]['id']},
               'families': [{'id': 'native-nex', 'label': 'Native Resilience · NEX-GDDP-CMIP6'}, {'id': 'usgs-nccv-loca2', 'label': 'USGS NCCV · LOCA2 regional context'}],
               'metrics': [{'id': 'temp_mean', 'label': 'Mean temperature change'}, {'id': 'pr_annual', 'label': 'Annual precipitation change'}],
               'baselines': [{'id': '1995-2014', 'label': '1995–2014'}, {'id': '1981-2010', 'label': '1981–2010'}],
               'periods': [{'id': p, 'label': p.replace('-', '–')} for p in ['2020-2039', '2040-2059', '2070-2089']],
               'lenses': [{'id': 'ecology', 'label': 'EPA/CEC Level III ecology'}, {'id': 'basin', 'label': 'USGS HUC4 watersheds'}],
               'places': places, 'areas': areas, 'cohorts': cohorts, 'views': views, 'files': files,
               'scanner_climate': scanner_climate,
               'coverage': {'nations': 575, **geography['coverage']}, 'sources': geography['source_refs'] + climate['sources'], 'limitations': geography['limitations'],
               'input_hashes': {name: sha256(path.read_bytes()).hexdigest() for name, path in [('geography', GEO / 'geography.json'), ('climate', ROOT / 'work/climate/public-manifest.json'), ('county_costs', county_path)]}}
    save(SITE / 'data/explorer/catalog.json', catalog)
    vendor_leaflet()
    bundle_explorer_styles()
    payload = sum(path.stat().st_size for path in SITE.rglob('*') if path.is_file()
                  and ('/explorer/' in path.as_posix() or '/leaflet-1.9.4/' in path.as_posix()
                       or path.parent.name in {'components', 'state'} or path.name in {'explorer.js', 'catalog.js'}))
    assert payload < 16 * 1024 * 1024, payload
    print(json.dumps({'places': len(places), 'climate_areas': len(areas), 'cohorts': len(cohorts), 'files': len(files), 'bytes': payload}))


if __name__ == '__main__':
    main()
