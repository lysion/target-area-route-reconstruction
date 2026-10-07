"""Validate untrusted M2C supporting claims before downstream consumption."""

import math

from shapely.errors import GEOSException
from shapely.geometry import box

from ._spatial_geometry import clip_edge, point_covered
from ._spatial_inputs import algorithm, prepare
from .models import TrackPosition
from .quality_models import ParentInterval
from .spatial_models import SpatialFailure, SpatialIssue, SpatialRelationProof, SpatialVerification, StationaryEvidence


def verify_spatial_relation(proof, *, evidence, quality_projection, quality_policy, target_area, target_reference):
    try:
        track, area, authority, verified = prepare(evidence=evidence, quality_projection=quality_projection,
                                                  quality_policy=quality_policy, target_area=target_area,
                                                  target_reference=target_reference)
        return _verify(proof, track, area, authority, quality_projection, verified)
    except SpatialFailure as exc:
        return SpatialVerification("invalid", exc.issues)
    except GEOSException:
        return SpatialVerification("invalid", (SpatialIssue("SPATIAL_ENGINE_FAILURE"),))
    except (AttributeError, TypeError, ValueError, IndexError, OverflowError):
        return SpatialVerification("invalid", (SpatialIssue("SPATIAL_PROOF_MALFORMED"),))


def _verify(proof, track, area, authority, quality, verified):
    errors = []
    def fail(code, path=""):
        errors.append(SpatialIssue(code, path))
    def result():
        return SpatialVerification("invalid" if errors else "valid", tuple(errors))
    if not isinstance(proof, SpatialRelationProof):
        fail("SPATIAL_PROOF_MALFORMED")
        return result()
    if proof.authority != authority:
        fail("SPATIAL_AUTHORITY_MISMATCH")
    if proof.algorithm != algorithm():
        fail("SPATIAL_ALGORITHM_MISMATCH")
    if type(proof.assessable) is not bool or any(type(value) is not tuple for value in (
        proof.target_coverage_intervals, proof.outside_evidence_intervals, proof.stationary_evidence, proof.gap_relevance
    )):
        fail("SPATIAL_PROOF_MALFORMED")
    if errors:
        return result()

    # Independently enumerate authority and positive/zero edges. No producer
    # helpers or producer output are used as an expected result.
    admitted = set()
    for span in quality.usable_intervals:
        admitted.update((span.start.part_index, i) for i in range(span.start.observation_index, span.end.observation_index))
    positives = set()
    expected_target, expected_outside, expected_stationary = [], [], []
    for p, i in sorted(admitted):
        observations = track["parts"][p]["observations"]
        left, right = observations[i]["position"], observations[i + 1]["position"]
        if left == right:
            expected_stationary.append(StationaryEvidence(ParentInterval(TrackPosition(p, i), TrackPosition(p, i + 1)), point_covered(left, area)))
        else:
            positives.add((p, i))
            inside, outside = clip_edge(p, i, left, right, area)
            expected_target.extend(inside)
            expected_outside.extend(outside)

    def position(value):
        if not isinstance(value, TrackPosition):
            return False
        p, i, f = value.part_index, value.observation_index, value.fraction_to_next
        return (type(p) is int and 0 <= p < len(track["parts"]) and type(i) is int
                and 0 <= i < len(track["parts"][p]["observations"])
                and type(f) in (int, float) and math.isfinite(f) and 0 <= f < 1
                and (f == 0 or i + 1 < len(track["parts"][p]["observations"])))

    actual_spans = {}
    for label, intervals in (("target", proof.target_coverage_intervals), ("outside", proof.outside_evidence_intervals)):
        previous_end = None
        for n, interval in enumerate(intervals):
            path = f"{label}/{n}"
            a, b = interval.start, interval.end
            if not position(a) or not position(b):
                fail("SPATIAL_POSITION_INVALID", path)
                continue
            ka, kb = (a.part_index, a.observation_index, a.fraction_to_next), (b.part_index, b.observation_index, b.fraction_to_next)
            if ka >= kb or a.part_index != b.part_index:
                fail("SPATIAL_RANGE_INVALID", path)
                continue
            if previous_end is not None and ka < previous_end:
                fail("SPATIAL_RANGE_ORDER_OR_OVERLAP", path)
            previous_end = kb
            if b.observation_index == a.observation_index:
                high = b.fraction_to_next
            elif b.observation_index == a.observation_index + 1 and b.fraction_to_next == 0:
                high = 1.0
            else:
                fail("SPATIAL_FRAGMENT_CROSSES_EDGE", path)
                continue
            edge = (a.part_index, a.observation_index)
            if edge not in positives:
                fail("SPATIAL_EDGE_NOT_ADMITTED_POSITIVE", path)
            actual_spans.setdefault(edge, []).append((a.fraction_to_next, high))
    for edge in sorted(positives):
        cursor = 0.0
        for low, high in sorted(actual_spans.get(edge, ())):
            if low != cursor:
                fail("SPATIAL_EDGE_COVERAGE_MISMATCH")
            cursor = high
        if cursor != 1:
            fail("SPATIAL_EDGE_COVERAGE_MISMATCH")
    if proof.target_coverage_intervals != tuple(expected_target):
        fail("TARGET_COVERAGE_PROOF_MISMATCH")
    if proof.outside_evidence_intervals != tuple(expected_outside):
        fail("OUTSIDE_EVIDENCE_PROOF_MISMATCH")
    if (proof.stationary_evidence != tuple(expected_stationary)
            or any(type(item.target_covered) is not bool
                   or not position(item.interval.start) or not position(item.interval.end)
                   for item in proof.stationary_evidence)):
        fail("STATIONARY_EVIDENCE_MISMATCH")

    # Independent gap-bound predicates, not the producer's bound classifier.
    constraints = {c.gap_index: (i, c) for i, c in enumerate(quality.gap_constraints)}
    relevant, possible_outside = False, False
    if len(proof.gap_relevance) != len(quality.gaps):
        fail("GAP_RELEVANCE_MISSING_OR_EXTRA")
    for i, gap in enumerate(quality.gaps):
        index, claim = constraints.get(i, (None, None))
        if claim is None:
            classification, unresolved, exterior = "unavailable", True, True
        else:
            if verified.gap_constraint_statuses[i] != "verified":
                fail("GAP_CONSTRAINT_NOT_VERIFIED")
                continue
            bound = box(*claim.bound.bbox)
            unresolved = not area.disjoint(bound)
            exterior = not area.covers(bound)
            classification = "disjoint" if not unresolved else "covered" if not exterior else "intersects"
        relevant |= unresolved
        possible_outside |= exterior
        reason = ("SOURCE_GAP_TARGET_UNRESOLVED" if gap.kind == "source_gap" else "QUALITY_GAP_TARGET_UNRESOLVED") if unresolved else "GAP_BOUND_DISJOINT"
        if i < len(proof.gap_relevance):
            item = proof.gap_relevance[i]
            if (type(item.gap_index) is not int or item.gap_index != i or item.gap != gap
                    or (item.constraint_index is not None and type(item.constraint_index) is not int)
                    or item.constraint_index != index or item.bound_relation != classification
                    or type(item.target_coverage_unresolved) is not bool or item.target_coverage_unresolved != unresolved
                    or type(item.possible_outside) is not bool or item.possible_outside != exterior or item.reason != reason):
                fail("GAP_RELEVANCE_PROOF_MISMATCH", f"gaps/{i}")

    if proof.assessable != bool(positives):
        fail("ASSESSABILITY_PROOF_MISMATCH")
    if not positives:
        if (proof.relation is not None or proof.coverage_completeness is not None
                or proof.reason != "NO_POSITIVE_LENGTH_USABLE_GEOMETRY"
                or proof.target_coverage_intervals or proof.outside_evidence_intervals):
            fail("NONASSESSABLE_ASSERTION_INVALID")
    else:
        has_inside, has_outside = bool(expected_target), bool(expected_outside)
        expected_relation = "unknown"
        if has_inside and has_outside:
            expected_relation = "partial"
        elif has_inside and not possible_outside:
            expected_relation = "inside"
        elif has_outside and not relevant:
            expected_relation = "outside"
        if proof.relation != expected_relation or proof.reason is not None:
            fail("RELATION_PROOF_MISMATCH")
        if proof.coverage_completeness != ("incomplete" if relevant else "complete"):
            fail("COMPLETENESS_PROOF_MISMATCH")
    if not errors:
        proof.to_json()
    return result()
