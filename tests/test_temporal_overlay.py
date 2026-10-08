"""M2F speed/pace derivation tests against accepted M2A→M2E authority."""

from __future__ import annotations

import json
import math
import unittest
from dataclasses import replace

from target_area_route_reconstruction import (
    QualityPolicy, export_temporal_geojson, ingest_bytes,
)
from test_quality_projection import ingest_parts, metric, POLICY
from test_spatial_relation import arguments, rectangle, route
from test_geojson_export import make_export


def projected(args, mode="speed_mps"):
    proof, assembly, base = make_export(args)
    assert base.outcome == "produced", base.issues
    output = export_temporal_geojson(
        bundle=assembly.bundle, proof=proof, metric_mode=mode, **args
    )
    return proof, assembly, base, output


def segments(output):
    return [f for f in json.loads(output.geojson_json)["features"]
            if f["properties"]["layer"] == "target_metric_edge"]


class M2FTemporalOverlayTests(unittest.TestCase):
    def test_constant_speed_and_pace_are_interval_properties(self):
        args = arguments(metric("constant-speed"), rectangle(-1, -1, 1, 1))
        _, assembly, base, output = projected(args)
        self.assertEqual(output.outcome, "produced", output.issues)
        edges = segments(output)
        self.assertEqual(len(edges), 2)
        self.assertEqual([x["properties"]["parent_edge"]["observation_index"]
                          for x in edges], [0, 1])
        speeds = [x["properties"]["metric"]["speed_mps"] for x in edges]
        self.assertAlmostEqual(speeds[0], speeds[1], places=6)
        self.assertAlmostEqual(speeds[0], 11.13195, delta=.01)
        for edge in edges:
            info = edge["properties"]["metric"]
            self.assertEqual(info["status"], "valid")
            self.assertAlmostEqual(info["duration_s"], 10)
            self.assertAlmostEqual(info["pace_s_per_km"], 1000 / info["speed_mps"])
            self.assertEqual(edge["properties"]["metric_algorithm"]["version"], "0.1.0")
        # All accepted M2E features remain unchanged in output and order.
        self.assertEqual(json.loads(output.geojson_json)["features"][:len(json.loads(base.geojson_json)["features"])],
                         json.loads(base.geojson_json)["features"])
        self.assertEqual(output.geojson_json, projected(args)[3].geojson_json)

    def test_acceleration_is_not_smoothed_to_one_segment_average(self):
        args = arguments(metric("acceleration-deceleration"), rectangle(-1, -1, 1, 1))
        _, _, _, output = projected(args)
        values = [e["properties"]["metric"]["speed_mps"] for e in segments(output)]
        self.assertEqual(len(values), 3)
        self.assertGreater(values[1], values[0])
        self.assertGreater(values[1], values[2])
        self.assertAlmostEqual(values[0], values[2], places=6)

    def test_fractional_clip_inherits_strict_original_edge_time(self):
        evidence = ingest_parts([[{"position": (-1, 1), "timestamp": "2026-10-07T00:00:00Z"},
                                  {"position": (3, 1), "timestamp": "2026-10-07T00:00:40Z"}]])
        args = arguments(evidence, rectangle())
        _, assembly, _, output = projected(args)
        self.assertEqual(len(assembly.bundle.segments), 1)
        edges = segments(output)
        self.assertEqual(len(edges), 1)
        info = edges[0]["properties"]["metric"]
        self.assertAlmostEqual(info["duration_s"], 20)
        self.assertEqual(edges[0]["properties"]["start_position"]["fraction_to_next"], .25)
        self.assertEqual(edges[0]["properties"]["end_position"]["fraction_to_next"], .75)
        self.assertEqual(edges[0]["geometry"], assembly.bundle.segments[0]["geometry"])

    def test_missing_timestamps_keep_spatial_geometry_neutral(self):
        args = arguments(metric("missing-timestamps"), rectangle(-1, -1, 1, 1))
        _, _, base, output = projected(args)
        self.assertEqual(output.outcome, "produced", output.issues)
        info = segments(output)[0]["properties"]["metric"]
        self.assertEqual(info["status"], "missing_timestamp")
        self.assertIsNone(info["speed_mps"])
        self.assertIsNone(info["pace_s_per_km"])
        self.assertEqual(json.loads(base.geojson_json)["metadata"]["relation"], "inside")
        self.assertEqual(json.loads(output.geojson_json)["metadata"]["relation"], "inside")

    def test_nonincreasing_and_partial_missing_timestamps_never_bleed(self):
        data = [
            {"position": (0, 0), "timestamp": "2026-10-07T00:00:20Z"},
            {"position": (.001, 0), "timestamp": "2026-10-07T00:00:10Z"},
            {"position": (.002, 0), "timestamp": "2026-10-07T00:00:20Z"},
            {"position": (.003, 0)},
        ]
        args = arguments(ingest_parts([data]), rectangle(-1, -1, 1, 1))
        _, _, _, output = projected(args)
        self.assertEqual([e["properties"]["metric"]["status"] for e in segments(output)],
                         ["nonincreasing_timestamp", "valid", "missing_timestamp"])
        self.assertIsNone(segments(output)[0]["properties"]["speed_mps"] if
                          "speed_mps" in segments(output)[0]["properties"] else
                          segments(output)[0]["properties"]["metric"]["speed_mps"])

    def test_pause_stays_stationary_event_and_not_moving_chord(self):
        args = arguments(metric("pause"), rectangle(-1, -1, 1, 1))
        _, _, _, output = projected(args)
        fc = json.loads(output.geojson_json)
        temporal = fc["metadata"]["temporal_overlay"]
        self.assertEqual(temporal["counts"], {"valid": 2, "unavailable": 0, "stationary": 1})
        self.assertEqual(len(temporal["stationary_observations"]), 1)
        event = temporal["stationary_observations"][0]
        self.assertEqual(event["metric"]["status"], "valid")
        self.assertEqual(event["metric"]["speed_mps"], 0)
        self.assertIsNone(event["metric"]["pace_s_per_km"])
        self.assertEqual(event["metric"]["duration_s"], 40)
        self.assertEqual(len(segments(output)), 2)

    def test_source_gap_preserves_two_occurrences_and_no_metric_bridge(self):
        rows = [[{"position": (0, 0), "timestamp": "2026-10-07T00:00:00Z"},
                 {"position": (.001, 0), "timestamp": "2026-10-07T00:00:10Z"}],
                [{"position": (.01, 0), "timestamp": "2026-10-07T00:00:20Z"},
                 {"position": (.011, 0), "timestamp": "2026-10-07T00:00:30Z"}]]
        args = arguments(ingest_parts(rows), rectangle(-1, -1, 1, 1))
        _, _, _, output = projected(args)
        fc = json.loads(output.geojson_json)
        self.assertEqual(len(segments(output)), 2)
        self.assertEqual({e["properties"]["parent_edge"]["part_index"] for e in segments(output)}, {0, 1})
        self.assertTrue(all(e["geometry"]["coordinates"][0][0] < .002 or
                            e["geometry"]["coordinates"][0][0] > .009 for e in segments(output)))
        self.assertEqual(fc["metadata"]["relation"], "unknown")
        self.assertEqual(fc["metadata"]["coverage_completeness"], "incomplete")

    def test_explicit_quality_exclusion_cannot_get_metric(self):
        args = arguments(metric("gps-jump"), rectangle(.2, -1, .8, 1), POLICY)
        _, _, _, output = projected(args)
        self.assertEqual(output.outcome, "produced", output.issues)
        self.assertEqual(segments(output), [])
        self.assertEqual(json.loads(output.geojson_json)["metadata"]["temporal_overlay"]["counts"]["valid"], 0)

    def test_no_geometry_does_not_invent_metric_or_assessment(self):
        args = arguments(route([(1, 1)]))
        _, assembly, _, output = projected(args)
        self.assertIsNone(assembly.bundle)
        self.assertEqual(output.outcome, "produced")
        self.assertEqual(segments(output), [])
        self.assertIsNone(json.loads(output.geojson_json)["metadata"]["relation"])

    def test_invalid_mode_and_stale_snapshot_fail_closed(self):
        args = arguments(metric("constant-speed"), rectangle(-1, -1, 1, 1))
        proof, assembly, _, _ = projected(args)
        for bad_mode in (None, "heart_rate", False, 42):
            with self.subTest(mode=bad_mode):
                output = export_temporal_geojson(
                    bundle=assembly.bundle, proof=proof, metric_mode=bad_mode, **args)
                self.assertEqual(output.outcome, "invalid_input")
                self.assertIsNone(output.geojson_json)
        stale = replace(assembly.bundle, assessment_json='{"relation":"outside",' + assembly.bundle.assessment_json[1:])
        output = export_temporal_geojson(bundle=stale, proof=proof, **args)
        self.assertEqual(output.outcome, "invalid_input")
        self.assertIsNone(output.geojson_json)

    def test_pace_view_preserves_all_derived_evidence(self):
        args = arguments(metric("constant-speed"), rectangle(-1, -1, 1, 1))
        _, _, _, speed = projected(args)
        _, _, _, pace = projected(args, "pace_s_per_km")
        self.assertEqual(segments(speed), segments(pace))
        self.assertEqual(json.loads(pace.geojson_json)["metadata"]["temporal_overlay"]["mode"], "pace_s_per_km")


if __name__ == "__main__":
    unittest.main()
