"""Focused offline fixtures for geographic identity, area and display semantics."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from shapely.geometry import box, Polygon, MultiPolygon, shape

spec = importlib.util.spec_from_file_location('geography', Path(__file__).resolve().parents[1] / 'scripts/prepare_geography.py')
geo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geo)


class GeographyTests(unittest.TestCase):
    def test_shared_proxy_unmatched_and_multiarea(self):
        registry = [{'tribe_id': i, 'name': i, 'states': ['AZ']} for i in ('a', 'b', 'c', 'n')]
        lands = [{'land_id': '0010R', 'AIANNHCE': '0010', 'name': 'Example Reservation', 'modeled': True}]
        lands += [{'land_id': f'2430R-{i}', 'AIANNHCE': '2430', 'name': f'Navajo Nation — {i} Agency', 'modeled': True} for i in range(5)]
        old = {'a': {'area_slug': 'Example_Reservation', 'method': 'normalized_exact', 'confidence': 'high'},
               'b': {'area_slug': 'Example_Reservation', 'method': 'host_area', 'confidence': 'medium'},
               'n': {'area_slug': 'old-navajo-name', 'method': 'explicit', 'confidence': 'verified'}}
        rows = {r['tribe_id']: r for r in geo.map_nations(registry, old, {'n': {'geoid': '2430R'}}, lands)}
        self.assertTrue(rows['a']['shared'])
        self.assertEqual(rows['b']['mapping_status'], 'proxy')
        self.assertEqual(rows['c']['area_ids'], [])
        self.assertEqual(rows['c']['mapping_status'], 'unmapped')
        self.assertEqual(len(rows['n']['area_ids']), 5)

    def test_multipart_area_and_boundary_touch(self):
        geom = MultiPolygon([box(0, 0, 2, 2), box(5, 0, 7, 2)])
        rows = geo.membership_rows('a', geom, [('one', 'One', box(0, 0, 1, 2), 'hash'), ('touch', 'Touch', box(7, 0, 8, 2), 'hash')], 'test')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['share_of_source_area'], .25)
        self.assertEqual(rows[0]['denominator_area_m2'], 8)

    def test_provider_documented_rename(self):
        nations = [{'tribe_id': 'cherokee', 'name': 'Eastern Band of Cherokee Indians', 'states': ['NC']}]
        old = {'cherokee': {'area_slug': 'Eastern_Cherokee_Reservation', 'method': 'normalized_exact', 'confidence': 'high'}}
        lands = [{'land_id': '3015R', 'AIANNHCE': '3015', 'name': 'Qualla Boundary', 'modeled': True}]
        row = geo.map_nations(nations, old, {}, lands)[0]
        self.assertEqual(row['area_ids'], ['3015R'])
        self.assertEqual(row['mapping_method'], 'provider_documented_2025_rename')

    def test_equal_area_crs_roundtrip(self):
        polygon = box(-125, 45, -124, 46)
        projected = geo.reproject_geometry(polygon, 'EPSG:4326')
        roundtrip = geo.reproject_geometry(projected, 'EPSG:6933', 'EPSG:4326')
        self.assertLess(roundtrip.hausdorff_distance(polygon), 1e-7)
        self.assertGreater(projected.area, 8e9)

    def test_alaska_dateline_split_and_display_only_unwrap(self):
        crossing = Polygon([(179, 52), (-179, 52), (-179, 54), (179, 54), (179, 52)])
        canonical = geo.split_dateline(crossing)
        self.assertTrue(canonical.is_valid)
        self.assertEqual(len(canonical.geoms), 2)
        self.assertAlmostEqual(canonical.area, 4)
        display = geo.alaska_display(canonical)
        self.assertLess(display.bounds[2] - display.bounds[0], 3)
        self.assertGreater(canonical.bounds[2], 179)
        for part in canonical.geoms:
            self.assertLess(part.bounds[2] - part.bounds[0], 3)

    def test_mainland_alaska_and_hawaii(self):
        for polygon in [box(-150, 60, -149, 61), box(-157, 20, -156, 21)]:
            transformed = geo.split_dateline(polygon)
            self.assertAlmostEqual(transformed.area, 1)
            self.assertGreater(geo.reproject_geometry(transformed, 'EPSG:4326').area, 1e9)
        self.assertIn('not a Nation', geo.geometry_role({'land_id': 'HI-01'}, {}))

    def test_reject_bad_coordinates(self):
        with self.assertRaises(ValueError):
            geo.split_dateline(box(40, -120, 41, -119))

    def test_display_precision_removes_collapsed_ring(self):
        tiny = Polygon([(-122, 40), (-121.9999999, 40), (-122, 40.0000001)])
        geometry = MultiPolygon([box(-124, 40, -123, 41), tiny])
        display = shape(geo.display_feature(geometry, {}, 0)['geometry'])
        self.assertTrue(display.is_valid)
        self.assertFalse(display.is_empty)
        self.assertAlmostEqual(display.area, 1)

    def test_display_does_not_mutate_analysis_and_atomic_determinism(self):
        polygon = box(-100, 40, -99, 41).buffer(.001)
        before = polygon.wkb
        feature = geo.display_feature(polygon, {'id': 'a'}, .1)
        self.assertEqual(polygon.wkb, before)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'result.json'
            geo.save(path, feature)
            first = geo.digest(path)
            geo.save(path, feature)
            self.assertEqual(geo.digest(path), first)
            self.assertFalse(path.with_suffix('.json.tmp').exists())


if __name__ == '__main__':
    unittest.main()
