"""M2E adversarial geometry and authority consistency witnesses."""

from __future__ import annotations

import copy
import json
import math
import unittest
from dataclasses import replace

from target_area_route_reconstruction import export_geojson, render_geojson_map
from test_geojson_export import make_export
from test_spatial_relation import arguments, rectangle, route


class M2EAdversarialTests(unittest.TestCase):
    def test_hole_and_multipolygon_are_exported_without_modification(self):
        hole = rectangle(-2, -2, 2, 2)
        hole["geometry"]["coordinates"].append(
            [[-.5, -.5], [-.5, .5], [.5, .5], [.5, -.5], [-.5, -.5]]
        )
        multi = rectangle()
        multi["geometry"] = {"type": "MultiPolygon", "coordinates": [
            rectangle(0, 0, 1, 2)["geometry"]["coordinates"],
            rectangle(2, 0, 3, 2)["geometry"]["coordinates"],
        ]}
        for target in (hole, multi):
            with self.subTest(kind=target["geometry"]["type"]):
                args = arguments(route([(-1, 0), (4, 0)]), target)
                _, _, output = make_export(args)
                self.assertEqual(output.outcome, "produced", output.issues)
                fc = json.loads(output.geojson_json)
                area = next(f for f in fc["features"] if f["properties"]["layer"] == "target_area")
                self.assertEqual(area["geometry"], target["geometry"])
                page = render_geojson_map(output.geojson_json)
                self.assertIn('"fill-rule":"evenodd"', page)
                self.assertIn("No inferred routes", page)

    def test_outside_entirely_has_no_target_segment(self):
        args = arguments(route([(-2, -1), (-1, -1)]))
        proof, assembled, output = make_export(args)
        self.assertEqual(output.outcome, "produced", output.issues)
        self.assertEqual(assembled.bundle.segments, ())
        self.assertEqual(proof.relation, "outside")
        fc = json.loads(output.geojson_json)
        self.assertEqual(fc["metadata"]["relation"], "outside")
        self.assertEqual(fc["metadata"]["coverage_completeness"], "complete")
        self.assertFalse(any(f["properties"]["layer"] == "target_segment" for f in fc["features"]))
        self.assertTrue(any(f["properties"]["layer"] == "observed_outside" for f in fc["features"]))

    def test_hide_outside_never_changes_spatial_assessment(self):
        args = arguments(route([(-1, 1), (3, 1)]))
        proof, assembled, original = make_export(args)
        hidden = export_geojson(
            bundle=assembled.bundle, proof=proof, include_outside=False, **args
        )
        self.assertEqual(hidden.outcome, "produced", hidden.issues)
        a, b = (json.loads(item.geojson_json) for item in (original, hidden))
        self.assertEqual(a["metadata"], b["metadata"])
        self.assertEqual(
            [f for f in a["features"] if f["properties"]["layer"] == "target_segment"],
            [f for f in b["features"] if f["properties"]["layer"] == "target_segment"],
        )
        self.assertFalse(any(f["properties"]["layer"] == "observed_outside" for f in b["features"]))

    def test_forged_snapshot_and_stale_policy_fail_closed(self):
        args = arguments(route([(.25, 1), (1.5, 1)]))
        proof, assembled, _ = make_export(args)
        segments = list(assembled.bundle.segments)
        segments[0]["geometry"]["coordinates"][0][0] = math.nextafter(
            segments[0]["geometry"]["coordinates"][0][0], math.inf
        )
        forged = replace(
            assembled.bundle, segment_json=tuple(json.dumps(seg) for seg in segments)
        )
        invalid = export_geojson(bundle=forged, proof=proof, **args)
        self.assertEqual(invalid.outcome, "invalid_input")
        self.assertIsNone(invalid.geojson_json)
        self.assertIn("M2D_CANONICAL_SNAPSHOT_MISMATCH", [i.code for i in invalid.issues])

        # Do not let an otherwise valid snapshot silently gain new authority.
        changed = copy.deepcopy(args)
        changed["target_reference"] = replace(args["target_reference"], revision_id="stale")
        rejected = export_geojson(bundle=assembled.bundle, proof=proof, **changed)
        self.assertEqual(rejected.outcome, "invalid_input")
        self.assertIsNone(rejected.geojson_json)

    def test_malformed_geojson_nesting_fails_before_html(self):
        polygons = [
            {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 1]]]},
            {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 1], [2, 2]]]},
            {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0]]]]},
        ]
        other = [
            ("gap_endpoint", {"type": "Point", "coordinates": [[0, 0], [1, 1]]}),
            ("gap_endpoint", {"type": "Point", "coordinates": [0, True]}),
            ("target_segment", {"type": "LineString", "coordinates": [[0, 0]]}),
            ("target_segment", {"type": "LineString", "coordinates": [[0, 0], [0, 0]]}),
            ("target_segment", {"type": "LineString", "coordinates": [0, 1]}),
            ("observed_outside", {"type": "LineString", "coordinates": [[0, 0], [181, 1]]}),
        ] + [("target_area", geometry) for geometry in polygons]
        for layer, geometry in other:
            with self.subTest(layer=layer, geometry=geometry):
                fc = {"type": "FeatureCollection", "features": [
                    {"type": "Feature", "properties": {"layer": layer}, "geometry": geometry}
                ]}
                with self.assertRaises(ValueError):
                    render_geojson_map(json.dumps(fc))

    def test_unicode_provenance_does_not_break_json_script_boundary(self):
        payload = '</script><script>globalThis.injected=1</script> &     <svg/onload=alert(1)>'
        fc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"layer": "gap_endpoint", "text": payload},
             "geometry": {"type": "Point", "coordinates": [0, 0]}}
        ]}
        page = render_geojson_map(json.dumps(fc), title=payload)
        self.assertNotIn('</script><script>globalThis.injected=1', page)
        self.assertIn("u003c", page)
        self.assertIn("&lt;/script&gt;", page)
        self.assertNotIn("<svg/onload", page)


if __name__ == "__main__":
    unittest.main()
