"""Prepare frozen, public geography derivatives without running source applications."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
import zipfile

import numpy as np
import pyarrow.parquet as pq
import pyogrio.raw
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling, transform as project_xy
from PIL import Image
import shapely
from shapely.geometry import box, mapping, shape, Polygon, MultiPolygon
from shapely.ops import transform, split, unary_union
from shapely.affinity import translate

ROOT = Path(__file__).resolve().parents[1]
METHOD = 'catf-geography-v1'
EXPECTED_REGISTRY = '5db8f52cf44d3a3853f8403cd6dc845a59088f07f42b40a3488575b5cbe7cece'
EXPECTED_NATIVE = '9214dff1a5412d0f4b7351bd4c9b8de99ae3543fb3a601c44c75ee4c1cf956e1'
EXTENTS = {'conus': [-126, 23, -66, 51], 'alaska': [-190, 50, -129, 72], 'hawaii': [-161, 18, -154, 23]}
STORIES = {
    'columbia-us': {'label': 'Columbia River Basin — U.S. portion', 'taxonomy': 'wbd04-20250107', 'unit_ids': [f'170{i}' for i in range(1, 10)]},
    'desert-southwest': {'label': 'Desert Southwest', 'taxonomy': 'epa-cec-l3-2010', 'unit_ids': ['10.2.1', '10.2.2', '10.2.4']},
    'northeast-forest': {'label': 'Northeast forest', 'taxonomy': 'epa-cec-l3-2010', 'unit_ids': ['5.3.1', '5.3.3', '8.1.1', '8.1.3', '8.1.7', '8.1.8']},
}
GEOMETRY_CAUTION = 'Public modeled land-area geometry is not a comprehensive statement of Nation territory, ownership or sovereign authority.'
MAPPING_CAUTION = 'Association carries a legacy reviewed name/code crosswalk forward to current source IDs; it is not independent Nation confirmation. Shared and borrowed areas remain explicit.'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n'
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(data, encoding='utf-8')
    load(temp)
    temp.replace(path)


def normalized_name(name):
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower())


def reproject_geometry(geom, source, target='EPSG:6933'):
    return transform(lambda x, y, z=None: project_xy(source, target, x, y), geom)


def polygon_parts(geom):
    if geom.geom_type == 'Polygon':
        return [geom]
    return [p for g in getattr(geom, 'geoms', []) for p in polygon_parts(g)]


def split_dateline(geom):
    """Split geographic rings at ±180 before any cylindrical area projection."""
    coords = shapely.get_coordinates(geom)
    if not np.isfinite(coords).all() or np.any(np.abs(coords[:, 0]) > 180.000001) or np.any(np.abs(coords[:, 1]) > 90):
        raise ValueError('Expected finite longitude/latitude coordinates in WGS84 order')
    pieces = []
    for polygon in polygon_parts(geom):
        def unwrap(ring, near=None):
            coords = list(ring.coords)
            out = [list(coords[0][:2])]
            if near is not None:
                out[0][0] += 360 * round((near - out[0][0]) / 360)
            for x, y, *rest in coords[1:]:
                x += 360 * round((out[-1][0] - x) / 360)
                out.append([x, y])
            return out
        shell = unwrap(polygon.exterior)
        holes = [unwrap(r, shell[0][0]) for r in polygon.interiors]
        unwrapped = shapely.make_valid(Polygon(shell, holes))
        for shift in (-360, 0, 360):
            part = translate(unwrapped, xoff=shift).intersection(box(-180, -90, 180, 90))
            pieces.extend(polygon_parts(part))
    return shapely.make_valid(MultiPolygon(pieces))


def alaska_display(geom):
    return MultiPolygon([translate(p, xoff=-360) if p.representative_point().x > 0 else p for p in polygon_parts(geom)])


def read_vector(path):
    metadata, _, geoms, columns = pyogrio.raw.read(str(path))
    rows = [{str(k): (v[i].item() if isinstance(v[i], np.generic) else v[i]) for k, v in zip(metadata['fields'], columns)} for i in range(len(geoms))]
    return metadata['crs'], rows, list(shapely.from_wkb(geoms))


def geometry_role(row, census):
    if row['land_id'].startswith('HI-'):
        return 'Hawaii climate division; regional context, not a Nation'
    if '-' in row['land_id']:
        return 'Native Resilience modeled Navajo agency grouping of Census subdivisions'
    if row['COMPTYP'] == 'T':
        return 'Census off-reservation trust or Hawaiian Home Lands component; annual climate product unavailable'
    name = row['name']
    if 'ANVSA' in name:
        return 'Census Alaska Native Village Statistical Area; statistical representation'
    if any(t in name for t in ('OTSA', 'TDSA', 'SDTSA')):
        return 'Census Tribal statistical area; modeled geographic context'
    return 'Census reservation or rancheria component used by the Native climate product'


def map_nations(registry, old, codes, native):
    by_name = defaultdict(list)
    by_code = defaultdict(list)
    for row in native:
        by_name[normalized_name(row['name'])].append(row)
        if row['AIANNHCE']:
            by_code[row['AIANNHCE']].append(row)
    nations = []
    for nation in registry:
        tid = nation['tribe_id']
        link = old.get(tid)
        matches, method = [], None
        if link:
            matches = by_name.get(normalized_name(link['area_slug']), [])
            method = 'legacy_name_exact_to_current_land'
            # The pinned provider boundary producer explicitly records this 2024→2025 rename.
            if not matches and link['area_slug'] == 'Eastern_Cherokee_Reservation':
                matches = by_name.get(normalized_name('Qualla Boundary'), [])
                method = 'provider_documented_2025_rename'
            if not matches:
                code = (codes.get(tid, {}).get('geoid') or '')[:4]
                # Only a recorded code may bridge a renamed or subdivided source area.
                matches = [r for r in by_code.get(code, []) if r['modeled']]
                method = 'legacy_reviewed_code_to_current_land'
            if any(r['AIANNHCE'] == '2430' for r in matches):
                matches = [r for r in by_code['2430'] if r['modeled']]
                method = 'legacy_code_to_five_current_navajo_agencies'
        matches = sorted(matches, key=lambda r: r['land_id'])
        proxy = bool(link and link['method'] in {'host_area', 'geospatial_pip'})
        nations.append({'tribe_id': tid, 'name': nation['name'], 'states': nation['states'],
                        'area_ids': [r['land_id'] for r in matches if r['modeled']],
                        'geometry_area_ids': [r['land_id'] for r in matches],
                        'mapping_status': ('proxy' if proxy else 'associated') if matches else 'unmapped',
                        'mapping_method': method if matches else None,
                        'mapping_confidence': link.get('confidence') if link and matches else None,
                        'legacy_method': link.get('method') if link else None,
                        'proxy': proxy, 'shared': False,
                        'evidence': 'Pinned legacy crosswalk name/code corroborated against the current Native land table' if matches else None,
                        'missing_reason': None if matches else 'No unambiguous current Native land association established from the pinned crosswalk.',
                        'mapping_caution': MAPPING_CAUTION})
    owners = defaultdict(set)
    for n in nations:
        for aid in n['area_ids']:
            owners[aid].add(n['tribe_id'])
    for n in nations:
        n['shared'] = any(len(owners[aid]) > 1 for aid in n['area_ids'])
    return nations


def prepare_mapping(args):
    out, raw = args.output, args.output / 'raw'
    assert digest(args.registry) == EXPECTED_REGISTRY, 'Registry changed; reconcile before processing'
    assert digest(raw / 'native-land.parquet') == EXPECTED_NATIVE, 'Native geometry changed; revalidate source manifest'
    registry = load(args.registry)['tribes']
    assert len(registry) == len({r['tribe_id'] for r in registry}) == 575
    native = pq.read_table(raw / 'native-land.parquet').to_pylist()
    lands = pq.read_table(args.lands).to_pylist()
    assert len(native) == len({r['land_id'] for r in native}) == len(lands)
    land_index = {r['land_id']: r for r in lands}
    for row in native:
        assert all(row[k] == land_index[row['land_id']][k] for k in ('name', 'GEOID', 'modeled', 'census_year', 'geom_hash'))
    nations = map_nations(registry, load(args.crosswalk)['mappings'], load(args.codes)['crosswalk'], native)
    hashes = {name: digest(path) for name, path in {'registry': args.registry, 'legacy_crosswalk': args.crosswalk, 'legacy_geoid_crosswalk': args.codes, 'current_lands': args.lands, 'native_geometry': raw / 'native-land.parquet'}.items()}
    result = {'schema_version': 'catf-nation-area-v1', 'method_version': METHOD, 'registry_sha256': hashes['registry'], 'dependency_hashes': hashes,
              'geometry_version': 'Native Resilience 2025 Census geometry; b8b55ca0e172a4694e4212108309621d8873615d',
              'nations': nations, 'coverage': {'accounted_nations': len(nations), 'mapping_status': dict(Counter(n['mapping_status'] for n in nations)), 'distinct_modeled_areas': len({a for n in nations for a in n['area_ids']}), 'shared_nations': sum(n['shared'] for n in nations), 'multi_area_nations': sum(len(n['area_ids']) > 1 for n in nations)}}
    save(out / 'nation-area-crosswalk.json', result)
    if args.mapping_only and (out / 'geography.json').exists():
        current = load(out / 'geography.json')
        assert current['dependency_hashes']['native_geometry'] == hashes['native_geometry']
        current['nations'] = nations
        current['dependency_hashes'] = hashes
        current['coverage'].update(result['coverage'])
        for cohort in current['cohorts']:
            cohort['tribe_ids'] = sorted(n['tribe_id'] for n in nations if set(n['area_ids']) & set(cohort['area_ids']))
        save(out / 'geography.json', current)
        save(out / 'coverage.json', current['coverage'])
        save(out / 'cohorts.json', {'schema_version': 'catf-cohorts-v1', 'cohorts': current['cohorts']})
    print(json.dumps(result['coverage']), flush=True)
    return result, native


def membership_rows(area_id, geom, candidates, taxonomy):
    denominator = geom.area
    result = []
    for cid, name, candidate, source_hash in candidates:
        intersection = geom.intersection(candidate)
        area = intersection.area
        if area > 1:
            result.append({'area_id': area_id, 'cohort_id': cid, 'name': name, 'taxonomy': taxonomy,
                           'relation': 'positive_area_intersection', 'status': 'associated',
                           'intersection_area_m2': round(area, 3), 'denominator_area_m2': round(denominator, 3),
                           'share_of_source_area': round(min(1, area / denominator), 9), 'analysis_crs': 'EPSG:6933',
                           'analysis_geometry_sha256': source_hash})
    return result


def display_feature(geom, properties, tolerance=.025, alaska=False):
    g = geom.simplify(tolerance, preserve_topology=True)
    if alaska:
        g = alaska_display(g)
    # Display precision is intentionally separate from all analysis intersections.
    g = shapely.set_precision(g, .00001, mode='valid_output')
    return {'type': 'Feature', 'properties': properties, 'geometry': mapping(g)}


def write_feature_collection(path, features):
    save(path, {'type': 'FeatureCollection', 'features': features})


def prepare_relief(out):
    result = []
    tif = '/vsizip/' + str((out / 'raw/relief.zip').resolve()).replace('\\', '/') + '/NE1_50M_SR/NE1_50M_SR.tif'
    with rasterio.open(tif) as source:
        assert source.crs.to_epsg() == 4326
        for key, bounds in EXTENTS.items():
            west, south, east, north = bounds
            # Use the continuous Mercator longitude window for the Alaska image.
            radius = 6378137
            x0, x1 = [radius * math.radians(x) for x in (west, east)]
            y0, y1 = [radius * math.log(math.tan(math.pi / 4 + math.radians(y) / 2)) for y in (south, north)]
            width = 1440 if key == 'conus' else 1000
            height = round(width * (y1 - y0) / (x1 - x0))
            data = np.zeros((3, height, width), dtype='uint8')
            target_transform = from_bounds(x0, y0, x1, y1, width, height)
            for band in range(3):
                reproject(source=rasterio.band(source, band + 1), destination=data[band], src_transform=source.transform, src_crs=source.crs,
                          dst_transform=target_transform, dst_crs='EPSG:3857', resampling=Resampling.bilinear)
            assert np.count_nonzero(data) > data.size * .9, f'{key} missing relief pixels'
            path = out / 'display' / f'relief-{key}.jpg'
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(np.moveaxis(data, 0, 2)).save(path, quality=80, optimize=True)
            result.append({'path': f'display/{path.name}', 'bounds': bounds, 'projected_extent': [x0, y0, x1, y1], 'crs': 'EPSG:3857', 'width': width, 'height': height, 'view': key,
                           'role': 'Natural Earth 1:50m shaded relief and land-cover artwork; contextual, not a hazard observation', 'max_useful_zoom': 6})
    return result


def finalize(args):
    """Refresh compact display shards and receipts without rerunning spatial analysis."""
    out = args.output
    manifest = load(out / 'geography.json')
    # Older cached display rounding can collapse sub-metre rings. Repair display
    # files only; analytical shapes and computed memberships remain untouched.
    for path in (out / 'display').rglob('*.json'):
        collection = load(path)
        changed = False
        for feature in collection['features']:
            geom = shape(feature['geometry'])
            if not geom.is_valid:
                geom = shapely.set_precision(shapely.make_valid(geom), .00001)
                geom = MultiPolygon(polygon_parts(geom))
                assert geom.is_valid and not geom.is_empty, path
                feature['geometry'] = mapping(geom)
                changed = True
        if changed:
            save(path, collection)
    crosswalk = load(out / 'nation-area-crosswalk.json')
    manifest['nations'] = crosswalk['nations']
    manifest['coverage'].update(crosswalk['coverage'])
    for cohort in manifest['cohorts']:
        cohort['tribe_ids'] = sorted(n['tribe_id'] for n in crosswalk['nations'] if set(n['area_ids']) & set(cohort['area_ids']))
    overlays = {'ecoregions': [], 'basins': []}
    for group in overlays:
        for feature in load(out / f'display/{group}.json')['features']:
            code = feature['properties']['id']
            path = f'display/{group}/{code}.json'
            write_feature_collection(out / path, [feature])
            row = {'id': code, 'name': feature['properties']['name'], 'display_asset': path}
            if shape(feature['geometry']).bounds[3] > 50:
                alaska_path = f'display/{group}/{code}-alaska.json'
                shifted = dict(feature)
                shifted['geometry'] = mapping(alaska_display(shape(feature['geometry'])))
                write_feature_collection(out / alaska_path, [shifted])
                row['alaska_display_asset'] = alaska_path
            overlays[group].append(row)
    manifest['overlays'] = overlays
    overlay_index = {('epa-cec-l3-2010' if group == 'ecoregions' else 'wbd04-20250107', row['id']): row for group, rows in overlays.items() for row in rows}
    for area in manifest['areas']:
        for membership in area['memberships']:
            overlay = overlay_index[(membership['taxonomy'], membership['cohort_id'])]
            membership['display_asset'] = overlay.get('alaska_display_asset', overlay['display_asset']) if area['view'] == 'alaska' else overlay['display_asset']
    manifest['limitations'] = [s.replace('the current page count differs from this pinned feature table.', 'the downloaded feature table has 182 Level III units; older linked metadata says 181.') for s in manifest['limitations']]
    manifest['limitations'] = list(dict.fromkeys(manifest['limitations'] + [
        'EPA/CEC boundaries are broad-scale ecological context at 1:250,000 source scale; small intersections do not establish locally precise ecological boundaries.',
        'Associated land areas carry forward the pinned crosswalk; the association is not an exhaustive inventory of each Nation’s lands.'
    ]))
    sources = {r['id']: r for r in manifest['source_refs']}
    sources['native-resilience']['license_url'] = 'https://data.native-resilience.com/projections/'
    sources['native-resilience']['license_evidence'] = 'Provider portal declares processed data CC0; this is a data license, not a repository-code license claim.'
    sources['census']['attribution'] = 'Repackaged from U.S. Census Bureau 2025 TIGER/Line® data. Statistical boundaries do not determine jurisdiction, ownership or legal land descriptions.'
    sources['census']['sha256'] = digest(out / 'raw/counties-2025.zip')
    sources['natural-earth']['relief_sha256'] = digest(out / 'raw/relief.zip')
    sources['natural-earth']['land_sha256'] = digest(out / 'raw/land.zip')
    receipts = load(out / 'acquisition.json') + [load(out / 'native-acquisition.json')] + load(out / 'wbd-acquisition.json')
    save(out / 'input-manifest.json', {'schema_version': 'catf-geography-inputs-v1', 'recorded_at': datetime.now(timezone.utc).isoformat(), 'producer_sha256': digest(__file__), 'crosswalk_dependencies': crosswalk['dependency_hashes'], 'sources': receipts})
    old_assets = {a['path']: a for a in manifest['assets']}
    assets = []
    for path in sorted((out / 'display').rglob('*')):
        if path.is_file():
            relative = path.relative_to(out).as_posix()
            if relative in {'display/ecoregions.json', 'display/basins.json'}:
                continue  # Private source collections duplicate the runtime shards.
            assets.append({**old_assets.get(relative, {}), 'path': relative, 'bytes': path.stat().st_size, 'sha256': digest(path)})
    manifest['assets'] = assets
    manifest['source_refs'] = list(sources.values())
    save(out / 'geography.json', manifest)
    save(out / 'coverage.json', manifest['coverage'])
    save(out / 'cohorts.json', {'schema_version': 'catf-cohorts-v1', 'cohorts': manifest['cohorts']})
    save(out / 'asset-manifest.json', {'assets': assets, 'total_bytes': sum(a['bytes'] for a in assets), 'relief_bytes': sum(a['bytes'] for a in assets if a['path'].endswith('.jpg')), 'display_vector_bytes': sum(a['bytes'] for a in assets if a['path'].endswith('.json'))})


def build(args):
    if args.finalize_only:
        finalize(args)
        return
    crosswalk, native = prepare_mapping(args)
    if args.mapping_only:
        return
    out, raw = args.output, args.output / 'raw'
    display = out / 'display'
    display.mkdir(parents=True, exist_ok=True)
    native_geoms = {r['land_id']: split_dateline(shapely.from_wkb(r['geometry'])) for r in native}
    assert all(g.is_valid and not g.is_empty for g in native_geoms.values())
    projected = {k: reproject_geometry(g, 'EPSG:4326') for k, g in native_geoms.items()}
    ids = list(projected)
    spatial = shapely.STRtree([projected[k] for k in ids])
    members = defaultdict(list)
    print('Native geometries validated; processing EPA/CEC taxonomy', flush=True)
    epa_crs, epa_rows, epa_geoms = read_vector(raw / 'epa-l3.zip')
    epa_hash = digest(raw / 'epa-l3.zip')
    epa_groups = defaultdict(list)
    epa_names = {}
    for row, geom in zip(epa_rows, epa_geoms):
        epa_groups[row['NA_L3CODE']].append(geom)
        epa_names[row['NA_L3CODE']] = row['NA_L3NAME']
    ecologies, ecological_display = {}, []
    for code, geoms in sorted(epa_groups.items()):
        geo = split_dateline(reproject_geometry(unary_union(geoms), epa_crs, 'EPSG:4326'))
        geom = reproject_geometry(geo, 'EPSG:4326')
        ecologies[code] = geom
        for i in spatial.query(geom, predicate='intersects'):
            members[ids[i]].extend(membership_rows(ids[i], projected[ids[i]], [(code, epa_names[code], geom, epa_hash)], 'epa-cec-l3-2010'))
        if any(geom.intersects(projected[aid]) for aid in ids):
            ecological_display.append(display_feature(geo, {'id': code, 'name': epa_names[code], 'taxonomy': 'epa-cec-l3-2010'}, .06))
    print(f'EPA/CEC complete: {len(epa_groups)} distinct L3 units', flush=True)
    write_feature_collection(display / 'ecoregions.json', ecological_display)
    wbd_index = load(raw / 'wbd04-index.json')
    wbd_expected = {f['properties']['huc4'] for f in wbd_index['features']}
    wbd_geoms, basin_display, wbd_failures = {}, [], []
    checkpoints = out / 'checkpoints'
    checkpoints.mkdir(exist_ok=True)
    for number, code in enumerate(sorted(wbd_expected)):
        path = raw / f'wbd04-{code}.json'
        if not path.exists():
            wbd_failures.append({'id': code, 'status': 'blocked', 'reason': 'Pinned source item not acquired'})
            continue
        source_hash = digest(path)
        key = hashlib.sha256((METHOD + source_hash + EXPECTED_NATIVE).encode()).hexdigest()
        checkpoint = checkpoints / f'wbd-{code}.json'
        cached = load(checkpoint) if checkpoint.exists() else {}
        if cached.get('input_key') == key:
            rows = cached['memberships']
            feature = cached['display']
        else:
            collection = load(path)
            assert len(collection['features']) == collection['numberMatched'] == 1
            source = collection['features'][0]
            assert source['properties']['huc4'] == code
            # Fabric defaults to NAD83 longitude/latitude (CRS83), transformed explicitly.
            geo = split_dateline(reproject_geometry(shape(source['geometry']), 'EPSG:4269', 'EPSG:4326'))
            geom = reproject_geometry(geo, 'EPSG:4326')
            rows = []
            for i in spatial.query(geom, predicate='intersects'):
                rows.extend(membership_rows(ids[i], projected[ids[i]], [(code, source['properties']['name'], geom, source_hash)], 'wbd04-20250107'))
            feature = display_feature(geo, {'id': code, 'name': source['properties']['name'], 'taxonomy': 'wbd04-20250107'}, .025)
            save(checkpoint, {'input_key': key, 'memberships': rows, 'display': feature})
        for row in rows:
            members[row['area_id']].append(row)
        basin_display.append(feature)
        if code in STORIES['columbia-us']['unit_ids'] or code in {'0102', '1501', '1707'}:
            src = load(path)['features'][0]
            wbd_geoms[code] = reproject_geometry(split_dateline(reproject_geometry(shape(src['geometry']), 'EPSG:4269', 'EPSG:4326')), 'EPSG:4326')
        if number % 25 == 0:
            print(f'WBD processed {number + 1}/{len(wbd_expected)}', flush=True)
    write_feature_collection(display / 'basins.json', basin_display)
    print('Processing exact county intersections and authored story scopes', flush=True)
    county_crs, county_rows, county_geoms = read_vector(raw / 'counties-2025.zip')
    county_geoms = [reproject_geometry(split_dateline(reproject_geometry(g, county_crs, 'EPSG:4326')), 'EPSG:4326') for g in county_geoms]
    county_tree = shapely.STRtree(county_geoms)
    cohorts = []
    for key, story in STORIES.items():
        source_geoms = ecologies if story['taxonomy'].startswith('epa') else wbd_geoms
        if any(c not in source_geoms for c in story['unit_ids']):
            cohorts.append({'id': key, **story, 'status': 'unavailable', 'county_fips': [], 'area_ids': [], 'tribe_ids': [], 'missing_reason': 'One or more defining source units unavailable'})
            continue
        geom = unary_union([source_geoms[c] for c in story['unit_ids']])
        county_matches = [int(i) for i in county_tree.query(geom, predicate='intersects') if geom.intersection(county_geoms[i]).area > 1]
        # Clip each story to the United States using the complete 2025 county coverage.
        us_clip = unary_union([geom.intersection(county_geoms[i]) for i in county_matches])
        area_ids = sorted(ids[i] for i in spatial.query(us_clip, predicate='intersects') if projected[ids[i]].intersection(us_clip).area > 1)
        nation_ids = sorted(n['tribe_id'] for n in crosswalk['nations'] if set(n['area_ids']) & set(area_ids))
        county_fips = sorted({county_rows[i]['GEOID'] for i in county_matches})
        geo = reproject_geometry(us_clip, 'EPSG:6933', 'EPSG:4326')
        path = f'display/story-{key}.json'
        write_feature_collection(out / path, [display_feature(geo, {'id': key, 'name': story['label']}, .015)])
        cohorts.append({'id': key, **story, 'status': 'supported', 'source_unit_ids': story['unit_ids'], 'rule': 'Union of listed authoritative units, clipped to 2025 U.S. county coverage; source-area membership requires more than 1 square metre positive intersection in EPSG:6933.',
                        'area_ids': area_ids, 'tribe_ids': nation_ids, 'county_fips': county_fips, 'county_count': len(county_fips),
                        'county_relation': 'Unique whole counties intersecting the story footprint; all county assets, not Nation assets or ecological-area loss.',
                        'county_geometry_sha256': digest(raw / 'counties-2025.zip'), 'geometry_asset': path, 'bounds': list(geo.bounds),
                        'climate_mean_available': False, 'climate_scope': 'Associated source areas remain separate; this membership is not a basin or ecological climate average.'})
    regions = []
    for code in ('1707', '1501', '0102'):
        if code in wbd_geoms:
            geo = reproject_geometry(wbd_geoms[code], 'EPSG:6933', 'EPSG:4326')
            name = next(f['properties']['name'] for f in wbd_index['features'] if f['properties']['huc4'] == code)
            path = f'display/region-huc4-{code}.json'
            write_feature_collection(out / path, [display_feature(geo, {'id': code, 'name': name}, .01)])
            regions.append({'id': code, 'name': name, 'kind': 'huc4', 'geometry_asset': path, 'bounds': list(geo.bounds), 'role': 'Independent USGS HUC4 context; not the authored story climate mean'})
    whatcom = next(i for i, row in enumerate(county_rows) if row['GEOID'] == '53073')
    whatcom_geo = reproject_geometry(county_geoms[whatcom], 'EPSG:6933', 'EPSG:4326')
    write_feature_collection(display / 'region-county-53073.json', [display_feature(whatcom_geo, {'id': '53073', 'name': 'Whatcom County'}, .01)])
    regions.append({'id': '53073', 'name': 'Whatcom County', 'kind': 'county', 'geometry_asset': 'display/region-county-53073.json', 'bounds': list(whatcom_geo.bounds)})
    areas = []
    for row in native:
        aid, geo = row['land_id'], native_geoms[row['land_id']]
        point = geo.representative_point()
        view = 'hawaii' if point.y < 25 and point.x < -150 else ('alaska' if point.y > 50 else 'conus')
        path = f'display/areas/{aid}.json'
        write_feature_collection(out / path, [display_feature(geo, {'id': aid, 'name': row['name'], 'role': geometry_role(row, {})}, .002, view == 'alaska')])
        areas.append({'area_id': aid, 'name': row['name'], 'geometry_role': geometry_role(row, {}), 'geometry_caution': GEOMETRY_CAUTION, 'geometry_status': 'validated',
                      'modeled': row['modeled'], 'source_geometry_hash': row['geom_hash'], 'geometry_vintage': 2025, 'point': [round(point.x, 5), round(point.y, 5)],
                      'point_role': 'Representative point within the public modeled source area; not a Nation office or territorial claim', 'bounds': list((alaska_display(geo) if view == 'alaska' else geo).bounds), 'view': view,
                      'display_asset': path, 'memberships': sorted(members[aid], key=lambda m: (m['taxonomy'], m['cohort_id'])),
                      'ecology_status': 'associated' if any(m['taxonomy'].startswith('epa') for m in members[aid]) else ('outside_product_domain' if view == 'hawaii' else 'unmatched'),
                      'basin_status': 'associated' if any(m['taxonomy'].startswith('wbd') for m in members[aid]) else ('blocked' if wbd_failures else 'unmatched')})
    land_crs, _, land_geoms = read_vector(raw / 'land.zip')
    for view, bounds in EXTENTS.items():
        base = []
        for geom in land_geoms:
            geo = split_dateline(reproject_geometry(geom, land_crs, 'EPSG:4326'))
            if view == 'alaska':
                geo = alaska_display(geo)
            cropped = geo.intersection(box(*bounds))
            if not cropped.is_empty:
                base.append(display_feature(cropped, {'role': 'Natural Earth public-domain land context'}, .04))
        write_feature_collection(display / f'land-{view}.json', base)
    relief = prepare_relief(out)
    assets = []
    for path in sorted(display.rglob('*')):
        if path.is_file():
            row = {'path': path.relative_to(out).as_posix(), 'bytes': path.stat().st_size, 'sha256': digest(path)}
            row.update(next((r for r in relief if r['path'] == row['path']), {}))
            assets.append(row)
    coverage = {**crosswalk['coverage'], 'source_areas': len(areas), 'modeled_source_areas': sum(a['modeled'] for a in areas), 'ecological_units': len(epa_groups), 'wbd_units': len(basin_display), 'wbd_expected': len(wbd_expected), 'wbd_failures': wbd_failures, 'hawaii_roster_nations': sum('HI' in n['states'] for n in crosswalk['nations']), 'hawaii_climate_divisions': sum(a['area_id'].startswith('HI-') for a in areas)}
    manifest = {'schema_version': 'catf-geography-v1', 'method_version': METHOD, 'generated_at': datetime.now(timezone.utc).isoformat(), 'registry_sha256': EXPECTED_REGISTRY,
                'dependency_hashes': crosswalk['dependency_hashes'], 'nations': crosswalk['nations'], 'areas': areas, 'cohorts': cohorts, 'regions': regions, 'extents': EXTENTS, 'assets': assets, 'coverage': coverage,
                'source_refs': [{'id': 'native-resilience', 'url': 'https://github.com/native-resilience/projections/tree/b8b55ca0e172a4694e4212108309621d8873615d', 'license': 'CC0-1.0', 'geometry_sha256': EXPECTED_NATIVE}, {'id': 'epa-cec', 'url': 'https://www.epa.gov/eco-research/ecoregions-north-america', 'version': '2010 revision', 'license': 'Metadata declares no access or use constraints', 'sha256': epa_hash}, {'id': 'usgs-wbd', 'url': 'https://api.water.usgs.gov/fabric/pygeoapi/collections/wbd04_20250107?f=json', 'version': '2025-01-07 snapshot', 'license': 'U.S. federal public data'}, {'id': 'census', 'url': 'https://www2.census.gov/geo/tiger/TIGER2025/COUNTY/tl_2025_us_county.zip', 'version': '2025', 'license': 'U.S. Census Bureau TIGER/Line; repackaged derivative, Census attribution retained; boundaries are not legal land descriptions'}, {'id': 'natural-earth', 'url': 'https://www.naturalearthdata.com/about/terms-of-use/', 'version': 'Natural Earth I 1:50m v3.2.0', 'license': 'Public domain', 'attribution': 'Made with Natural Earth'}],
                'limitations': [GEOMETRY_CAUTION, MAPPING_CAUTION, 'EPA/CEC 2010 taxonomy does not cover Hawaii; the current page count differs from this pinned feature table.', 'Geographic memberships may overlap. Deduplicate Nation IDs, source areas and county FIPS separately.', 'County context includes assets outside Tribal lands and is not a future Tribal loss forecast.', 'Display geometry is simplified separately; all intersections use unsimplified source geometry. Intersections at or below 1 square metre are numerical slivers and excluded.']}
    save(out / 'geography.json', manifest)
    save(out / 'coverage.json', coverage)
    save(out / 'cohorts.json', {'schema_version': 'catf-cohorts-v1', 'cohorts': cohorts})
    save(out / 'asset-manifest.json', {'assets': assets, 'total_bytes': sum(a['bytes'] for a in assets), 'relief_bytes': sum(a['bytes'] for a in assets if a['path'].endswith('.jpg')), 'display_vector_bytes': sum(a['bytes'] for a in assets if a['path'].endswith('.json'))})
    finalize(args)
    print(json.dumps({'coverage': coverage, 'display_bytes': sum(a['bytes'] for a in assets)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'work/geography')
    parser.add_argument('--registry', type=Path, default=Path('I:/data/tcr-policy-scanner/reference/data/tribal_registry.json'))
    parser.add_argument('--crosswalk', type=Path, default=Path('I:/data/tcr-policy-scanner/reference/data/cpre/cmip6_crosswalk.json'))
    parser.add_argument('--codes', type=Path, default=Path('I:/data/tcr-policy-scanner/reference/data/cpre/aiannh_geoid_crosswalk.json'))
    parser.add_argument('--lands', type=Path, default=ROOT / 'work/climate/raw/lands.parquet')
    parser.add_argument('--mapping-only', action='store_true')
    parser.add_argument('--finalize-only', action='store_true')
    build(parser.parse_args())
