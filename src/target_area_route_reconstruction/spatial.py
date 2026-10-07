"""M2C proof producer. Entity extraction/assembly remains downstream."""

from shapely.errors import GEOSException

from ._spatial_geometry import bound_relation, clip_edge, point_covered
from ._spatial_inputs import algorithm, prepare
from .models import TrackPosition
from .quality_models import ParentInterval
from .spatial_models import GapRelevance, SpatialFailure, SpatialIssue, SpatialRelationProof, SpatialResult, StationaryEvidence


def prove_spatial_relation(*, evidence, quality_projection, quality_policy, target_area, target_reference):
    """Produce immutable proof or stable failure; never bypass quality authority."""
    try:
        track, area, authority, verified = prepare(evidence=evidence, quality_projection=quality_projection,
                                                  quality_policy=quality_policy, target_area=target_area,
                                                  target_reference=target_reference)
        target_intervals, outside_intervals, stationary = [], [], []
        for admitted in quality_projection.usable_intervals:
            p = admitted.start.part_index
            observations = track["parts"][p]["observations"]
            for i in range(admitted.start.observation_index, admitted.end.observation_index):
                left, right = observations[i]["position"], observations[i + 1]["position"]
                if left == right:
                    stationary.append(StationaryEvidence(ParentInterval(TrackPosition(p, i), TrackPosition(p, i + 1)),
                                                         point_covered(left, area)))
                    continue
                covered, outside = clip_edge(p, i, left, right, area)
                target_intervals.extend(covered)
                outside_intervals.extend(outside)
        constraints = {claim.gap_index: (i, claim) for i, claim in enumerate(quality_projection.gap_constraints)}
        gaps = []
        for i, gap in enumerate(quality_projection.gaps):
            constraint_index = None
            classification = "unavailable"
            if i in constraints:
                constraint_index, claim = constraints[i]
                if verified.gap_constraint_statuses[i] != "verified":
                    raise SpatialFailure("GAP_CONSTRAINT_NOT_VERIFIED")
                classification = bound_relation(claim.bound, area)
            relevant = classification != "disjoint"
            reason = ("SOURCE_GAP_TARGET_UNRESOLVED" if gap.kind == "source_gap" else "QUALITY_GAP_TARGET_UNRESOLVED") if relevant else "GAP_BOUND_DISJOINT"
            gaps.append(GapRelevance(i, gap, constraint_index, classification, relevant,
                                     classification != "covered", reason))
        assessable = bool(target_intervals or outside_intervals)
        reason = None
        relation = completeness = None
        if not assessable:
            reason = "NO_POSITIVE_LENGTH_USABLE_GEOMETRY"
        else:
            relevant = any(g.target_coverage_unresolved for g in gaps)
            possible_outside = any(g.possible_outside for g in gaps)
            if target_intervals and outside_intervals:
                relation = "partial"
            elif target_intervals and not possible_outside:
                relation = "inside"
            elif outside_intervals and not relevant:
                relation = "outside"
            else:
                relation = "unknown"
            completeness = "incomplete" if relevant else "complete"
        proof = SpatialRelationProof(authority, algorithm(), assessable, relation, completeness, reason,
                                     tuple(target_intervals), tuple(outside_intervals), tuple(stationary), tuple(gaps))
        return SpatialResult("produced", proof)
    except SpatialFailure as exc:
        outcome = "numerical_failure" if any(i.code.startswith("SPATIAL_") and "INPUT" not in i.code for i in exc.issues) else "invalid_input"
        return SpatialResult(outcome, None, exc.issues)
    except GEOSException:
        return SpatialResult("numerical_failure", None, (SpatialIssue("SPATIAL_ENGINE_FAILURE"),))
