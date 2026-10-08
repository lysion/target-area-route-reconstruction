"""M2E export contract witnesses: authority, occurrence, no-gap-chord, null endpoints."""

import copy
import json
import unittest
from dataclasses import replace

from target_area_route_reconstruction import (
    QualityPolicy, assemble_spatial_entities, export_geojson, ingest_bytes,
    prove_spatial_relation,
)
from test_spatial_relation import arguments, rectangle, route
from test_quality_projection import ROOT


def make_export(args, *, include_outside=True):
    m2c = prove_spatial_relation(**args)
    assert m2c.outcome == "produced", m2c.issues
    m2d = assemble_spatial_entities(proof=m2c.proof, **args)
    assert m2d.outcome in ("produced", "non_assessable"), m2d.issues
    result = export_geojson(bundle=m2d.bundle, proof=m2c.proof,
                            include_outside=include_outside, **args)
    return m2c.proof, m2d, result


class M2EGeoJSONTests(unittest.TestCase):
    def test_partial_crossing_yields_exact_target_and_outside_fragments(self):
        args = arguments(route([(-1, 1), (3, 1)]))
        proof, assembled, exported = make_export(args)
        self.assertEqual(exported.outcome, "produced", exported.issues)
        fc = json.loads(exported.geojson_json)
        self.assertEqual(fc["type"], "FeatureCollection")
        layers = [f["properties"]["layer"] for f in fc["features"]]
        self.assertEqual(layers.count("target_area"), 1)
        self.assertEqual(layers.count("target_segment"), 1)
        self.assertEqual(layers.count("observed_outside"), len(proof.outside_evidence_intervals))
        self.assertEqual(layers.count("gap_endpoint"), 0)
        segment_feature = next(f for f in fc["features"] if f["properties"]["layer"] == "target_segment")
        self.assertEqual(segment_feature["geometry"], assembled.bundle.segments[0]["geometry"])
        self.assertEqual(segment_feature["properties"]["start_position"],
                         assembled.bundle.segments[0]["start_position"])
        self.assertEqual(fc["metadata"]["relation"], "partial")
        self.assertEqual(fc["metadata"]["coverage_completeness"], "complete")
        self.assertEqual(exported.geojson_json, make_export(args)[2].geojson_json)

    def test_repeated_visits_preserve_occurrences_and_order(self):
        args = arguments(route([(-1, 1), (3, 1), (-1, 1), (3, 1)]))
        _, assembled, result = make_export(args, include_outside=False)
        self.assertEqual(result.outcome, "produced")
        feats = json.loads(result.geojson_json)["features"]
        segs = [f for f in feats if f["properties"]["layer"] == "target_segment"]
        self.assertEqual(len(segs), 3)
        self.assertEqual([f["properties"]["ordinal"] for f in segs], [0, 1, 2])
        self.assertEqual([f["properties"]["target_segment"]["id"] for f in segs],
                         [s["id"] for s in assembled.bundle.segments])
        self.assertEqual(len({f["properties"]["target_segment"]["id"] for f in segs}), 3)

    def test_relevant_gap_draws_only_real_endpoints_no_connection(self):
        args = arguments(route([(1, 1), (1.5, 1)], [(1, 1), (1.5, 1)]))
        proof, _, result = make_export(args)
        self.assertEqual(result.outcome, "produced")
        fc = json.loads(result.geojson_json)
        self.assertEqual(fc["metadata"]["relation"], "unknown")
        self.assertEqual(fc["metadata"]["coverage_completeness"], "incomplete")
        self.assertEqual(len(fc["metadata"]["gaps"]), 1)
        self.assertTrue(fc["metadata"]["gaps"][0]["target_coverage_unresolved"])
        lines = [f for f in fc["features"] if f["geometry"]["type"] == "LineString"]
        self.assertEqual(len([f for f in lines if f["properties"]["layer"] == "target_segment"]), 2)
        points = [f for f in fc["features"] if f["geometry"]["type"] == "Point"]
        self.assertEqual(len(points), 2)
        self.assertEqual({f["properties"]["side"] for f in points}, {"start", "end"})
        self.assertFalse(any(f["properties"]["layer"] == "gap" for f in lines))

    def test_leading_and_trailing_unknown_endpoints_are_not_fabricated(self):
        for side in ("leading", "trailing"):
            with self.subTest(side=side):
                evidence = ingest_bytes(
                    (ROOT / "tests/m2d-contract" / (side + "-gap.gpx")).read_bytes(),
                    source_kind="gpx", track_source={"id": "source", "revision_id": "r1"})
                args = arguments(evidence, policy=QualityPolicy())
                _, _, result = make_export(args)
                self.assertEqual(result.outcome, "produced", result.issues)
                fc = json.loads(result.geojson_json)
                self.assertEqual(len(fc["metadata"]["gaps"]), 1)
                missing_side = "start" if side == "leading" else "end"
                self.assertIsNone(fc["metadata"]["gaps"][0][missing_side])
                points = [f for f in fc["features"] if f["properties"]["layer"] == "gap_endpoint"]
                self.assertEqual(len(points), 1)
                self.assertNotEqual(points[0]["properties"]["side"], missing_side)

    def test_nonassessable_is_not_falsely_outside(self):
        args = arguments(route([(1, 1)]))
        proof, assembled, result = make_export(args)
        self.assertFalse(proof.assessable)
        self.assertIsNone(assembled.bundle)
        self.assertEqual(result.outcome, "produced")
        fc = json.loads(result.geojson_json)
        self.assertFalse(fc["metadata"]["assessable"])
        self.assertIsNone(fc["metadata"]["relation"])
        self.assertIsNone(fc["metadata"]["coverage_completeness"])
        self.assertEqual([f["properties"]["layer"] for f in fc["features"]], ["target_area"])

    def test_verifier_rejects_stale_or_tampered_m2d_before_export(self):
        args = arguments(route([(-1, 1), (3, 1)]))
        proof, m2d, _ = make_export(args)
        bad_bundle = replace(
            m2d.bundle,
            assessment_json='{"relation":"outside",' + m2d.bundle.assessment_json[1:])
        failed = export_geojson(bundle=bad_bundle, proof=proof, **args)
        self.assertEqual(failed.outcome, "invalid_input")
        self.assertIsNone(failed.geojson_json)
        self.assertEqual(failed.issues[0].code, "M2E_SPATIAL_ENTITIES_INVALID")
        self.assertIn("M2D_DUPLICATE_JSON_MEMBER", [e.code for e in failed.issues])
        bad_args = copy.deepcopy(args)
        bad_args["target_area"]["geometry"]["coordinates"][0][1][0] += .1
        stale = export_geojson(bundle=m2d.bundle, proof=proof, **bad_args)
        self.assertEqual(stale.outcome, "invalid_input")
        self.assertEqual(stale.issues[0].code, "M2E_SPATIAL_PROOF_INVALID")

    def test_invalid_export_option_never_returns_geojson(self):
        args = arguments(route([(-1, 1), (3, 1)]))
        proof, m2d, _ = make_export(args)
        for invalid in (0, 1, None, "yes"):
            with self.subTest(invalid=invalid):
                result = export_geojson(
                    bundle=m2d.bundle, proof=proof, include_outside=invalid, **args)
                self.assertEqual(result.outcome, "invalid_input")
                self.assertIsNone(result.geojson_json)
                self.assertEqual(result.issues[0].code, "M2E_EXPORT_OPTION_INVALID")


if __name__ == "__main__":
    unittest.main()
