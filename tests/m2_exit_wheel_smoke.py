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
    assert q.algorithm.version == "0.1.3"
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

    # R3 P1: an ordinary-length edge crosses a positive-width target strip
    # that GEOS previously dropped *without* any numerical warning. Real
    # GPX -> installed wheel must never admit an incorrect complete relation.
    def r3_polygon(rings, multi=False):
        result = target()
        result["geometry"] = {
            "type": "MultiPolygon" if multi else "Polygon",
            "coordinates": rings,
        }
        return result

    def r3_ring(x0, y0, x1, y1):
        return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]

    for scale in (1e-154, 1e-160):
        next_scale = math.nextafter(scale, math.inf)
        assert Fraction(next_scale) > Fraction(scale)
        examples = (
            r3_polygon([r3_ring(scale, -scale, next_scale, scale)]),
            r3_polygon([r3_ring(-2, -2, 2, 2),
                        r3_ring(scale, -scale, next_scale, scale)]),
            r3_polygon([[r3_ring(scale, -scale, next_scale, scale)],
                        [r3_ring(-1.9, 0.5, -1.8, 0.6)]], multi=True),
        )
        for r3_area in examples:
            r3_evidence = core.ingest_bytes(
                numerical_gpx(-1.0, 1.0), source_kind="gpx",
                track_source={"id":"r3-wheel-numerics", "revision_id":"r1"})
            assert r3_evidence.outcome == "success", r3_evidence
            r3_policy = core.QualityPolicy()
            r3_q = core.project_quality(r3_evidence, policy=r3_policy)
            assert r3_q.outcome == "produced", r3_q
            assert r3_q.projection.algorithm.version == "0.1.3"
            r3_args = dict(
                evidence=r3_evidence, quality_projection=r3_q.projection,
                quality_policy=r3_policy, target_area=r3_area,
                target_reference=ParentReference(r3_area["id"], r3_area["revision_id"]))
            r3 = core.prove_spatial_relation(**r3_args)
            # Safe, explicitly uncertain output is required for these
            # geometrically positive, binary64-unrepresentable tiny slices.
            assert r3.outcome == "numerical_failure" and r3.proof is None, r3

    assert core.prove_spatial_relation(**{
        **args, "quality_projection": core.project_quality(
            canonical_gpx, policy=policy).projection}).outcome != "numerical_failure"
    print("M2 EXIT ISOLATED WHEEL: R3 six thin-strip/hole/multipolygon cases fail closed")

    # R2-02: all equivalent signed/integer zero parent positions must have
    # one canonical JSON representation before snapshot identity/digest.
    for variant in (0.0, 0, -0.0):
        t = TrackPosition(0, 0, variant)
        assert type(t.fraction_to_next) is float
        assert math.copysign(1.0, t.fraction_to_next) == 1.0
        assert t == TrackPosition(0, 0)
        assert str(t) == str(TrackPosition(0, 0))
    assert q.projection.algorithm.version == "0.1.3"

    # PR #21 Codex P2: dataclass-equal diagnostic endpoints must not admit
    # alternative JSON representations of the same quality evidence. Run
    # this independently from an installed, noneditable wheel.
    from target_area_route_reconstruction.quality_models import EdgeDiagnostic
    diag_policy = core.QualityPolicy()
    diag_q = core.project_quality(canonical_gpx, policy=diag_policy).projection
    assert diag_q.diagnostics and isinstance(diag_q.diagnostics[0], EdgeDiagnostic)
    assert core.verify_quality(diag_q, canonical_gpx, policy=diag_policy).outcome == "valid"
    for endname in ("start", "end"):
        for noncanonical in (0, -0.0):
            base_pos = getattr(diag_q.diagnostics[0].interval, endname)
            forged_pos = object.__new__(TrackPosition)
            object.__setattr__(forged_pos, "part_index", base_pos.part_index)
            object.__setattr__(forged_pos, "observation_index", base_pos.observation_index)
            object.__setattr__(forged_pos, "fraction_to_next", noncanonical)
            hacked_interval = replace(diag_q.diagnostics[0].interval, **{endname: forged_pos})
            hacked = replace(diag_q, diagnostics=(
                replace(diag_q.diagnostics[0], interval=hacked_interval),
                *diag_q.diagnostics[1:]))
            assert hacked.diagnostics == diag_q.diagnostics
            assert hacked.to_json() != diag_q.to_json()
            check = core.verify_quality(hacked, canonical_gpx, policy=diag_policy)
            assert check.outcome == "invalid" and any(
                issue.code == "TRACK_POSITION_INVALID" for issue in check.issues), check
            rejected = core.prove_spatial_relation(
                evidence=canonical_gpx, quality_projection=hacked, quality_policy=diag_policy,
                target_area=polygon,
                target_reference=ParentReference(polygon["id"], polygon["revision_id"]))
            assert rejected.outcome != "produced" and rejected.proof is None, rejected

    # A separate Codex P2 found the same representation bypass earlier
    # than quality projection: M2A source mappings and ingestion gap diagnostic
    # endpoints participate in the evidence SHA-256. Verify both negative
    # paths from real GPX using only the installed package.
    def forged_vertex(original, variant):
        bad = object.__new__(TrackPosition)
        object.__setattr__(bad, "part_index", original.part_index)
        object.__setattr__(bad, "observation_index", original.observation_index)
        object.__setattr__(bad, "fraction_to_next", variant)
        assert bad == original
        return bad

    gap_evidence = core.ingest_file(
        fixtures / "gpx/discontinuity.gpx", source_kind="gpx",
        track_source={"id": "r2-wheel-gap", "revision_id": "r1"})
    assert gap_evidence.outcome == "success", gap_evidence
    for source_evidence, source_kind in ((canonical_gpx, "mapping"),
                                         (gap_evidence, "diagnostic")):
        base_projection = core.project_quality(source_evidence, policy=diag_policy)
        assert base_projection.outcome == "produced", base_projection
        for variant in (0, -0.0):
            if source_kind == "mapping":
                mapping = source_evidence.observation_sources[0]
                bad = forged_vertex(mapping.position, variant)
                swapped = replace(source_evidence, observation_sources=(
                    replace(mapping, position=bad), *source_evidence.observation_sources[1:]))
                expected_code = "SOURCE_MAPPING_INVALID"
            else:
                position_index = next(i for i, d in enumerate(source_evidence.diagnostics)
                                      if d.previous_position is not None)
                d = source_evidence.diagnostics[position_index]
                bad = forged_vertex(d.previous_position, variant)
                changed_diags = list(source_evidence.diagnostics)
                changed_diags[position_index] = replace(d, previous_position=bad)
                swapped = replace(source_evidence, diagnostics=tuple(changed_diags))
                expected_code = "SOURCE_DIAGNOSTIC_POSITION_INVALID"
            assert swapped.to_json() != source_evidence.to_json()
            rejected = core.project_quality(swapped, policy=diag_policy)
            assert rejected.outcome == "quality_evidence_unavailable", rejected
            assert expected_code in {issue.code for issue in rejected.issues}, rejected
            validation = core.verify_quality(
                base_projection.projection, swapped, policy=diag_policy)
            assert validation.outcome == "quality_evidence_unavailable", validation

    # PR review's third representation bypass: the M2C proof has a nested
    # GapRelevance.gap snapshot distinct from its validated M2B parent. Forge
    # either endpoint and require an installed-wheel M2C + M2D refusal.
    gap_quality = core.project_quality(gap_evidence, policy=diag_policy).projection
    gap_args = dict(evidence=gap_evidence, quality_projection=gap_quality,
                    quality_policy=diag_policy, target_area=polygon,
                    target_reference=ParentReference(polygon["id"], polygon["revision_id"]))
    spatial_gap = core.prove_spatial_relation(**gap_args)
    assert spatial_gap.outcome == "produced" and spatial_gap.proof.gap_relevance, spatial_gap
    for field in ("start", "end"):
        for noncanonical in (0, -0.0):
            parent_gap = spatial_gap.proof.gap_relevance[0].gap
            original = getattr(parent_gap, field)
            assert original is not None
            forged_gap = replace(parent_gap, **{field: forged_vertex(original, noncanonical)})
            assert forged_gap == parent_gap
            forged_rel = replace(spatial_gap.proof.gap_relevance[0], gap=forged_gap)
            bad_proof = replace(spatial_gap.proof, gap_relevance=(
                forged_rel, *spatial_gap.proof.gap_relevance[1:]))
            assert bad_proof.to_json() != spatial_gap.proof.to_json()
            checked = core.verify_spatial_relation(bad_proof, **gap_args)
            assert checked.outcome == "invalid" and any(
                issue.code == "SPATIAL_POSITION_INVALID" for issue in checked.issues), checked
            downstream = core.assemble_spatial_entities(proof=bad_proof, **gap_args)
            assert downstream.outcome != "produced", downstream

    # R3 exact-head P2: a nested source gap must not accept bool/float
    # aliases of diagnostic indices. These variants compare equal to canonical
    # ints in dataclass equality but create distinct installed-wheel JSON.
    saw_diagnostic_index = False
    for gap_index, original_rel in enumerate(spatial_gap.proof.gap_relevance):
        gap = original_rel.gap
        if not gap.diagnostic_indices:
            continue
        saw_diagnostic_index = True
        index = gap.diagnostic_indices[0]
        candidates = [float(index)] + ([False] if index == 0 else [])
        for candidate in candidates:
            modified_gap = replace(gap, diagnostic_indices=(
                candidate, *gap.diagnostic_indices[1:]))
            assert modified_gap == gap
            wrong_quality = replace(gap_quality, gaps=tuple(
                modified_gap if i == gap_index else item
                for i, item in enumerate(gap_quality.gaps)))
            assert wrong_quality.to_json() != gap_quality.to_json()
            assert core.verify_quality(
                wrong_quality, gap_evidence, policy=diag_policy).outcome == "invalid"
            assert core.prove_spatial_relation(**{
                **gap_args, "quality_projection": wrong_quality}).outcome != "produced"

            modified_rel = replace(original_rel, gap=modified_gap)
            wrong_proof = replace(spatial_gap.proof, gap_relevance=tuple(
                modified_rel if i == gap_index else item
                for i, item in enumerate(spatial_gap.proof.gap_relevance)))
            assert wrong_proof.to_json() != spatial_gap.proof.to_json()
            invalid = core.verify_spatial_relation(wrong_proof, **gap_args)
            assert invalid.outcome == "invalid" and any(
                issue.code == "SPATIAL_PROOF_MALFORMED"
                for issue in invalid.issues), invalid
            denied = core.assemble_spatial_entities(proof=wrong_proof, **gap_args)
            assert denied.outcome != "produced", denied
    assert saw_diagnostic_index, "Gap diagnostic identity witness is required"
    print("M2 EXIT ISOLATED WHEEL: strict nested Gap diagnostic integer identity PASS")

    # Codex P2: even a fully typed positive-zero non-gap M2A diagnostic
    # must name its own positioned record and exact predecessor. Source
    # acceptance cannot rely on in-bounds checks alone.
    from target_area_route_reconstruction.models import Diagnostic
    first_src, second_src = canonical_gpx.observation_sources[:2]
    timestamp_diag = Diagnostic(
        "TIMESTAMP_UNREPRESENTABLE", second_src.source, "timestamp",
        first_src.position, second_src.position)
    with_diag = replace(canonical_gpx, diagnostics=(timestamp_diag,))
    clean_projection = core.project_quality(with_diag, policy=diag_policy)
    assert clean_projection.outcome == "produced", clean_projection
    for field, altered in (
        ("previous_position", TrackPosition(99, 99, 0.0)),
        ("next_position", TrackPosition(99, 99, 0.0)),
        ("next_position", first_src.position),
    ):
        bad_evidence = replace(with_diag, diagnostics=(
            replace(timestamp_diag, **{field: altered}),))
        result = core.project_quality(bad_evidence, policy=diag_policy)
        assert result.outcome == "quality_evidence_unavailable", result
        assert "SOURCE_DIAGNOSTIC_POSITION_INVALID" in {
            issue.code for issue in result.issues}, result
        rejected = core.verify_quality(
            clean_projection.projection, bad_evidence, policy=diag_policy)
        assert rejected.outcome == "quality_evidence_unavailable", rejected

    # Independent audit D-01: a genuine parser-emitted GPX time warning
    # must survive M2A-M2F, but malformed primitive diagnostic fields
    # must be refused by M2B, M2C and M2D on the isolated installed wheel.
    from dataclasses import replace
    raw_warning = (
        '<gpx version="1.1" creator="r3-d01" xmlns="http://www.topografix.com/GPX/1/1">'
        '<trk><trkseg>'
        '<trkpt lon="112.904" lat="28.2"><time>2026-01-01T00:00:00</time></trkpt>'
        '<trkpt lon="112.905" lat="28.2"><time>2026-01-01T00:01:00Z</time></trkpt>'
        '</trkseg></trk></gpx>').encode()
    warning_evidence = core.ingest_bytes(
        raw_warning, source_kind="gpx",
        track_source={"id":"r3-wheel-d01","revision_id":"r1"})
    assert warning_evidence.outcome == "success", warning_evidence
    original_warning = next(d for d in warning_evidence.diagnostics
                            if d.code == "TIMESTAMP_TIMEZONE_MISSING")
    assert original_warning.field == "timestamp"
    valid_policy = core.QualityPolicy()
    valid_quality = core.project_quality(warning_evidence, policy=valid_policy)
    assert valid_quality.outcome == "produced", valid_quality
    assert core.verify_quality(
        valid_quality.projection, warning_evidence,
        policy=valid_policy).outcome == "valid"
    valid_args = dict(
        evidence=warning_evidence, quality_projection=valid_quality.projection,
        quality_policy=valid_policy, target_area=polygon,
        target_reference=ParentReference(polygon["id"], polygon["revision_id"]))
    valid_proof = core.prove_spatial_relation(**valid_args)
    assert valid_proof.outcome == "produced", valid_proof
    assert core.verify_spatial_relation(valid_proof.proof, **valid_args).outcome == "valid"
    valid_entities = core.assemble_spatial_entities(proof=valid_proof.proof, **valid_args)
    assert valid_entities.outcome == "produced", valid_entities
    valid_temporal = core.export_temporal_geojson(
        bundle=valid_entities.bundle, proof=valid_proof.proof, **valid_args)
    assert valid_temporal.outcome == "produced", valid_temporal
    for name, invalid in (
        ("field", False), ("field", 0), ("field", 0.0),
        ("field", -0.0), ("code", False), ("code", 0),
        ("code", 0.0), ("code", -0.0),
    ):
        changed_evidence = replace(warning_evidence, diagnostics=tuple(
            replace(d, **{name:invalid}) if d is original_warning else d
            for d in warning_evidence.diagnostics))
        assert changed_evidence.to_json() != warning_evidence.to_json()
        projected = core.project_quality(changed_evidence, policy=valid_policy)
        assert projected.outcome == "quality_evidence_unavailable", projected
        assert "SOURCE_DIAGNOSTIC_TYPE_INVALID" in {
            issue.code for issue in projected.issues}, projected
        verified = core.verify_quality(
            valid_quality.projection, changed_evidence, policy=valid_policy)
        assert verified.outcome == "quality_evidence_unavailable", verified
        invalid_args = {**valid_args, "evidence": changed_evidence}
        assert core.prove_spatial_relation(**invalid_args).outcome != "produced"
        assert core.assemble_spatial_entities(
            proof=valid_proof.proof, **invalid_args).outcome != "produced"
        assert core.export_temporal_geojson(
            bundle=valid_entities.bundle, proof=valid_proof.proof,
            **invalid_args).outcome != "produced"
    print("M2 EXIT ISOLATED WHEEL: R3 D-01 Diagnostic primitive types rejected")

    # The closed M2A gate also covers containers and JSON payloads. A valid
    # projection/proof must not authorize a differently typed source snapshot,
    # even if list/tuple happen to encode the same JSON. No hash is reached.
    from unittest.mock import patch
    from target_area_route_reconstruction._quality_evidence import evidence_digest
    malformed_sources = (
        replace(warning_evidence, diagnostics=list(warning_evidence.diagnostics)),
        replace(warning_evidence, observation_sources=list(warning_evidence.observation_sources)),
        replace(warning_evidence, outcome=False),
        replace(warning_evidence, content_hash={**warning_evidence.content_hash, "digest": False}),
        replace(warning_evidence, canonical_track={
            **warning_evidence.canonical_track,
            "parts": tuple(warning_evidence.canonical_track["parts"])}),
        replace(warning_evidence, canonical_track={
            **warning_evidence.canonical_track, "extra": original_warning}),
    )
    for changed in malformed_sources:
        with patch("target_area_route_reconstruction._quality_evidence.digest",
                   side_effect=AssertionError("noncanonical source reached a hash")):
            assert core.project_quality(changed, policy=valid_policy).projection is None
            assert core.verify_quality(valid_quality.projection, changed,
                                       policy=valid_policy).outcome != "valid"
            try:
                evidence_digest(changed)
            except ValueError as error:
                assert str(error) == "QUALITY_EVIDENCE_INVALID"
            else:
                raise AssertionError("malformed M2A source received a digest")
            denied_args = {**valid_args, "evidence": changed}
            assert core.prove_spatial_relation(**denied_args).proof is None
            assert core.assemble_spatial_entities(proof=valid_proof.proof, **denied_args).bundle is None
            assert core.export_temporal_geojson(bundle=valid_entities.bundle,
                                               proof=valid_proof.proof, **denied_args).geojson_json is None
    print("M2 EXIT ISOLATED WHEEL: closed M2A source types rejected before hashing")

    # Type-sensitive source lineage witness: these are *equal* as Python
    # SourceLocation values, but their JSON spellings and fingerprints differ.
    # Check both observation mapping and diagnostic copies against the wheel.
    from target_area_route_reconstruction.models import SourceLocation
    src0 = canonical_gpx.observation_sources[0]
    injected_diag = Diagnostic(
        "TIMESTAMP_UNREPRESENTABLE", src0.source, "timestamp",
        None, src0.position)
    inject = replace(canonical_gpx, diagnostics=(injected_diag,))
    assert core.project_quality(inject, policy=diag_policy).outcome == "produced"
    for name in ("record_index", "track_index", "segment_index", "point_index"):
        # The reference wheel fixture's initial GPX indices are all zero.
        assert getattr(src0.source, name) == 0
        for representation in (False, 0.0):
            bad_source = replace(src0.source, **{name: representation})
            assert isinstance(bad_source, SourceLocation) and bad_source == src0.source
            spoofed = replace(inject, diagnostics=(replace(injected_diag, source=bad_source),))
            assert spoofed.to_json() != inject.to_json()
            result = core.project_quality(spoofed, policy=diag_policy)
            assert result.outcome == "quality_evidence_unavailable", result
            assert "SOURCE_DIAGNOSTIC_SOURCE_INVALID" in {
                issue.code for issue in result.issues}, result

    # Exact SourceLocation class identity must be enforced even if a
    # dataclass subclass retains every canonical source index and only
    # appends an independent JSON field. This is a wheel-only adversary.
    from dataclasses import dataclass
    @dataclass(frozen=True)
    class ExtendedSourceLocation(SourceLocation):
        extra: str = "forged"

    forged_src = src0.source
    inherited = ExtendedSourceLocation(
        forged_src.source_kind, forged_src.record_index,
        forged_src.track_index, forged_src.segment_index, forged_src.point_index)
    fake_evidence = replace(canonical_gpx, observation_sources=(
        replace(src0, source=inherited), *canonical_gpx.observation_sources[1:]))
    assert fake_evidence.to_json() != canonical_gpx.to_json()
    rejected = core.project_quality(fake_evidence, policy=diag_policy)
    assert rejected.outcome == "quality_evidence_unavailable", rejected
    assert "SOURCE_MAPPING_INVALID" in {i.code for i in rejected.issues}, rejected

    # Native FIT Record locations have no track/segment/point indices.
    # GPX part-level discontinuity reports have no record/point index.
    # Canonical types alone do not prevent None→integer hash aliases.
    fit_src = core.ingest_file(
        fixtures / "fit/complete-activity.fit", source_kind="fit",
        track_source={"id": "wheel-fit-shape", "revision_id": "r1"})
    assert fit_src.outcome == "success", fit_src
    fit_mapping = fit_src.observation_sources[0]
    for field in ("track_index", "segment_index", "point_index"):
        assert getattr(fit_mapping.source, field) is None
        fake = replace(fit_src, observation_sources=(
            replace(fit_mapping, source=replace(fit_mapping.source, **{field: 0})),
            *fit_src.observation_sources[1:]))
        check = core.project_quality(fake, policy=diag_policy)
        assert check.outcome == "quality_evidence_unavailable" and any(
            issue.code == "SOURCE_MAPPING_INVALID" for issue in check.issues), check
    part_diag = next(d for d in gap_evidence.diagnostics
                     if d.code == "SOURCE_CONTINUITY_BREAK")
    assert part_diag.source.record_index is None and part_diag.source.point_index is None
    for field in ("record_index", "point_index"):
        changed = list(gap_evidence.diagnostics)
        i = changed.index(part_diag)
        changed[i] = replace(part_diag, source=replace(part_diag.source, **{field: 0}))
        fake = replace(gap_evidence, diagnostics=tuple(changed))
        check = core.project_quality(fake, policy=diag_policy)
        assert check.outcome == "quality_evidence_unavailable" and any(
            issue.code == "SOURCE_DIAGNOSTIC_SOURCE_INVALID" for issue in check.issues), check

    # Codex PR #21 P2: a subclass of TrackPosition retains numerically
    # valid coordinates, but adds a serialized field to the quality/spatial
    # SHA identity. Check both public independent verifiers on the wheel.
    @dataclass(frozen=True)
    class ExtendedTrackPosition(TrackPosition):
        injected_identity: str = "untrusted-wheel-field"

    def inherited_position(value):
        return ExtendedTrackPosition(value.part_index, value.observation_index,
                                     value.fraction_to_next)

    quality_span = diag_q.usable_intervals[0]
    for endname in ("start", "end"):
        changed_span = replace(quality_span,
                               **{endname: inherited_position(getattr(quality_span, endname))})
        forged_quality = replace(diag_q, usable_intervals=(
            changed_span, *diag_q.usable_intervals[1:]))
        assert forged_quality.to_json() != diag_q.to_json()
        check = core.verify_quality(forged_quality, canonical_gpx, policy=diag_policy)
        assert check.outcome == "invalid" and any(
            issue.code == "TRACK_POSITION_INVALID" for issue in check.issues), check
        refused = core.prove_spatial_relation(
            evidence=canonical_gpx, quality_projection=forged_quality,
            quality_policy=diag_policy, target_area=polygon,
            target_reference=ParentReference(polygon["id"], polygon["revision_id"]))
        assert refused.outcome != "produced" and refused.proof is None, refused

    spatial_span = spatial_gap.proof.target_coverage_intervals[0]
    for endname in ("start", "end"):
        changed_span = replace(spatial_span,
                               **{endname: inherited_position(getattr(spatial_span, endname))})
        forged_spatial = replace(spatial_gap.proof, target_coverage_intervals=(
            changed_span, *spatial_gap.proof.target_coverage_intervals[1:]))
        assert forged_spatial.to_json() != spatial_gap.proof.to_json()
        checked = core.verify_spatial_relation(forged_spatial, **gap_args)
        assert checked.outcome == "invalid" and any(
            issue.code == "SPATIAL_POSITION_INVALID" for issue in checked.issues), checked
        denied = core.assemble_spatial_entities(proof=forged_spatial, **gap_args)
        assert denied.outcome != "produced", denied

    # R3 P2: inherited supporting dataclasses can carry new JSON fields
    # even when their base-class fields compare equal. Reject BEFORE digest.
    from dataclasses import fields, make_dataclass
    def r3_extended(value):
        kind = type(value)
        extended = make_dataclass(
            "R3Extended" + kind.__name__, [("untrusted_extension", str, "forged")],
            bases=(kind,), frozen=True)
        return extended(**{f.name: getattr(value, f.name) for f in fields(value)})

    original_span = diag_q.usable_intervals[0]
    bad_quality = replace(diag_q, usable_intervals=(
        r3_extended(original_span), *diag_q.usable_intervals[1:]))
    assert bad_quality.to_json() != diag_q.to_json()
    checked = core.verify_quality(bad_quality, canonical_gpx, policy=diag_policy)
    assert checked.outcome == "invalid", checked
    refused = core.prove_spatial_relation(
        evidence=canonical_gpx, quality_projection=bad_quality,
        quality_policy=diag_policy, target_area=polygon,
        target_reference=ParentReference(polygon["id"], polygon["revision_id"]))
    assert refused.outcome != "produced" and refused.proof is None, refused

    prior = spatial_gap.proof
    inherited_rel = r3_extended(prior.gap_relevance[0])
    bad_spatial = replace(prior, gap_relevance=(
        inherited_rel, *prior.gap_relevance[1:]))
    assert bad_spatial.to_json() != prior.to_json()
    checked = core.verify_spatial_relation(bad_spatial, **gap_args)
    assert checked.outcome == "invalid", checked
    refused = core.assemble_spatial_entities(proof=bad_spatial, **gap_args)
    assert refused.outcome != "produced", refused
    print("M2 EXIT ISOLATED WHEEL: R3 inherited ParentInterval/GapRelevance digest aliases rejected")

    print("M2 EXIT ISOLATED WHEEL: TrackPosition subclass hash-identity attacks fail closed at M2B/M2C/M2D")

    print("M2 EXIT ISOLATED WHEEL: R2-01 Fraction GPX numerical attacks fail closed; R2-02 canonical M2A FIT/GPX source shapes, M2B diagnostics and M2C nested gaps PASS")

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
