"""Milestone 2 exit smoke against an installed wheel, outside source checkout.

This file is copied into the isolated venv's working directory by CI.
Only raw fixture bytes are read from the checkout. No test modules, source
package directory or editable install can supply implementation code.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import target_area_route_reconstruction as core
from target_area_route_reconstruction.quality_models import ParentReference


def target():
    return {
        "schema_version": "0.1.0", "id": "m2-exit-isolated", "revision_id": "r1",
        "spatial_reference": "OGC:CRS84",
        "geometry": {"type": "Polygon", "coordinates": [[
            [112.902, 28.19], [112.908, 28.19], [112.908, 28.22],
            [112.902, 28.22], [112.902, 28.19],
        ]]},
        "definition_provenance": {"description": "Independent installed-wheel M2 exit check"},
    }


def pipeline(evidence, polygon):
    policy = core.QualityPolicy()
    projection = core.project_quality(evidence, policy=policy)
    assert projection.outcome == "produced", projection
    assert core.verify_quality(projection.projection, evidence, policy=policy).outcome == "valid"
    args = dict(evidence=evidence, quality_projection=projection.projection,
                quality_policy=policy, target_area=polygon,
                target_reference=ParentReference(polygon["id"], polygon["revision_id"]))
    spatial = core.prove_spatial_relation(**args)
    assert spatial.outcome == "produced", spatial
    assert core.verify_spatial_relation(spatial.proof, **args).outcome == "valid"
    assembled = core.assemble_spatial_entities(proof=spatial.proof, **args)
    assert assembled.outcome in ("produced", "non_assessable"), assembled
    assert core.verify_spatial_entities(assembled.bundle, proof=spatial.proof, **args).outcome == "valid"
    export = core.export_geojson(bundle=assembled.bundle, proof=spatial.proof, **args)
    assert export.outcome == "produced", export
    metric = core.export_temporal_geojson(bundle=assembled.bundle, proof=spatial.proof, **args)
    assert metric.outcome == "produced", metric
    assert core.render_geojson_map(metric.geojson_json).startswith("<!doctype html>")
    return spatial, assembled, json.loads(export.geojson_json), json.loads(metric.geojson_json)


def layers(fc, name):
    return [f for f in fc["features"] if f["properties"]["layer"] == name]


def main():
    fixtures, checkout = (Path(arg).resolve() for arg in sys.argv[1:])
    installed = Path(core.__file__).resolve()
    assert not installed.is_relative_to(checkout), installed
    assert not Path.cwd().resolve().is_relative_to(checkout)
    manifest = json.loads((fixtures / "manifest.json").read_text())
    expected_hashes = {item["path"]: item["sha256"] for item in manifest["fixtures"]}
    outputs = []
    for name in ("equivalent/basic.gpx", "equivalent/basic.fit"):
        path = fixtures / name
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected_hashes[name]
        evidence = core.ingest_file(
            path, source_kind=path.suffix[1:],
            track_source={"id": "m2-exit-wheel-source", "revision_id": "r1"},
        )
        assert evidence.outcome == "success", evidence
        assert data == path.read_bytes(), "Source bytes changed during ingestion"
        first = pipeline(evidence, target())
        second = pipeline(evidence, target())
        assert first[0].to_json() == second[0].to_json()
        assert first[1].to_json() == second[1].to_json()
        assert first[2] == second[2] and first[3] == second[3]
        spatial, entities, base, timed = first
        assert (spatial.proof.relation, spatial.proof.coverage_completeness) == ("partial", "complete")
        assert len(entities.bundle.segments) == len(layers(base, "target_segment")) == 1
        assert len(layers(timed, "target_metric_edge")) == 2
        assert timed["features"][:len(base["features"])] == base["features"]
        outputs.append((evidence.canonical_track, base, timed))
    fit, gpx = outputs
    assert fit[0]["revision_id"] != gpx[0]["revision_id"], "distinct evidence revisions must not alias"
    a = layers(fit[1], "target_segment")[0]["geometry"]["coordinates"]
    b = layers(gpx[1], "target_segment")[0]["geometry"]["coordinates"]
    assert len(a) == len(b)
    assert all(abs(x - y) <= 1e-6 for pa, pb in zip(a, b) for x, y in zip(pa, pb)), (a, b)

    # A gap through the target must remain unresolved, never a fabricated chord.
    gap_path = fixtures / "gpx/discontinuity.gpx"
    original = gap_path.read_bytes()
    gap = core.ingest_file(gap_path, source_kind="gpx",
                           track_source={"id": "m2-exit-gap", "revision_id": "r1"})
    polygon = target()
    polygon["geometry"]["coordinates"] = [[
        [112.89, 28.19], [112.92, 28.19], [112.92, 28.22],
        [112.89, 28.22], [112.89, 28.19],
    ]]
    spatial, entities, base, metric = pipeline(gap, polygon)
    assert gap_path.read_bytes() == original
    assert (spatial.proof.relation, spatial.proof.coverage_completeness) == ("unknown", "incomplete")
    assert len(entities.bundle.segments) == len(layers(metric, "target_metric_edge")) == 2
    assert {f["properties"]["parent_edge"]["part_index"] for f in layers(metric, "target_metric_edge")} == {0, 1}
    assert all(f["geometry"]["type"] == "Point" for f in layers(base, "gap_endpoint"))

    # A spatially valid track with no timestamps must never acquire a speed.
    missing_path = fixtures / "gpx/no-timestamps.gpx"
    missing = core.ingest_file(
        missing_path, source_kind="gpx",
        track_source={"id": "m2-exit-time", "revision_id": "r1"})
    spatial, entities, base, timed = pipeline(missing, polygon)
    assert spatial.proof.assessable
    assert layers(timed, "target_metric_edge")
    assert all(edge["properties"]["metric"]["speed_mps"] is None
               and edge["properties"]["metric"]["pace_s_per_km"] is None
               and edge["properties"]["metric"]["status"] == "missing_timestamp"
               for edge in layers(timed, "target_metric_edge"))
    assert layers(base, "target_segment"), "spatial validity must survive missing time"

    # Unsupported GPX route-only input cannot masquerade as a track.
    route_only = (b'<?xml version="1.0" encoding="UTF-8"?>'
                  b'<gpx version="1.1" creator="m2exit" xmlns="http://www.topografix.com/GPX/1/1">'
                  b'<rte><rtept lat="28.20" lon="112.90"/>'
                  b'<rtept lat="28.21" lon="112.91"/></rte></gpx>')
    rejected = core.ingest_bytes(
        route_only, source_kind="gpx",
        track_source={"id": "route-not-a-track", "revision_id": "r1"})
    assert rejected.outcome == "failure" and rejected.canonical_track is None
    assert any(d.code == "UNSUPPORTED_GPX_ROUTE_OR_WAYPOINT" for d in rejected.diagnostics)

    # New independent exit witness for the Codex F1 producer/verifier
    # disagreement: equivalent arbitrary partitions are *not* valid
    # QualityProjection values, even when their admitted edges are identical.
    from dataclasses import replace
    from target_area_route_reconstruction.models import TrackPosition
    from target_area_route_reconstruction.quality_models import ParentInterval
    canonical_gpx = core.ingest_file(
        fixtures / "equivalent/basic.gpx", source_kind="gpx",
        track_source={"id": "m2-codex-wheel-f1", "revision_id": "r1"})
    policy = core.QualityPolicy()
    original = core.project_quality(canonical_gpx, policy=policy)
    assert original.outcome == "produced"
    q = original.projection
    assert q.algorithm.version == "0.1.2"
    assert len(q.usable_intervals) == 1
    split = replace(q, usable_intervals=(
        ParentInterval(TrackPosition(0, 0), TrackPosition(0, 1)),
        ParentInterval(TrackPosition(0, 1), TrackPosition(0, 2)),
    ))
    split_check = core.verify_quality(split, canonical_gpx, policy=policy)
    assert split_check.outcome == "invalid", split_check
    assert "USABLE_INTERVAL_NOT_MAXIMAL" in {issue.code for issue in split_check.issues}
    args = dict(evidence=canonical_gpx, quality_projection=split,
                quality_policy=policy, target_area=polygon,
                target_reference=ParentReference(polygon["id"], polygon["revision_id"]))
    rejected = core.prove_spatial_relation(**args)
    assert rejected.outcome != "produced", rejected

    # New isolated-wheel F2 witness must preserve the *exact verified M2B
    # parent-edge decision*, even if a temporal metric happens to be finite.
    # Tiny positive distance is below the numeric guard; cap=1 cannot certify.
    tiny_raw = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<gpx version="1.1" creator="m2-codex" '
        b'xmlns="http://www.topografix.com/GPX/1/1">'
        b'<trk><trkseg>'
        b'<trkpt lat="0" lon="0"><time>2026-10-07T00:00:00Z</time></trkpt>'
        b'<trkpt lat="0" lon="0.000000000001">'
        b'<time>2026-10-07T00:00:00.000000000001Z</time></trkpt>'
        b'</trkseg></trk></gpx>'
    )
    tiny = core.ingest_bytes(tiny_raw, source_kind="gpx",
                            track_source={"id": "m2-codex-wheel-f2", "revision_id": "r1"})
    tiny_target = target()
    tiny_target["geometry"]["coordinates"] = [[
        [-1, -1], [2, -1], [2, 2], [-1, 2], [-1, -1],
    ]]
    tiny_policy = core.QualityPolicy(max_implied_speed_mps=1)
    tiny_q = core.project_quality(tiny, policy=tiny_policy)
    assert tiny_q.outcome == "produced", tiny_q
    assert [d.code for d in tiny_q.projection.diagnostics] == [
        "SPEED_NUMERICALLY_INDETERMINATE"
    ], tiny_q.projection.diagnostics
    tiny_inputs = dict(evidence=tiny, quality_projection=tiny_q.projection,
                       quality_policy=tiny_policy, target_area=tiny_target,
                       target_reference=ParentReference(tiny_target["id"], tiny_target["revision_id"]))
    proof = core.prove_spatial_relation(**tiny_inputs)
    assert proof.outcome == "produced", proof
    assembled = core.assemble_spatial_entities(proof=proof.proof, **tiny_inputs)
    assert assembled.outcome == "produced", assembled
    derived = core.export_temporal_geojson(
        bundle=assembled.bundle, proof=proof.proof, **tiny_inputs)
    assert derived.outcome == "produced", derived
    collection = json.loads(derived.geojson_json)
    edges = layers(collection, "target_metric_edge")
    assert len(edges) == 1, edges
    edge = edges[0]["properties"]
    assert edge["metric"]["status"] == "valid"
    assert edge["speed_screen_result"] == "indeterminate"
    assert edge["speed_screen_reason"] == "SPEED_NUMERICALLY_INDETERMINATE"
    assert edge["metric"]["speed_mps"] > 10000
    assert collection["metadata"]["temporal_overlay"]["algorithm"]["version"] == "0.1.1"

    # Independent second full-repository Codex audit R2-01: real GPX XML
    # -> wheel M2A/B/C, never a forged canonical support snapshot. Exact
    # binary64 rectangle arithmetic establishes that both tiny bounds have
    # strictly positive intersections, but GEOS previously classified the
    # first outside and overshot the second into the target.
    import math
    from fractions import Fraction
    from decimal import Decimal
    def format_decimal(value):
        return format(Decimal(str(value)), "f")
    def numerical_gpx(start, end):
        points = "".join(
            '<trkpt lon="' + format_decimal(x) + '" lat="0"/>'
            for x in (start, end)
        )
        return ('<gpx xmlns="http://www.topografix.com/GPX/1/1" '
                'version="1.1" creator="codex-r2"><trk><trkseg>'
                + points + '</trkseg></trk></gpx>').encode()
    def rectangle_local(a, b):
        polygon = target()
        polygon["geometry"]["coordinates"] = [[
            [a, -1], [b, -1], [b, 1], [a, 1], [a, -1],
        ]]
        return polygon
    for x0, x1, a, b in (
        (-9e-200, 1.8e-199, 8e-200, math.nextafter(8e-200, math.inf)),
        (-1.3e-199, 3e-200, 0.0, 5e-324),
    ):
        dx = Fraction(x1) - Fraction(x0)
        low = max(Fraction(0), (Fraction(a) - Fraction(x0)) / dx)
        high = min(Fraction(1), (Fraction(b) - Fraction(x0)) / dx)
        assert low < high, "Exact-Fraction independent oracle: nonempty intersection"
        raw = numerical_gpx(x0, x1)
        src = core.ingest_bytes(raw, source_kind="gpx",
                  track_source={"id": "codex-r2-wheel", "revision_id": "r1"})
        assert src.outcome == "success", src
        q = core.project_quality(src, policy=core.QualityPolicy())
        assert q.outcome == "produced", q
        area = rectangle_local(a, b)
        args = dict(evidence=src, quality_projection=q.projection,
                    quality_policy=core.QualityPolicy(), target_area=area,
                    target_reference=ParentReference(area["id"], area["revision_id"]))
        rejected = core.prove_spatial_relation(**args)
        assert rejected.outcome == "numerical_failure" and rejected.proof is None, rejected
        assert any(issue.code.startswith("SPATIAL_NUMERICAL_") for issue in rejected.issues)

    # R2-02: all equivalent signed/integer zero parent positions must have
    # one canonical JSON representation before snapshot identity/digest.
    for variant in (0.0, 0, -0.0):
        t = TrackPosition(0, 0, variant)
        assert type(t.fraction_to_next) is float
        assert math.copysign(1.0, t.fraction_to_next) == 1.0
        assert t == TrackPosition(0, 0)
        assert str(t) == str(TrackPosition(0, 0))
    assert q.projection.algorithm.version == "0.1.2"

    print("M2 EXIT ISOLATED WHEEL: R2-01 exact Fraction GPX numerical attacks fail closed; R2-02 canonical identity PASS")

    # No positioned observations is not "outside".
    none = core.ingest_file(
        fixtures / "fit/no-position.fit", source_kind="fit",
        track_source={"id": "no-position", "revision_id": "r1"})
    assert none.outcome == "no_positioned_observations" and none.canonical_track is None
    print("M2 EXIT ISOLATED WHEEL: F1 reject nonmaximal quality partitions and F2 preserve indeterminate numeric screening PASS")
    print("M2 EXIT ISOLATED WHEEL: actual FIT/GPX partial equivalence, exact raw hashes, "
          "determinism, spatial revision separation, unknown gap without chord, "
          "missing-time neutrality, route-only rejection, non-assessability PASS")


if __name__ == "__main__":
    main()
