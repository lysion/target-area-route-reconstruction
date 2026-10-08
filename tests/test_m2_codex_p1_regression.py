"""Independent replay of Codex F1/F2 counterexamples and F4 contract boundary.

Expected outcomes are based on original parent edges and the accepted
maximality/quality semantics; tests MUST fail against the pre-remediation main.
No producer helper is used to construct the F1 split quality claim.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from target_area_route_reconstruction import (
    QualityPolicy, export_temporal_geojson, project_quality,
    prove_spatial_relation, render_geojson_map, verify_quality,
    verify_spatial_relation,
)
from target_area_route_reconstruction.quality_models import ParentInterval
from target_area_route_reconstruction.models import TrackPosition
from test_geojson_export import make_export
from test_quality_projection import ingest_parts
from test_spatial_relation import arguments, rectangle


def edge_rows(points):
    return ingest_parts([[{"position": pair, "timestamp": stamp}
                          for pair, stamp in points]])


def metric_edges(args):
    proof, entities, _ = make_export(args)
    output = export_temporal_geojson(bundle=entities.bundle, proof=proof, **args)
    assert output.outcome == "produced", output.issues
    fc = json.loads(output.geojson_json)
    return fc, [feature for feature in fc["features"]
                if feature["properties"]["layer"] == "target_metric_edge"]


class CodexRemediationRegressionTests(unittest.TestCase):
    def test_f1_equal_coverage_split_is_invalid_before_m2c(self):
        evidence = edge_rows([
            ((0, 0), "2026-10-07T00:00:00Z"),
            ((.01, 0), "2026-10-07T00:00:10Z"),
            ((.02, 0), "2026-10-07T00:00:20Z"),
        ])
        policy = QualityPolicy()
        actual = project_quality(evidence, policy=policy)
        self.assertEqual(actual.outcome, "produced")
        accepted = actual.projection
        self.assertEqual(accepted.usable_intervals, (
            ParentInterval(TrackPosition(0, 0), TrackPosition(0, 2)),))
        divided = replace(accepted, usable_intervals=(
            ParentInterval(TrackPosition(0, 0), TrackPosition(0, 1)),
            ParentInterval(TrackPosition(0, 1), TrackPosition(0, 2)),
        ))
        self.assertEqual(accepted.excluded_intervals, divided.excluded_intervals)
        self.assertEqual(accepted.diagnostics, divided.diagnostics)
        self.assertEqual(accepted.gaps, divided.gaps)
        self.assertEqual(accepted.evidence_digest, divided.evidence_digest)
        good = verify_quality(accepted, evidence, policy=policy)
        self.assertEqual(good.outcome, "valid", good.issues)
        bad = verify_quality(divided, evidence, policy=policy)
        self.assertEqual(bad.outcome, "invalid", bad)
        self.assertIn("USABLE_INTERVAL_NOT_MAXIMAL", [i.code for i in bad.issues])

        args = arguments(evidence, rectangle(-1, -1, 2, 2), policy)
        result = prove_spatial_relation(**args)
        self.assertEqual(result.outcome, "produced")
        self.assertEqual(verify_spatial_relation(result.proof, **args).outcome, "valid")
        forged_args = {**args, "quality_projection": divided}
        rejected = prove_spatial_relation(**forged_args)
        self.assertNotEqual(rejected.outcome, "produced", rejected)
        self.assertNotEqual(
            verify_spatial_relation(result.proof, **forged_args).outcome, "valid")

    def test_f1_genuine_quality_exclusion_and_source_break_remain_separate(self):
        evidence = edge_rows([
            ((0, 0), "2026-10-07T00:00:00Z"),
            ((.0001, 0), "2026-10-07T00:00:10Z"),
            ((1, 0), "2026-10-07T00:00:11Z"),
            ((1.0001, 0), "2026-10-07T00:00:21Z"),
        ])
        policy = QualityPolicy(max_implied_speed_mps=100)
        q = project_quality(evidence, policy=policy)
        self.assertEqual(q.outcome, "produced")
        self.assertEqual(len(q.projection.usable_intervals), 2)
        self.assertEqual(len(q.projection.excluded_intervals), 1)
        self.assertEqual(verify_quality(q.projection, evidence, policy=policy).outcome, "valid")
        disconnected = ingest_parts([
            [{"position": (0, 0)}, {"position": (.0001, 0)}],
            [{"position": (1, 0)}, {"position": (1.0001, 0)}],
        ])
        result = project_quality(disconnected, policy=QualityPolicy())
        self.assertEqual(result.outcome, "produced")
        self.assertEqual(len(result.projection.usable_intervals), 2)
        self.assertEqual(verify_quality(
            result.projection, disconnected, policy=QualityPolicy()).outcome, "valid")

    def test_f2_indeterminate_screen_is_not_equal_to_passed(self):
        points = [
            ((0, 0), "2026-10-07T00:00:00Z"),
            ((0.000000000001, 0), "2026-10-07T00:00:00.000000000001Z"),
        ]
        args = arguments(edge_rows(points), rectangle(-1, -1, 2, 2),
                         QualityPolicy(max_implied_speed_mps=1))
        q = args["quality_projection"]
        self.assertEqual([d.code for d in q.diagnostics], ["SPEED_NUMERICALLY_INDETERMINATE"])
        fc, edges = metric_edges(args)
        self.assertEqual(len(edges), 1)
        props = edges[0]["properties"]
        self.assertEqual(props["metric"]["status"], "valid")
        self.assertGreater(props["metric"]["speed_mps"], 1e4)
        self.assertEqual(props["speed_screen"], "explicit_m2b_policy_enabled")
        self.assertEqual(props["speed_screen_result"], "indeterminate")
        self.assertEqual(props["speed_screen_reason"], "SPEED_NUMERICALLY_INDETERMINATE")
        self.assertEqual(fc["metadata"]["temporal_overlay"]["screening_counts"]["indeterminate"], 1)
        self.assertEqual(props["metric"]["duration_basis"], "observed_parent_endpoints")
        self.assertIn("not_observed_arrival_time",
                      fc["metadata"]["temporal_overlay"]["clipped_duration_semantics"])
        self.assertIn("not_clipped_fragment",
                      fc["metadata"]["temporal_overlay"]["parent_speed_cap_scope"])
        self.assert_own_display(fc, "2 3", "indeterminate")

    def test_f2_screened_pass_and_unscreened_distinguishable(self):
        evidence = edge_rows([
            ((0, 0), "2026-10-07T00:00:00Z"),
            ((.001, 0), "2026-10-07T00:00:10Z"),
        ])
        for policy, outcome, dash in (
            (QualityPolicy(max_implied_speed_mps=100), "passed", "solid"),
            (QualityPolicy(), "not_screened", "7 3"),
        ):
            with self.subTest(outcome=outcome):
                fc, edges = metric_edges(arguments(
                    evidence, rectangle(-1, -1, 2, 2), policy))
                self.assertEqual(len(edges), 1)
                self.assertEqual(edges[0]["properties"]["speed_screen_result"], outcome)
                self.assert_own_display(fc, dash, outcome)

    def test_f2_nonnumeric_screen_preserves_unavailability_even_if_cap_enabled(self):
        evidence = ingest_parts([[
            {"position": (0, 0)},
            {"position": (.001, 0)},
        ]])
        args = arguments(evidence, rectangle(-1, -1, 2, 2),
                         QualityPolicy(max_implied_speed_mps=100))
        fc, edges = metric_edges(args)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["properties"]["speed_screen_result"], "unavailable")
        self.assertEqual(edges[0]["properties"]["speed_screen_reason"], "SPEED_TIME_MISSING")
        self.assertEqual(edges[0]["properties"]["metric"]["status"], "missing_timestamp")
        self.assertIsNone(edges[0]["properties"]["metric"]["speed_mps"])
        self.assert_own_display(fc, "4 3", "unavailable")

    def test_f4_clip_has_allocated_duration_and_parent_screen_scope(self):
        evidence = edge_rows([
            ((-89, 80), "2026-10-07T00:00:00Z"),
            ((89, 80), "2026-10-08T00:00:00Z"),
        ])
        args = arguments(evidence, rectangle(-1, 79, 1, 81),
                         QualityPolicy(max_implied_speed_mps=30))
        self.assertEqual(args["quality_projection"].diagnostics, ())
        fc, edges = metric_edges(args)
        self.assertEqual(len(edges), 1)
        props = edges[0]["properties"]
        self.assertEqual(props["speed_screen_result"], "passed")
        self.assertEqual(props["speed_screen_reason"], "ADMITTED")
        self.assertEqual(props["metric"]["duration_basis"], "proportional_parent_edge_allocation")
        self.assertGreater(props["metric"]["speed_mps"], 30)
        self.assertLess(props["metric"]["duration_s"], 1500)
        self.assertIn("not_clipped_fragment", fc["metadata"]["temporal_overlay"]["parent_speed_cap_scope"])
        self.assert_own_display(fc, "solid", "passed")

    def assert_own_display(self, fc, dash, screening):
        if shutil.which("node") is None:
            self.skipTest("Node.js unavailable; CI runs mandatory Node.js runtime gate")
        html = render_geojson_map(json.dumps(fc, separators=(",", ":"), ensure_ascii=False))
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "metric.html"
            page.write_text(html, encoding="utf-8")
            cmd = ["node", str(Path(__file__).parent / "m2_codex_screening_dom.cjs"),
                   str(page), dash, screening]
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
