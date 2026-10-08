"""Independent Milestone 2 cross-checkpoint exit witnesses.

Intentionally consumes public APIs and preserved raw source fixtures rather
than relying on producers' internal helpers or prior stage review outcomes.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from target_area_route_reconstruction import (
    QualityPolicy, assemble_spatial_entities, export_geojson,
    export_temporal_geojson, ingest_bytes, ingest_file, project_quality,
    prove_spatial_relation, verify_quality, verify_spatial_entities,
    verify_spatial_relation,
)
from target_area_route_reconstruction.quality_models import ParentReference


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "source-fixtures"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
SHA256 = {row["path"]: row["sha256"] for row in MANIFEST["fixtures"]}


def target(x0=112.89, y0=28.19, x1=112.92, y1=28.22):
    return {
        "schema_version": "0.1.0", "id": "m2-exit-target", "revision_id": "r1",
        "spatial_reference": "OGC:CRS84",
        "geometry": {"type": "Polygon", "coordinates": [[
            [x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0],
        ]]},
        "definition_provenance": {"description": "Independent M2 exit audit witness"},
    }


def run_pipeline(evidence, area):
    policy = QualityPolicy()
    q = project_quality(evidence, policy=policy)
    assert q.outcome == "produced", q.issues
    assert verify_quality(q.projection, evidence, policy=policy).outcome == "valid"
    inputs = dict(
        evidence=evidence, quality_projection=q.projection, quality_policy=policy,
        target_area=area,
        target_reference=ParentReference(area["id"], area["revision_id"]),
    )
    c = prove_spatial_relation(**inputs)
    assert c.outcome == "produced", c.issues
    assert verify_spatial_relation(c.proof, **inputs).outcome == "valid"
    d = assemble_spatial_entities(proof=c.proof, **inputs)
    assert d.outcome in ("produced", "non_assessable"), d.issues
    assert verify_spatial_entities(d.bundle, proof=c.proof, **inputs).outcome == "valid"
    geo = export_geojson(bundle=d.bundle, proof=c.proof, **inputs)
    assert geo.outcome == "produced", geo.issues
    metric = export_temporal_geojson(bundle=d.bundle, proof=c.proof, **inputs)
    assert metric.outcome == "produced", metric.issues
    return c, d, json.loads(geo.geojson_json), json.loads(metric.geojson_json)


def by_layer(fc, layer):
    return [f for f in fc["features"] if f["properties"]["layer"] == layer]


class Milestone2ExitCrossStage(unittest.TestCase):
    def ingest(self, relative):
        src = FIXTURES / relative
        initial = src.read_bytes()
        self.assertEqual(hashlib.sha256(initial).hexdigest(), SHA256[relative],
                         "Independent fixture manifest must match immutable raw input")
        kind = src.suffix[1:]
        evidence = ingest_file(
            src, source_kind=kind, track_source={"id": "m2-exit-source", "revision_id": "r1"}
        )
        self.assertEqual(src.read_bytes(), initial, "M2A must not modify raw input")
        self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(), SHA256[relative])
        return evidence

    def test_actual_fit_and_gpx_are_spatially_equivalent_through_final_view(self):
        # FIT semicircle rounding is permitted within manifest tolerance:
        # identity/revision of different raw files must NOT be conflated.
        outputs = []
        for relative in ("equivalent/basic.gpx", "equivalent/basic.fit"):
            with self.subTest(relative=relative):
                evidence = self.ingest(relative)
                self.assertEqual(evidence.outcome, "success")
                c, d, geo, metric = run_pipeline(
                    evidence, target(112.902, 28.19, 112.908, 28.22)
                )
                self.assertEqual((c.proof.relation, c.proof.coverage_completeness),
                                 ("partial", "complete"))
                self.assertEqual(len(d.bundle.segments), 1)
                self.assertEqual(len(by_layer(geo, "target_segment")), 1)
                self.assertEqual(len(by_layer(metric, "target_metric_edge")), 2)
                self.assertEqual(metric["features"][:len(geo["features"])], geo["features"])
                self.assertTrue(all(edge["properties"]["metric"]["status"] == "valid"
                                    for edge in by_layer(metric, "target_metric_edge")))
                self.assertEqual(metric["metadata"]["relation"], geo["metadata"]["relation"])
                self.assertEqual(metric["metadata"]["coverage_completeness"],
                                 geo["metadata"]["coverage_completeness"])
                outputs.append((evidence, d, geo, metric))
        (first, _d1, first_geo, first_metric), (second, _d2, second_geo, second_metric) = outputs
        self.assertNotEqual(first.canonical_track["revision_id"],
                            second.canonical_track["revision_id"])
        for feature_a, feature_b in zip(by_layer(first_geo, "target_segment"),
                                        by_layer(second_geo, "target_segment")):
            points_a = feature_a["geometry"]["coordinates"]
            points_b = feature_b["geometry"]["coordinates"]
            self.assertEqual(len(points_a), len(points_b))
            for point_a, point_b in zip(points_a, points_b):
                for v1, v2 in zip(point_a, point_b):
                    self.assertLessEqual(abs(v1 - v2), 1e-6)
        for e1, e2 in zip(by_layer(first_metric, "target_metric_edge"),
                          by_layer(second_metric, "target_metric_edge")):
            self.assertEqual(e1["properties"]["parent_edge"],
                             e2["properties"]["parent_edge"])
            self.assertLessEqual(abs(e1["properties"]["metric"]["duration_s"] -
                                     e2["properties"]["metric"]["duration_s"]), 1e-3)

    def test_repeated_full_pipeline_is_byte_deterministic_and_read_only(self):
        evidence = self.ingest("fit/complete-activity.fit")
        area = target(112.902, 28.19, 112.908, 28.22)
        before = evidence.to_json()
        first = run_pipeline(evidence, area)
        second = run_pipeline(evidence, area)
        self.assertEqual(evidence.to_json(), before)
        self.assertEqual(first[0].to_json(), second[0].to_json())
        self.assertEqual(first[1].to_json(), second[1].to_json())
        self.assertEqual(first[2], second[2])
        self.assertEqual(first[3], second[3])

    def test_multi_part_unknown_does_not_add_gap_chord_or_metric(self):
        evidence = self.ingest("gpx/discontinuity.gpx")
        c, d, geo, metric = run_pipeline(evidence, target())
        self.assertEqual(c.proof.relation, "unknown")
        self.assertEqual(c.proof.coverage_completeness, "incomplete")
        self.assertEqual(len(d.bundle.segments), 2)
        self.assertEqual(len(by_layer(metric, "target_metric_edge")), 2)
        self.assertEqual({e["properties"]["parent_edge"]["part_index"]
                          for e in by_layer(metric, "target_metric_edge")}, {0, 1})
        self.assertTrue(all(f["geometry"]["type"] == "Point"
                            for f in by_layer(geo, "gap_endpoint")))
        self.assertFalse(any(f["properties"]["layer"] == "gap" for f in metric["features"]))
        self.assertEqual(geo["metadata"]["coverage_completeness"], "incomplete")
        self.assertEqual(metric["metadata"]["coverage_completeness"], "incomplete")
        self.assertEqual(metric["metadata"]["temporal_overlay"]["counts"]["valid"], 2)

    def test_no_time_retains_spatial_result_but_no_derived_speed(self):
        evidence = self.ingest("gpx/no-timestamps.gpx")
        c, d, geo, metric = run_pipeline(evidence, target())
        self.assertTrue(c.proof.assessable)
        self.assertEqual(c.proof.relation, "inside")
        self.assertEqual(len(d.bundle.segments), 1)
        derived = by_layer(metric, "target_metric_edge")
        self.assertEqual(len(derived), 2)
        self.assertTrue(all(f["properties"]["metric"]["status"] == "missing_timestamp"
                            and f["properties"]["metric"]["speed_mps"] is None
                            and f["properties"]["metric"]["pace_s_per_km"] is None
                            for f in derived))
        self.assertEqual(geo["metadata"]["relation"], metric["metadata"]["relation"])

    def test_no_position_cannot_turn_into_false_outside(self):
        source = self.ingest("fit/no-position.fit")
        self.assertIsNone(source.canonical_track)
        self.assertEqual(source.outcome, "no_positioned_observations")
        self.assertTrue(source.diagnostics)

    def test_singleton_is_nonassessable_even_with_a_positioned_source(self):
        data = (b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="M2-exit">'
                b'<trk><trkseg><trkpt lat="28.200" lon="112.900"/></trkseg></trk></gpx>')
        evidence = ingest_bytes(
            data, source_kind="gpx",
            track_source={"id": "m2-exit-singleton", "revision_id": "r1"},
        )
        self.assertEqual(evidence.outcome, "success")
        c, d, geo, metric = run_pipeline(evidence, target())
        self.assertFalse(c.proof.assessable)
        self.assertIsNone(c.proof.relation)
        self.assertIsNone(c.proof.coverage_completeness)
        self.assertIsNone(d.bundle)
        self.assertEqual(by_layer(metric, "target_metric_edge"), [])
        self.assertEqual(by_layer(geo, "target_segment"), [])
        self.assertIsNone(geo["metadata"]["relation"])


if __name__ == "__main__":
    unittest.main()
