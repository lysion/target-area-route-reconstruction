"""Independent M2D entity verifier.

Does not import or call the producer. It independently rebuilds ordered
admitted coverage accounting; the narrow parent interpolation primitive is
shared and separately cross-checked by fixture tests.
"""

from __future__ import annotations

from dataclasses import asdict

from ._m2d_common import (
    M2D_NAME, M2D_VERSION, IDENTITY_POLICY, digest, position_dict,
    position_key, regenerate, schema_issues,
)
from .models import TrackPosition
from .spatial_verifier import verify_spatial_relation
from .spatial_entities_models import (
    SpatialEntityBundle, SpatialEntityIssue, SpatialEntityVerification,
)


def _expected_ranges(proof, quality):
    """Independent sweep over verified parent events, per admitted run."""
    result = []
    for admissible in quality.usable_intervals:
        lo, hi = position_key(admissible.start), position_key(admissible.end)
        events = []
        for interval in proof.target_coverage_intervals:
            if lo <= position_key(interval.start) and position_key(interval.end) <= hi:
                events.append((interval.start, interval.end, 1))
        for item in proof.stationary_evidence:
            if not item.target_covered:
                continue
            interval = item.interval
            if lo <= position_key(interval.start) and position_key(interval.end) <= hi:
                events.append((interval.start, interval.end, 0))
        events.sort(key=lambda e: (position_key(e[0]), position_key(e[1])))
        block = []
        for item in events:
            if not block or position_key(block[-1][1]) == position_key(item[0]):
                block.append(item)
            else:
                if any(x[2] for x in block):
                    result.append((block[0][0], block[-1][1]))
                block = [item]
        if block and any(x[2] for x in block):
            result.append((block[0][0], block[-1][1]))
    return tuple(result)


def _expected_uncertainties(proof):
    relevant = []
    parent_proof_digest = digest(proof.to_dict())
    for item in proof.gap_relevance:
        if not item.target_coverage_unresolved:
            continue
        gap = item.gap
        relevant.append({
            "affected_track_range": {
                "start": None if gap.start is None else position_dict(gap.start),
                "end": None if gap.end is None else position_dict(gap.end),
            },
            "relevance": item.reason,
            "provenance": {
                "name": M2D_NAME, "version": M2D_VERSION,
                "parameters": {
                    "proof_digest": parent_proof_digest,
                    "gap_index": item.gap_index,
                    "gap_kind": gap.kind,
                    "gap_causes": list(gap.causes),
                    "gap_diagnostic_indices": list(gap.diagnostic_indices),
                    "gap_excluded_interval_index": gap.excluded_interval_index,
                    "constraint_index": item.constraint_index,
                    "bound_relation": item.bound_relation,
                    "evidence_digest": proof.authority.evidence_digest,
                    "quality_projection_digest": proof.authority.quality_projection_digest,
                },
            },
        })
    return relevant


def verify_spatial_entities(bundle, *, proof, evidence, quality_projection,
                            quality_policy, target_area, target_reference):
    upstream = verify_spatial_relation(
        proof, evidence=evidence, quality_projection=quality_projection,
        quality_policy=quality_policy, target_area=target_area,
        target_reference=target_reference,
    )
    if upstream.outcome != "valid":
        return SpatialEntityVerification("invalid", (
            SpatialEntityIssue("M2D_SPATIAL_PROOF_INVALID"),))
    if not proof.assessable:
        return SpatialEntityVerification("valid" if bundle is None else "invalid",
            () if bundle is None else (SpatialEntityIssue("M2D_NONASSESSABLE_ENTITIES"),))
    if not isinstance(bundle, SpatialEntityBundle):
        return SpatialEntityVerification("invalid", (SpatialEntityIssue("M2D_BUNDLE_MALFORMED"),))
    try:
        assessment, segments = bundle.assessment, bundle.segments
    except (ValueError, TypeError, OverflowError, KeyError):
        return SpatialEntityVerification("invalid", (SpatialEntityIssue("M2D_BUNDLE_MALFORMED"),))
    issues = []
    def fail(code, path=""):
        issues.append(SpatialEntityIssue(code, path))
    if not isinstance(assessment, dict) or not isinstance(segments, tuple):
        return SpatialEntityVerification("invalid", (SpatialEntityIssue("M2D_BUNDLE_MALFORMED"),))
    for path, name, instance in (
        ("assessment", "spatial-assessment", assessment),
        *((f"segments/{n}", "target-segment", s) for n, s in enumerate(segments)),
    ):
        if not isinstance(instance, dict) or schema_issues(name, instance):
            fail("M2D_ENTITY_SCHEMA_INVALID", path)
    if issues:
        return SpatialEntityVerification("invalid", tuple(issues))

    parent = asdict(proof.authority.canonical_track)
    target = asdict(proof.authority.target_area)
    if assessment["canonical_track"] != parent or assessment["target_area"] != target:
        fail("M2D_PARENT_REFERENCE_MISMATCH")
    if (assessment["relation"] != proof.relation
            or assessment["coverage_completeness"] != proof.coverage_completeness):
        fail("M2D_RELATION_OR_COMPLETENESS_CHANGED")
    if assessment["coverage_uncertainties"] != _expected_uncertainties(proof):
        fail("M2D_UNCERTAINTY_MISMATCH")

    actual_algorithm = assessment["algorithm"]
    expected_algorithm = {
        "name": M2D_NAME, "version": M2D_VERSION,
        "parameters": {
            "identity_policy": IDENTITY_POLICY,
            "m2c_proof_digest": digest(proof.to_dict()),
            "m2c_algorithm": asdict(proof.algorithm),
            "quality_projection_digest": proof.authority.quality_projection_digest,
        },
    }
    if actual_algorithm != expected_algorithm:
        fail("M2D_ALGORITHM_MISMATCH")

    expected_ranges = _expected_ranges(proof, quality_projection)
    if len(expected_ranges) != len(segments):
        fail("M2D_TARGET_COVERAGE_NOT_EXHAUSTIVE")
    expected_data = []
    for n, (start, end) in enumerate(expected_ranges):
        expected_data.append({
            "ordinal": n,
            "start_position": position_dict(start),
            "end_position": position_dict(end),
            "geometry": regenerate(evidence.canonical_track, start, end),
        })
    for n, item in enumerate(segments):
        path = f"segments/{n}"
        if n >= len(expected_data):
            break
        info = expected_data[n]
        if (item["ordinal"] != n or item["start_position"] != info["start_position"]
                or item["end_position"] != info["end_position"]):
            fail("M2D_MAXIMALITY_OR_LINEAGE_MISMATCH", path)
        if item["geometry"] != info["geometry"]:
            fail("M2D_GEOMETRY_REGEN_MISMATCH", path)
        if item["canonical_track"] != parent or item["spatial_reference"] != "OGC:CRS84":
            fail("M2D_SEGMENT_PARENT_MISMATCH", path)

    # Independently derive both sides of the reciprocal revision references
    # from the verified proof and expected semantic payloads (pre-reference).
    seed = {
        "identity_policy": IDENTITY_POLICY,
        "algorithm": {"name": M2D_NAME, "version": M2D_VERSION},
        "proof": proof.to_dict(),
        "segments": expected_data,
        "uncertainties": _expected_uncertainties(proof),
    }
    root = digest(seed)
    id_expected = "assessment-" + digest({
        "track_id": proof.authority.canonical_track.id,
        "target_id": proof.authority.target_area.id,
    })[:40]
    assessment_ref = {"id": id_expected, "revision_id": "m2d-" + root[:48]}
    if {"id": assessment["id"], "revision_id": assessment["revision_id"]} != assessment_ref:
        fail("M2D_ASSESSMENT_IDENTITY_MISMATCH")
    expected_refs = []
    for n, info in enumerate(expected_data):
        token = digest({"seed": root, "ordinal": n, "segment": info})
        expected_refs.append({
            "id": "target-segment-" + token[:40],
            "revision_id": "m2d-" + token[:48],
        })
    if assessment["target_segment_refs"] != expected_refs:
        fail("M2D_SEGMENT_REFERENCES_MISMATCH")
    for n, item in enumerate(segments):
        if n >= len(expected_refs):
            break
        ref = expected_refs[n]
        if (item["id"] != ref["id"] or item["revision_id"] != ref["revision_id"]
                or item["spatial_assessment"] != assessment_ref):
            fail("M2D_RECIPROCAL_REFERENCES_MISMATCH", f"segments/{n}")
    return SpatialEntityVerification("invalid" if issues else "valid", tuple(issues))
