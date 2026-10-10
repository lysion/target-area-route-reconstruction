"""Independent coverage, provenance and proof checks. Does not import producer."""

import math
from fractions import Fraction

from ._quality_evidence import GAP_CODES, evidence_digest, evidence_issues
from ._quality_numerics import distance_metres, utc_seconds
from .models import IngestionResult, TrackPosition
from .quality_models import (
    DomainProofParameters, EdgeDiagnostic, ParentInterval, ParentReference,
    QualityAlgorithm, QualityIssue, QualityParameters, QualityPolicy,
    QualityProjection, QualityVerification,
)


def verify_quality(projection: QualityProjection, evidence: IngestionResult, *,
                   policy: QualityPolicy) -> QualityVerification:
    """Caller supplies the expected policy and trusted M2A snapshot independently.

    Malformed typed claims fail with stable codes rather than parser exceptions.
    Verification never supplies missing constraints or silently repairs claims.
    """
    if not isinstance(policy, QualityPolicy):
        return QualityVerification("invalid", (QualityIssue("QUALITY_POLICY_INVALID"),))
    issues = evidence_issues(evidence)
    if issues:
        return QualityVerification("quality_evidence_unavailable", issues)
    try:
        return _verify(projection, evidence, policy)
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, OverflowError):
        return QualityVerification("invalid", (QualityIssue("PROJECTION_MALFORMED"),))


def _verify(q, evidence, policy):
    issues = []
    def fail(code, path=""):
        issues.append(QualityIssue(code, path))
    def result(statuses=()):
        return QualityVerification("invalid" if issues else "valid", tuple(issues), tuple(statuses))
    if not isinstance(q, QualityProjection):
        fail("PROJECTION_MALFORMED")
        return result()
    if any(type(value) is not tuple for value in (q.usable_intervals, q.excluded_intervals,
                                                 q.gaps, q.gap_constraints, q.diagnostics)):
        fail("PROJECTION_MALFORMED")
        return result()
    track = evidence.canonical_track
    parts = track["parts"]
    parent = ParentReference(track["id"], track["revision_id"])
    if q.canonical_track != parent:
        fail("PARENT_REFERENCE_MISMATCH", "canonical_track")
    if q.evidence_digest != evidence_digest(evidence):
        fail("EVIDENCE_REFERENCE_MISMATCH", "evidence_digest")
    parameters = QualityParameters(policy)
    if q.algorithm != QualityAlgorithm(parameters):
        fail("ALGORITHM_CONTRACT_MISMATCH", "algorithm")
    if issues:
        return result()

    def position(pos, path):
        if not isinstance(pos, TrackPosition):
            fail("TRACK_POSITION_INVALID", path)
            return False
        p, i, f = pos.part_index, pos.observation_index, pos.fraction_to_next
        if (type(p) is not int or not 0 <= p < len(parts) or type(i) is not int
                or not 0 <= i < len(parts[p]["observations"])):
            fail("TRACK_POSITION_OUT_OF_BOUNDS", path)
            return False
        # Even objects manufactured without TrackPosition.__post_init__ may
        # arrive from an untrusted snapshot. Refuse noncanonical signed zeros
        # and integer fractions before they enter a revision/digest identity.
        if (type(f) is not float or not math.isfinite(f) or not 0 <= f < 1
                or (f == 0.0 and math.copysign(1.0, f) < 0)
                or (f != 0 and i + 1 == len(parts[p]["observations"]))):
            fail("TRACK_POSITION_INVALID", path)
            return False
        if f != 0:
            fail("WHOLE_EDGE_RANGE_REQUIRED", path)
            return False
        return True

    # Domain identity is the pair (original part, original edge), not geometry.
    universe = {(p, i) for p, part in enumerate(parts) for i in range(len(part["observations"]) - 1)}
    classes = {}
    excluded_by_edge = {}
    for name, entries in (("usable_intervals", q.usable_intervals), ("excluded_intervals", q.excluded_intervals)):
        previous_start = None
        seen = set()
        for n, entry in enumerate(entries):
            interval = entry if name == "usable_intervals" else entry.interval
            path = f"{name}/{n}"
            valid_start = position(interval.start, path + "/start")
            valid_end = position(interval.end, path + "/end")
            if not (valid_start and valid_end):
                continue
            a, b = interval.start, interval.end
            if a.part_index != b.part_index:
                fail("INTERVAL_CROSS_PART", path)
                continue
            if a.observation_index >= b.observation_index:
                fail("INTERVAL_REVERSED_OR_EMPTY", path)
                continue
            start = (a.part_index, a.observation_index)
            if previous_start is not None and start < previous_start:
                fail("INTERVAL_ORDER_INVALID", path)
            previous_start = start
            if name == "excluded_intervals" and b.observation_index != a.observation_index + 1:
                fail("EXCLUSION_MUST_BE_ONE_EDGE", path)
            for i in range(a.observation_index, b.observation_index):
                edge = (a.part_index, i)
                if edge in seen:
                    fail("INTERVAL_OVERLAP", path)
                seen.add(edge)
                if edge in classes:
                    fail("EDGE_DOUBLE_ACCOUNTED", path)
                classes[edge] = name
                if name == "excluded_intervals":
                    excluded_by_edge[edge] = (n, entry)
    # A verified QualityProjection is a *canonical coverage partition*, not
    # merely a set of admitted edges. Neighboring intervals within the same
    # original part cannot be split at an arbitrary observation vertex. Only
    # an excluded edge or a real source-part boundary terminates a usable run.
    # This admission check prevents M2D from mistaking representational
    # fragmentation for distinct maximal TargetSegments (ADR-0005).
    previous_usable = None
    for index, admitted in enumerate(q.usable_intervals):
        if (previous_usable is not None
                and previous_usable.end.part_index == admitted.start.part_index
                and previous_usable.end.observation_index == admitted.start.observation_index):
            fail("USABLE_INTERVAL_NOT_MAXIMAL", f"usable_intervals/{index}")
        previous_usable = admitted
    if universe - classes.keys():
        fail("EDGE_UNACCOUNTED")
    if issues:
        return result()

    # Re-evaluate the contracted rule for each original edge; never call the
    # producer's decision, coalescing or gap builders.
    mapping_indices = {m.position: i for i, m in enumerate(evidence.observation_sources)}
    expected_diagnostics = []
    for p, i in sorted(universe):
        left, right = parts[p]["observations"][i:i + 2]
        interval = ParentInterval(TrackPosition(p, i), TrackPosition(p, i + 1))
        cap = policy.max_implied_speed_mps
        reason = None
        reject = False
        if cap is None:
            reason = "SPEED_RULE_DISABLED"
        elif not {"timestamp"} <= left.keys() or not {"timestamp"} <= right.keys():
            reason = "SPEED_TIME_MISSING"
        else:
            times = (utc_seconds(left["timestamp"]), utc_seconds(right["timestamp"]))
            if None in times:
                reason = "SPEED_TIME_UNSUPPORTED"
            elif times[1] <= times[0]:
                reason = "SPEED_TIME_NONINCREASING"
            else:
                try:
                    d = Fraction(distance_metres(left["position"], right["position"]))
                    threshold = Fraction(cap) * (times[1] - times[0])
                    margin = Fraction(parameters.distance_roundoff_guard_m)
                    reject = d > threshold + margin
                    if not reject and d > threshold - margin:
                        reason = "SPEED_NUMERICALLY_INDETERMINATE"
                except ValueError:
                    reason = "SPEED_DISTANCE_UNAVAILABLE"
        claimed_rejected = (p, i) in excluded_by_edge
        if reject != claimed_rejected:
            fail("EDGE_DECISION_MISMATCH", f"parts/{p}/edges/{i}")
        if claimed_rejected:
            n, exclusion = excluded_by_edge[(p, i)]
            if exclusion.reason != "IMPLIED_SPEED_EXCEEDS_POLICY":
                fail("EXCLUSION_REASON_INVALID", f"excluded_intervals/{n}")
            expected = (mapping_indices[interval.start], mapping_indices[interval.end])
            if (type(exclusion.observation_source_indices) is not tuple
                    or any(type(i) is not int for i in exclusion.observation_source_indices)
                    or exclusion.observation_source_indices != expected):
                fail("EXCLUSION_EVIDENCE_MISMATCH", f"excluded_intervals/{n}")
        if reason is not None:
            expected_diagnostics.append(EdgeDiagnostic(interval, reason))
    # Dataclass equality accepts 0 == 0.0 == -0.0, but snapshot JSON does
    # not: diagnostics are hashed into the downstream spatial authority.
    # Validate every original diagnostic endpoint independently before a
    # structurally equal claim can be admitted as the canonical projection.
    for n, diagnostic in enumerate(q.diagnostics):
        path = f"diagnostics/{n}"
        if not isinstance(diagnostic, EdgeDiagnostic) or not isinstance(diagnostic.interval, ParentInterval):
            fail("QUALITY_DIAGNOSTICS_MISMATCH", path)
            continue
        position(diagnostic.interval.start, path + "/interval/start")
        position(diagnostic.interval.end, path + "/interval/end")
    if q.diagnostics != tuple(expected_diagnostics):
        fail("QUALITY_DIAGNOSTICS_MISMATCH", "diagnostics")

    # Check every diagnostic reference against independently supplied source
    # evidence. Exactly one source gap per neighbor pair; every cause survives.
    source_groups = {}
    for index, diag in enumerate(evidence.diagnostics):
        if diag.code in GAP_CODES:
            source_groups.setdefault((diag.previous_position, diag.next_position), []).append(index)
    seen_sources, seen_exclusions = set(), set()
    previous_key = None
    for n, gap in enumerate(q.gaps):
        path = f"gaps/{n}"
        if gap.canonical_track != parent:
            fail("GAP_PARENT_MISMATCH", path)
        if gap.state != "unresolved":
            fail("GAP_STATE_INVALID", path)
        if gap.start is not None and not position(gap.start, path + "/start"):
            continue
        if gap.end is not None and not position(gap.end, path + "/end"):
            continue
        key = ((-1, -1) if gap.start is None else (gap.start.part_index, gap.start.observation_index),
               (len(parts), 0) if gap.end is None else (gap.end.part_index, gap.end.observation_index), gap.kind)
        if previous_key is not None and key < previous_key:
            fail("GAP_ORDER_INVALID", path)
        previous_key = key
        if gap.kind == "source_gap":
            pair = (gap.start, gap.end)
            indices = source_groups.get(pair)
            if indices is None or pair in seen_sources:
                fail("GAP_PROVENANCE_MISMATCH", path)
            else:
                seen_sources.add(pair)
                causes = tuple(dict.fromkeys(evidence.diagnostics[i].code for i in indices))
                if (type(gap.diagnostic_indices) is not tuple
                        or any(type(i) is not int for i in gap.diagnostic_indices)
                        or gap.diagnostic_indices != tuple(indices) or gap.causes != causes
                        or gap.excluded_interval_index is not None):
                    fail("GAP_PROVENANCE_MISMATCH", path)
        elif gap.kind == "quality_exclusion":
            index = gap.excluded_interval_index
            if (type(index) is not int or not 0 <= index < len(q.excluded_intervals)
                    or index in seen_exclusions):
                fail("GAP_PROVENANCE_MISMATCH", path)
            else:
                seen_exclusions.add(index)
                exclusion = q.excluded_intervals[index]
                if (gap.start != exclusion.interval.start or gap.end != exclusion.interval.end
                        or gap.causes != (exclusion.reason,) or gap.diagnostic_indices):
                    fail("GAP_PROVENANCE_MISMATCH", path)
        else:
            fail("GAP_KIND_UNSUPPORTED", path)
    if set(source_groups) != seen_sources or set(range(len(q.excluded_intervals))) != seen_exclusions:
        fail("REQUIRED_GAP_MISSING", "gaps")
    if issues:
        return result()

    statuses = ["unavailable"] * len(q.gaps)
    previous_index = -1
    for n, constraint in enumerate(q.gap_constraints):
        path = f"gap_constraints/{n}"
        index = constraint.gap_index
        if type(index) is not int or not 0 <= index < len(q.gaps) or index <= previous_index:
            fail("CONSTRAINT_GAP_REFERENCE_INVALID", path)
            continue
        previous_index = index
        before = len(issues)
        if constraint.method != "crs84-domain" or constraint.version != "1":
            fail("GAP_CONSTRAINT_UNSUPPORTED", path)
            statuses[index] = "unsupported"
            continue
        if constraint.canonical_track != parent or constraint.evidence_digest != q.evidence_digest:
            fail("CONSTRAINT_EVIDENCE_MISMATCH", path)
        if constraint.parameters != DomainProofParameters():
            fail("CONSTRAINT_PARAMETERS_MISMATCH", path)
        bound = constraint.bound
        if (len(bound.bbox) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in bound.bbox)):
            fail("CONSTRAINT_BOUND_INVALID", path)
        elif bound.spatial_reference != "OGC:CRS84" or bound.bbox != (-180.0, -90.0, 180.0, 90.0):
            fail("CONSTRAINT_BOUND_PROOF_MISMATCH", path)
        statuses[index] = "verified" if len(issues) == before else "invalid"
    if policy.include_domain_bounds:
        if len(q.gap_constraints) != len(q.gaps):
            fail("CONSTRAINT_POLICY_MISMATCH", "gap_constraints")
    elif q.gap_constraints:
        fail("CONSTRAINT_POLICY_MISMATCH", "gap_constraints")
    # Also reject mutable/non-serializable values smuggled into typed fields.
    if not issues:
        q.to_json()
    return result(statuses)
