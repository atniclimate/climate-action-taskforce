"""Accept exact scanner handoff and shared county snapshot; never run a model."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROSTER_HASH = '5db8f52cf44d3a3853f8403cd6dc845a59088f07f42b40a3488575b5cbe7cece'
COUNTY_HASH = 'f6640493f6225f2bee7484c698878807299a0081a1aa163f11695f048e94ab50'
COUNTY_VERSION = ['December 2025']
PINS = {
    'handoff-manifest.json': '74e200fb7fabaaeebbfb11f3f756ccfbc9f6f4cfa500add29a4841e19e2b382c',
    'manifest.json': '7ac3d508f4c35bb995aba94a0583b048a208cbb2653521c18fd4d140e1b290a7',
    'climate_manifest.json': '4fa4cfdbc4270fe27430a52830a0f8f23baf1d10d2d5fed9aa196ab54d488bb4',
    'calculation-verification.json': '857c98342ceb25625acf590304acc230a617f27552f2afa384ecc816f8439b4f',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def require_hash(path, expected):
    if digest(path) != expected:
        raise ValueError(f'Accepted snapshot hash mismatch: {Path(path).name}')


def projection_matches(raw, reduced):
    if isinstance(reduced, dict):
        return isinstance(raw, dict) and all(k in raw and projection_matches(raw[k], v) for k, v in reduced.items())
    if isinstance(reduced, list):
        return isinstance(raw, list) and len(raw) == len(reduced) and all(projection_matches(a, b) for a, b in zip(raw, reduced))
    return raw == reduced


def accept_county_snapshot(path):
    require_hash(path, COUNTY_HASH)
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    versions = sorted({r['NRI_VER'] for r in rows})
    if versions != COUNTY_VERSION:
        raise ValueError('Accepted county NRI version mismatch')
    ids = [r['STCOFIPS'] for r in rows]
    if len(ids) != len(set(ids)) or any(not i or len(i) != 5 for i in ids):
        raise ValueError('Missing or duplicate county identity')
    for row in rows:
        for key, value in row.items():
            if (key == 'EAL_VALT' or key.endswith('_EALT')) and value.strip():
                if not math.isfinite(float(value)) or float(value) < 0:
                    raise ValueError('Invalid county EAL')
    return rows, {'version': versions, 'sha256': COUNTY_HASH}


def verify_bundle(bundle, data_root):
    bundle, data_root = Path(bundle), Path(data_root)
    files = dict(PINS)
    for name, expected in PINS.items():
        require_hash(bundle / name, expected)
    handoff = load(bundle / 'handoff-manifest.json')
    if handoff['status'] != 'passed':
        raise ValueError('Scanner handoff not accepted')
    manifest = load(bundle / 'manifest.json')
    climate_manifest = load(bundle / 'climate_manifest.json')
    outputs = {r['path']: r['sha256'] for r in manifest['outputs']}
    outputs.update({name: r['sha256'] for name, r in climate_manifest['outputs'].items()})
    outputs.update({name: r['sha256'] for name, r in handoff['files'].items()})
    for name, expected in outputs.items():
        if Path(name).name != name:
            raise ValueError('Bundle output must be a direct child')
        require_hash(bundle / name, expected)
    files.update(outputs)
    for name, expected in climate_manifest['inputs'].items():
        if name.startswith('risk/'):
            require_hash(bundle / Path(name).name, expected)
    registry_path = data_root / 'reference/data/tribal_registry.json'
    require_hash(registry_path, ROSTER_HASH)
    registry = load(registry_path)['tribes']
    registry_input = next(r for r in manifest['inputs'] if r['role'] == 'registry')
    if registry_input['sha256'] != ROSTER_HASH:
        raise ValueError('Risk export registry identity mismatch')
    ids = {r['tribe_id'] for r in registry}
    nations = load(bundle / 'nations.json')['nations']
    climate_nations = load(bundle / 'climate_nations.json')['nations']
    for records in [registry, nations, climate_nations]:
        if len(records) != 575 or {r['tribe_id'] for r in records} != ids:
            raise ValueError('Canonical 575 identities differ or contain duplicates')
    profiles = {}
    for nation in nations:
        identity = nation['tribe_id']
        expected_path = f'data/cpre/cpri_profiles/{identity}.json'
        if nation['source']['path'] != expected_path:
            raise ValueError('Unexpected canonical profile path')
        path = data_root / 'output' / expected_path
        require_hash(path, nation['source']['sha256'])
        profile = load(path)
        if profile['tribe_id'] != identity:
            raise ValueError('Canonical profile identity mismatch')
        if not projection_matches(profile, nation['profile']):
            raise ValueError('Reduced profile does not match canonical fields')
        profiles[identity] = profile
    dashboard_path = data_root / 'output/outputs/cpri_dashboard.json'
    dashboard = load(dashboard_path)
    if len(dashboard) != 575 or {r['tribe_id'] for r in dashboard} != ids:
        raise ValueError('Canonical dashboard identities differ')
    for row in dashboard:
        profile = profiles[row['tribe_id']]
        if any(row[k] != profile['primary_cpri'][k] for k in ('cpri_final', 'percentile_rank')):
            raise ValueError('Canonical dashboard/profile values differ')
    files['canonical_dashboard'] = digest(dashboard_path)
    comparison = load(bundle / 'comparison.json')
    if comparison['numerically_changed_nations'] or comparison['added_nation_ids'] or comparison['removed_nation_ids']:
        raise ValueError('Accepted rerun is not numerical reproduction')
    return {'handoff': handoff, 'manifest': manifest, 'climate_manifest': climate_manifest,
            'nations': nations, 'registry': registry, 'profiles': profiles, 'files': files}
