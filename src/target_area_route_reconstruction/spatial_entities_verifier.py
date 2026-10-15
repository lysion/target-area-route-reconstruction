"""Independent M2D entity verifier.

Does not import or call the producer. It independently rebuilds ordered
admitted coverage accounting; the narrow parent interpolation primitive is
shared and separately cross-checked by fixture tests.
"""

from __future__ import annotations

from dataclasses import asdict
from operator import itemgetter

from ._m2d_common import (
    M2D_NAME, M2D_VERSION, IDENTITY_POLICY, SNAPSHOT_POLICY, digest, position_dict,
    position_key, regenerate, schema_issues, canonical_json, strict_load,
    BundleJSONError, exact_proof_metadata, geometry_matches_parent,
)
from .models import TrackPosition
from .spatial_verifier import verify_spatial_relation
from .spatial_entities_models import (
    SpatialEntityBundle, SpatialEntityIssue, SpatialEntityVerification,
)


def _expected_ranges(proof, quality):
    """Independent sweep over verified parent events, per admitted run."""
    # Cache positional keys once. This verifier still independently materializes
    # and sorts its complete event set (the producer uses a streaming merge), but
    # avoids recomputing the same two keys during sorting and the cursor sweep.
    result = []
    events = [(position_key(interval.start), position_key(interval.end),
               interval.start, interval.end, 1)
              for interval in proof.target_coverage_intervals]
    events.extend((position_key(item.interval.start), position_key(item.interval.end),
                   item.interval.start, item.interval.end, 0)
                  for item in proof.stationary_evidence if item.target_covered)
    events.sort(key=itemgetter(0, 1))
    cursor = 0
    for admissible in quality.usable_intervals:
        lo, hi = position_key(admissible.start), position_key(admissible.end)
        while cursor < len(events) and events[cursor][1] <= lo:
            cursor += 1
        block_start = block_end = block_end_key = None
        block_has_positive = False
        while cursor < len(events) and events[cursor][0] < hi:
            item = events[cursor]
            cursor += 1
            if item[0] < lo or item[1] > hi:
                raise ValueError("M2D_COVERAGE_CROSSES_QUALITY_RUN")
            if block_start is None:
                block_start, block_end, block_end_key = item[2], item[3], item[1]
                block_has_positive = bool(item[4])
            elif block_end_key == item[0]:
                block_end, block_end_key = item[3], item[1]
                block_has_positive = block_has_positive or bool(item[4])
            else:
                if block_has_positive:
                    result.append((block_start, block_end))
                block_start, block_end, block_end_key = item[2], item[3], item[1]
                block_has_positive = bool(item[4])
        if block_start is not None and block_has_positive:
            result.append((block_start, block_end))
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
    """Check semantic lineage AND the versioned immutable assembly payload.

    This is not a general-purpose validator for arbitrary schema-valid spatial
    entities. No exception becomes successful empty coverage.
    """
    try:
        return _verify_spatial_entities(
            bundle, proof=proof, evidence=evidence, quality_projection=quality_projection,
            quality_policy=quality_policy, target_area=target_area,
            target_reference=target_reference)
    except Exception:
        # Fail closed even on unexpected engine/resource/internal failures.
        # Deliberately do not catch process-control BaseExceptions.
        return SpatialEntityVerification("invalid", (
            SpatialEntityIssue("M2D_VERIFICATION_FAILURE"),))


def _verify_spatial_entities(bundle, *, proof, evidence, quality_projection,
                             quality_policy, target_area, target_reference):
    upstream = verify_spatial_relation(
        proof, evidence=evidence, quality_projection=quality_projection,
        quality_policy=quality_policy, target_area=target_area,
        target_reference=target_reference,
    )
    if upstream.outcome != "valid":
        return SpatialEntityVerification("invalid", (
            SpatialEntityIssue("M2D_SPATIAL_PROOF_INVALID"),))
    if not exact_proof_metadata(proof, quality_projection):
        return SpatialEntityVerification("invalid", (
            SpatialEntityIssue("M2D_PROOF_METADATA_MISMATCH"),))
    if not proof.assessable:
        return SpatialEntityVerification("valid" if bundle is None else "invalid",
            () if bundle is None else (SpatialEntityIssue("M2D_NONASSESSABLE_ENTITIES"),))
    if (type(bundle) is not SpatialEntityBundle
            or type(bundle.assessment_json) is not str
            or type(bundle.segment_json) is not tuple
            or any(type(s) is not str for s in bundle.segment_json)):
        return SpatialEntityVerification("invalid", (SpatialEntityIssue("M2D_BUNDLE_MALFORMED"),))
    decoded = []
    for path, raw in (("assessment", bundle.assessment_json),
                      *((f"segments/{n}", raw) for n, raw in enumerate(bundle.segment_json))):
        try:
            decoded.append(strict_load(raw))
        except BundleJSONError as exc:
            return SpatialEntityVerification("invalid", (SpatialEntityIssue(exc.code, path),))
        except (ValueError, TypeError, OverflowError, RecursionError):
            return SpatialEntityVerification("invalid", (SpatialEntityIssue("M2D_BUNDLE_MALFORMED", path),))
    assessment, segments = decoded[0], tuple(decoded[1:])
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
    if canonical_json(assessment["coverage_uncertainties"]) != canonical_json(_expected_uncertainties(proof)):
        fail("M2D_UNCERTAINTY_MISMATCH")

    actual_algorithm = assessment["algorithm"]
    expected_algorithm = {
        "name": M2D_NAME, "version": M2D_VERSION,
        "parameters": {
            "identity_policy": IDENTITY_POLICY,
            "snapshot_policy": SNAPSHOT_POLICY,
            "m2c_proof_digest": digest(proof.to_dict()),
            "m2c_algorithm": asdict(proof.algorithm),
            "quality_projection_digest": proof.authority.quality_projection_digest,
        },
    }
    if canonical_json(actual_algorithm) != canonical_json(expected_algorithm):
        fail("M2D_ALGORITHM_MISMATCH")

    expected_ranges = _expected_ranges(proof, quality_projection)
    if len(expected_ranges) != len(segments):
        fail("M2D_TARGET_COVERAGE_NOT_EXHAUSTIVE")
    expected_data = []
    from ._m2d_common import parent_coordinate_scale
    coordinate_scale = parent_coordinate_scale(evidence.canonical_track)
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
        if not geometry_matches_parent(item["geometry"], info["geometry"], evidence.canonical_track,
                                       parent_scale=coordinate_scale):
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
    # Schema-legal extensions and numeric substitutions must not reuse a
    # revision whose seed never bound that content. Compare the whole expected
    # payload, after independent authority/coverage/geometry/reference checks.
    expected_assessment = {
        "schema_version": "0.1.0", **assessment_ref,
        "canonical_track": parent, "target_area": target,
        "relation": proof.relation, "coverage_completeness": proof.coverage_completeness,
        "coverage_uncertainties": _expected_uncertainties(proof),
        "target_segment_refs": expected_refs, "algorithm": expected_algorithm,
    }
    if canonical_json(assessment) != canonical_json(expected_assessment):
        fail("M2D_CANONICAL_SNAPSHOT_MISMATCH", "assessment")
    for n, item in enumerate(segments):
        if n >= len(expected_refs):
            break
        ref = expected_refs[n]
        if (item["id"] != ref["id"] or item["revision_id"] != ref["revision_id"]
                or item["spatial_assessment"] != assessment_ref):
            fail("M2D_RECIPROCAL_REFERENCES_MISMATCH", f"segments/{n}")
        expected_segment = {
            "schema_version": "0.1.0", **ref, **expected_data[n],
            "spatial_assessment": assessment_ref, "canonical_track": parent,
            "spatial_reference": "OGC:CRS84",
        }
        if canonical_json(item) != canonical_json(expected_segment):
            fail("M2D_CANONICAL_SNAPSHOT_MISMATCH", f"segments/{n}")
    return SpatialEntityVerification("invalid" if issues else "valid", tuple(issues))
