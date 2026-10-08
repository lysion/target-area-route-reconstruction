"""Adversarial independent witnesses for extreme timing, GPS jumps and lineage.

Metric values are cross-checked against explicit source times and geodesic
physical distance; the producer is never allowed to fill a GPS gap or silently
change the caller's quality policy.
"""

from __future__ import annotations

import json
import math
import unittest
from fractions import Fraction

from geographiclib.geodesic import Geodesic

from target_area_route_reconstruction import QualityPolicy, export_temporal_geojson
from test_quality_projection import ingest_parts, metric
from test_geojson_export import make_export
from test_spatial_relation import arguments, rectangle


def overlay(args):
    proof, entities, _ = make_export(args)
    result = export_temporal_geojson(bundle=entities.bundle, proof=proof, **args)
    assert result.outcome == "produced", result.issues
    return json.loads(result.geojson_json)


def edge_features(collection):
    return [item for item in collection["features"]
            if item["properties"]["layer"] == "target_metric_edge"]


def source(rows):
    return arguments(ingest_parts([rows]), rectangle(-1, -1, 2, 2))


class M2FAdversarialTests(unittest.TestCase):
    def test_extreme_gps_jump_without_quality_cap_is_math_valid_not_speed_verified(self):
        args = arguments(metric("gps-jump"), rectangle(-1, -1, 2, 2),
                         QualityPolicy())
        fc = overlay(args)
        edges = edge_features(fc)
        self.assertEqual(len(edges), 3)
        jump = edges[1]
        self.assertGreater(jump["properties"]["metric"]["speed_mps"], 10000)
        self.assertEqual(jump["properties"]["metric"]["status"], "valid")
        self.assertEqual(jump["properties"]["speed_screen"], "not_screened")
        temporal = fc["metadata"]["temporal_overlay"]
        self.assertEqual(temporal["speed_screen"], "not_screened")
        self.assertIsNone(temporal["speed_cap_mps"])
        self.assertIn("not_motion_truth", temporal["valid_status_means"])

    def test_identical_jump_is_absent_when_explicit_quality_screen_enabled(self):
        args = arguments(metric("gps-jump"), rectangle(-1, -1, 2, 2),
                         QualityPolicy(max_implied_speed_mps=20))
        fc = overlay(args)
        self.assertEqual(fc["metadata"]["temporal_overlay"]["speed_screen"],
                         "explicit_m2b_policy_enabled")
        self.assertEqual(fc["metadata"]["temporal_overlay"]["speed_cap_mps"], 20)
        edges = edge_features(fc)
        self.assertEqual([e["properties"]["parent_edge"]["observation_index"]
                          for e in edges], [0, 2])
        self.assertTrue(all(e["properties"]["speed_screen"] ==
                            "explicit_m2b_policy_enabled" for e in edges))
        self.assertTrue(any(g["kind"] == "quality_exclusion"
                            for g in fc["metadata"]["gaps"]))
        self.assertEqual(fc["metadata"]["relation"], "unknown")

    def test_subsecond_fraction_preserved_not_truncated_to_microseconds(self):
        # GPX ingestion keeps full fractional UTC precision beyond Python's
        # datetime microseconds; elapsed uses exact UTC Fractions.
        rows = [
            {"position": (0, 0), "timestamp": "2026-10-07T00:00:00.000000000001Z"},
            {"position": (.001, 0), "timestamp": "2026-10-07T00:00:00.000000000003Z"},
        ]
        fc = overlay(source(rows))
        item = edge_features(fc)[0]["properties"]["metric"]
        self.assertEqual(item["status"], "valid")
        self.assertAlmostEqual(item["duration_s"], 2e-12)
        manual_distance = Geodesic.WGS84.Inverse(0, 0, 0, .001)["s12"]
        self.assertAlmostEqual(item["distance_m"], manual_distance, places=8)
        self.assertAlmostEqual(item["speed_mps"], manual_distance / (2e-12), delta=manual_distance * 1e-2)

    def test_underflow_duration_cannot_be_reported_as_valid_zero_seconds(self):
        # A positive, UTC-exact duration can be too small for binary64.
        tiny = "0" * 350 + "1"
        rows = [
            {"position": (0, 0), "timestamp": "2026-10-07T00:00:00Z"},
            {"position": (.001, 0), "timestamp": "2026-10-07T00:00:00." + tiny + "Z"},
        ]
        fc = overlay(source(rows))
        item = edge_features(fc)[0]["properties"]["metric"]
        self.assertEqual(item["status"], "metric_unavailable")
        self.assertIsNone(item["duration_s"])
        self.assertIsNone(item["speed_mps"])
        self.assertIsNone(item["pace_s_per_km"])

    def test_equal_time_is_invalid_but_spatial_geometry_is_retained(self):
        rows = [
            {"position": (0, 0), "timestamp": "2026-10-07T00:00:10Z"},
            {"position": (.001, 0), "timestamp": "2026-10-07T00:00:10Z"},
        ]
        fc = overlay(source(rows))
        item = edge_features(fc)[0]
        self.assertEqual(item["properties"]["metric"]["status"],
                         "nonincreasing_timestamp")
        self.assertIsNone(item["properties"]["metric"]["speed_mps"])
        self.assertEqual(item["geometry"]["type"], "LineString")
        self.assertEqual(fc["metadata"]["relation"], "inside")

    def test_planar_dateline_geometry_is_not_silently_reinterpreted_geodesically(self):
        rows = [
            {"position": (179, 0), "timestamp": "2026-10-07T00:00:00Z"},
            {"position": (-179, 0), "timestamp": "2026-10-07T00:01:00Z"},
        ]
        args = arguments(ingest_parts([rows]), rectangle(-180, -90, 180, 90))
        fc = overlay(args)
        edges = edge_features(fc)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["properties"]["metric"]["status"],
                         "planar_dateline_ambiguous")
        self.assertIsNone(edges[0]["properties"]["metric"]["speed_mps"])
        self.assertEqual(edges[0]["geometry"]["coordinates"], [[179, 0], [-179, 0]])

    def test_mixed_complete_time_across_same_segment_cannot_impute_missing_middle(self):
        rows = [
            {"position": (0, 0), "timestamp": "2026-10-07T00:00:00Z"},
            {"position": (.001, 0), "timestamp": "2026-10-07T00:00:10Z"},
            {"position": (.002, 0)},
            {"position": (.003, 0), "timestamp": "2026-10-07T00:00:30Z"},
            {"position": (.004, 0), "timestamp": "2026-10-07T00:00:40Z"},
        ]
        fc = overlay(source(rows))
        edges = edge_features(fc)
        self.assertEqual([e["properties"]["metric"]["status"] for e in edges],
                         ["valid", "missing_timestamp", "missing_timestamp", "valid"])
        self.assertEqual([e["properties"]["parent_edge"]["observation_index"]
                          for e in edges], [0, 1, 2, 3])
        self.assertEqual(fc["metadata"]["temporal_overlay"]["counts"]["unavailable"], 2)
        self.assertEqual(fc["metadata"]["temporal_overlay"]["counts"]["valid"], 2)

    def test_fractional_time_seconds_use_exact_source_edge_not_adjacent_timestamp(self):
        rows = [
            {"position": (-1, 1), "timestamp": "2026-10-07T00:00:00Z"},
            {"position": (3, 1), "timestamp": "2026-10-07T00:00:00.040Z"},
        ]
        args = arguments(ingest_parts([rows]), rectangle(0, 0, 2, 2))
        fc = overlay(args)
        edge = edge_features(fc)[0]
        metric = edge["properties"]["metric"]
        self.assertAlmostEqual(metric["duration_s"], .02, places=12)
        self.assertEqual(edge["properties"]["start_position"]["fraction_to_next"], .25)
        self.assertEqual(edge["properties"]["end_position"]["fraction_to_next"], .75)
        self.assertEqual(fc["metadata"]["relation"], "partial")


if __name__ == "__main__":
    unittest.main()
