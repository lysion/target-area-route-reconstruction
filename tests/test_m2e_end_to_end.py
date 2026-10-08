"""End-to-end M2A→M2E and adversarial map tests."""
import json
import unittest
from target_area_route_reconstruction import render_geojson_map
from test_geojson_export import make_export
from test_spatial_relation import arguments,route


class M2EEndToEndTests(unittest.TestCase):
    def test_full_pipeline_repeated_visits_to_offline_html(self):
        args=arguments(route([(-1,1),(3,1),(-1,1),(3,1)]))
        proof,assembled,exported=make_export(args)
        self.assertEqual(exported.outcome,"produced",exported.issues)
        fc=json.loads(exported.geojson_json)
        self.assertEqual(len([f for f in fc["features"] if f["properties"]["layer"]=="target_segment"]),3)
        page=render_geojson_map(exported.geojson_json)
        self.assertIn('id="map"',page)
        self.assertIn('id="evidence"',page)
        self.assertIn('data-layer="target_segment"',page)
        self.assertIn("No inferred routes",page)
        self.assertEqual(page,render_geojson_map(exported.geojson_json))

    def test_full_pipeline_unknown_gap_stays_point_only(self):
        args=arguments(route([(1,1),(1.5,1)],[(1,1),(1.5,1)]))
        _,_,exported=make_export(args)
        self.assertEqual(exported.outcome,"produced")
        fc=json.loads(exported.geojson_json)
        self.assertEqual(fc["metadata"]["relation"],"unknown")
        self.assertEqual(fc["metadata"]["coverage_completeness"],"incomplete")
        self.assertEqual(len([f for f in fc["features"] if f["properties"]["layer"]=="gap_endpoint"]),2)
        self.assertFalse(any(f["properties"]["layer"]=="gap" for f in fc["features"]))
        page=render_geojson_map(exported.geojson_json)
        self.assertIn("gap_endpoint",page)

    def test_reject_gap_line_forgery_and_out_of_range(self):
        for geom,layer in [
            ({"type":"LineString","coordinates":[[1,1],[2,2]]},"gap_endpoint"),
            ({"type":"Point","coordinates":[181,2]},"gap_endpoint"),
            ({"type":"Point","coordinates":[True,2]},"gap_endpoint"),
            ({"type":"Point","coordinates":[float("inf"),2]},"gap_endpoint"),
        ]:
            with self.subTest(geom=geom):
                fc={"type":"FeatureCollection","features":[{"type":"Feature",
                    "geometry":geom,"properties":{"layer":layer}}]}
                with self.assertRaises(ValueError):
                    render_geojson_map(json.dumps(fc))

    def test_duplicate_json_members_fail_closed(self):
        doc='{"type":"FeatureCollection","features":[],"features":[]}'
        with self.assertRaises(ValueError):
            render_geojson_map(doc)


if __name__=="__main__":
    unittest.main()
