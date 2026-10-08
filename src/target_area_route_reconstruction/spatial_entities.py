"""M2D producer: verified M2C intervals to frozen spatial entities.

No M2C clipping, relation inference, gap geometry, or in-place revision edits.
"""

from __future__ import annotations

from dataclasses import asdict

from ._m2d_common import (
    IDENTITY_POLICY, M2D_NAME, M2D_VERSION, SNAPSHOT_POLICY, canonical_json, digest,
    position_dict, position_key, regenerate, schema_issues, exact_proof_metadata,
)
from .spatial_verifier import verify_spatial_relation
from .spatial_entities_models import (
    SpatialAssemblyResult, SpatialEntityBundle, SpatialEntityIssue,
)


def _maximal_covered(track, projection, proof):
    """Coalesce parent-adjacent coverage inside each quality-admitted run.

    Stationary covered edges preserve repeated observations as lineage
    bridges; zero-only ranges never create TargetSegments. Run boundaries
    make bridging any quality exclusion or source part impossible.
    """
    output = []
    for usable in projection.usable_intervals:
        lower, upper = position_key(usable.start), position_key(usable.end)
        candidates = []
        for interval in proof.target_coverage_intervals:
            if lower <= position_key(interval.start) and position_key(interval.end) <= upper:
                candidates.append((interval.start, interval.end, True))
        for witness in proof.stationary_evidence:
            interval = witness.interval
            if (witness.target_covered and lower <= position_key(interval.start)
                    and position_key(interval.end) <= upper):
                candidates.append((interval.start, interval.end, False))
        candidates.sort(key=lambda entry: (position_key(entry[0]), position_key(entry[1])))
        current_start = current_end = None
        has_positive = False

        def flush():
            if current_start is not None and has_positive:
                output.append((current_start, current_end))

        for start, end, positive in candidates:
            if current_start is None:
                current_start, current_end, has_positive = start, end, positive
            elif position_key(current_end) == position_key(start):
                current_end, has_positive = end, (has_positive or positive)
            else:
                flush()
                current_start, current_end, has_positive = start, end, positive
        flush()
    return tuple(output)


def _uncertainties(proof):
    result = []
    proof_digest = digest(proof.to_dict())
    for item in proof.gap_relevance:
        if not item.target_coverage_unresolved:
            continue
        gap = item.gap
        result.append({
            "affected_track_range": {
                "start": position_dict(gap.start) if gap.start is not None else None,
                "end": position_dict(gap.end) if gap.end is not None else None,
            },
            "relevance": item.reason,
            "provenance": {
                "name": M2D_NAME,
                "version": M2D_VERSION,
                "parameters": {
                    "proof_digest": proof_digest,
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
    return result


def _assemble(track, projection, proof):
    ranges = _maximal_covered(track, projection, proof)
    segments_data = [{
        "ordinal": index,
        "start_position": position_dict(start),
        "end_position": position_dict(end),
        "geometry": regenerate(track, start, end),
    } for index, (start, end) in enumerate(ranges)]
    uncertainties = _uncertainties(proof)
    # All semantic data is fixed before assigning reciprocal references.
    # Never compute a hash of final mutually-referencing entity JSON.
    seed = {
        "identity_policy": IDENTITY_POLICY,
        "algorithm": {"name": M2D_NAME, "version": M2D_VERSION},
        "proof": proof.to_dict(),
        "segments": segments_data,
        "uncertainties": uncertainties,
    }
    root = digest(seed)
    parent = proof.authority.canonical_track
    target = proof.authority.target_area
    assessment_id = "assessment-" + digest({"track_id": parent.id, "target_id": target.id})[:40]
    assessment_rev = "m2d-" + root[:48]
    assessment_ref = {"id": assessment_id, "revision_id": assessment_rev}
    parent_ref = asdict(parent)
    segments, refs = [], []
    for info in segments_data:
        ordinal = info["ordinal"]
        token = digest({"seed": root, "ordinal": ordinal, "segment": info})
        identity = {"id": "target-segment-" + token[:40], "revision_id": "m2d-" + token[:48]}
        refs.append(identity)
        segments.append({
            "schema_version": "0.1.0",
            **identity,
            "spatial_assessment": assessment_ref,
            "canonical_track": parent_ref,
            "ordinal": ordinal,
            "spatial_reference": "OGC:CRS84",
            "start_position": info["start_position"],
            "end_position": info["end_position"],
            "geometry": info["geometry"],
        })
    assessment = {
        "schema_version": "0.1.0",
        **assessment_ref,
        "canonical_track": parent_ref,
        "target_area": asdict(target),
        "relation": proof.relation,
        "coverage_completeness": proof.coverage_completeness,
        "coverage_uncertainties": uncertainties,
        "target_segment_refs": refs,
        "algorithm": {
            "name": M2D_NAME,
            "version": M2D_VERSION,
            "parameters": {
                "identity_policy": IDENTITY_POLICY,
                "snapshot_policy": SNAPSHOT_POLICY,
                "m2c_proof_digest": digest(proof.to_dict()),
                "m2c_algorithm": asdict(proof.algorithm),
                "quality_projection_digest": proof.authority.quality_projection_digest,
            },
        },
    }
    return assessment, segments


def assemble_spatial_entities(*, proof, evidence, quality_projection,
                              quality_policy, target_area, target_reference):
    """Consume only a valid exact M2C proof; fail closed on every mismatch."""
    try:
        verification = verify_spatial_relation(
            proof, evidence=evidence, quality_projection=quality_projection,
            quality_policy=quality_policy, target_area=target_area,
            target_reference=target_reference,
        )
    except Exception:
        return SpatialAssemblyResult("invalid_input", issues=(
            SpatialEntityIssue("M2D_AUTHORITY_CHECK_FAILED"),))
    if verification.outcome != "valid":
        return SpatialAssemblyResult("invalid_input", issues=(
            SpatialEntityIssue("M2D_SPATIAL_PROOF_INVALID"),
            *(SpatialEntityIssue(i.code, i.path) for i in verification.issues),
        ))
    try:
        if not exact_proof_metadata(proof, quality_projection):
            return SpatialAssemblyResult("invalid_input", issues=(
                SpatialEntityIssue("M2D_PROOF_METADATA_MISMATCH"),))
    except Exception:
        return SpatialAssemblyResult("invalid_input", issues=(
            SpatialEntityIssue("M2D_AUTHORITY_CHECK_FAILED"),))
    if not proof.assessable:
        return SpatialAssemblyResult("non_assessable", issues=(
            SpatialEntityIssue("NO_POSITIVE_LENGTH_USABLE_GEOMETRY"),))
    try:
        assessment, segments = _assemble(evidence.canonical_track, quality_projection, proof)
        for name, instance in [("spatial-assessment", assessment),
                               *(("target-segment", item) for item in segments)]:
            if schema_issues(name, instance):
                return SpatialAssemblyResult("assembly_failure", issues=(
                    SpatialEntityIssue("M2D_ENTITY_SCHEMA_INVALID", name),))
        bundle = SpatialEntityBundle(canonical_json(assessment),
                                     tuple(canonical_json(item) for item in segments))
        # The verifier does not import or call this producer.
        from .spatial_entities_verifier import verify_spatial_entities
        check = verify_spatial_entities(
            bundle, proof=proof, evidence=evidence,
            quality_projection=quality_projection, quality_policy=quality_policy,
            target_area=target_area, target_reference=target_reference,
        )
        if check.outcome != "valid":
            return SpatialAssemblyResult("assembly_failure", issues=(
                SpatialEntityIssue("M2D_ASSEMBLY_VERIFICATION_FAILED"),
                *check.issues,
            ))
        return SpatialAssemblyResult("produced", bundle)
    except (ValueError, TypeError, OverflowError, IndexError, KeyError, RecursionError):
        return SpatialAssemblyResult("assembly_failure", issues=(
            SpatialEntityIssue("M2D_ASSEMBLY_NUMERICAL_OR_STRUCTURAL_FAILURE"),))
    except Exception:
        return SpatialAssemblyResult("assembly_failure", issues=(
            SpatialEntityIssue("M2D_ASSEMBLY_FAILURE"),))
