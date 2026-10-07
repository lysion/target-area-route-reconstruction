"""Whole-edge quality selection. Never edits or reindexes canonical evidence."""

from fractions import Fraction

from ._quality_evidence import GAP_CODES, evidence_digest, evidence_issues
from ._quality_numerics import distance_metres, utc_seconds
from .models import IngestionResult, TrackPosition
from .quality_models import (
    EdgeDiagnostic, ExcludedInterval, Gap, GapConstraint, ParentInterval,
    ParentReference, QualityAlgorithm, QualityParameters, QualityPolicy,
    QualityProjection, QualityResult,
)


def _decision(left: dict, right: dict, parameters: QualityParameters) -> str:
    cap = parameters.policy.max_implied_speed_mps
    if cap is None:
        return "SPEED_RULE_DISABLED"
    if "timestamp" not in left or "timestamp" not in right:
        return "SPEED_TIME_MISSING"
    start, end = utc_seconds(left["timestamp"]), utc_seconds(right["timestamp"])
    if start is None or end is None:
        return "SPEED_TIME_UNSUPPORTED"
    if end <= start:
        return "SPEED_TIME_NONINCREASING"
    try:
        distance = Fraction(distance_metres(left["position"], right["position"]))
    except ValueError:
        return "SPEED_DISTANCE_UNAVAILABLE"
    limit = Fraction(cap) * (end - start)
    guard = Fraction(parameters.distance_roundoff_guard_m)
    if distance - guard > limit:
        return "IMPLIED_SPEED_EXCEEDS_POLICY"
    if distance + guard > limit:
        return "SPEED_NUMERICALLY_INDETERMINATE"
    return "ADMITTED"


def project_quality(evidence: IngestionResult, *, policy: QualityPolicy) -> QualityResult:
    """Policy is explicit, including the choice to disable motion screening."""
    if not isinstance(policy, QualityPolicy):
        raise ValueError("QUALITY_POLICY_INVALID")
    issues = evidence_issues(evidence)
    if issues:
        return QualityResult("quality_evidence_unavailable", None, issues)
    track = evidence.canonical_track
    parent = ParentReference(track["id"], track["revision_id"])
    algorithm = QualityAlgorithm(QualityParameters(policy))
    fingerprint = evidence_digest(evidence)
    usable, excluded, diagnostics = [], [], []
    source_indices = {m.position: i for i, m in enumerate(evidence.observation_sources)}
    for p, part in enumerate(track["parts"]):
        observations = part["observations"]
        run_start = None
        for i, (left, right) in enumerate(zip(observations, observations[1:])):
            interval = ParentInterval(TrackPosition(p, i), TrackPosition(p, i + 1))
            decision = _decision(left, right, algorithm.parameters)
            rejected = decision == "IMPLIED_SPEED_EXCEEDS_POLICY"
            if rejected:
                if run_start is not None:
                    usable.append(ParentInterval(TrackPosition(p, run_start), TrackPosition(p, i)))
                    run_start = None  # rejection breaks usable continuity
                excluded.append(ExcludedInterval(interval, decision,
                                (source_indices[interval.start], source_indices[interval.end])))
            else:
                if run_start is None:
                    run_start = i
                if decision != "ADMITTED":
                    diagnostics.append(EdgeDiagnostic(interval, decision))
        if run_start is not None:
            usable.append(ParentInterval(TrackPosition(p, run_start), TrackPosition(p, len(observations) - 1)))

    # Multiple missing records / empty parts remain individually referenced.
    groups = {}
    for i, diagnostic in enumerate(evidence.diagnostics):
        if diagnostic.code in GAP_CODES:
            groups.setdefault((diagnostic.previous_position, diagnostic.next_position), []).append(i)
    gaps = [Gap(parent, start, end, "source_gap",
                tuple(dict.fromkeys(evidence.diagnostics[i].code for i in indices)), tuple(indices))
            for (start, end), indices in groups.items()]
    gaps.extend(Gap(parent, item.interval.start, item.interval.end, "quality_exclusion",
                    (item.reason,), excluded_interval_index=i) for i, item in enumerate(excluded))
    def order(gap):
        start = (-1, -1) if gap.start is None else (gap.start.part_index, gap.start.observation_index)
        end = (len(track["parts"]), 0) if gap.end is None else (gap.end.part_index, gap.end.observation_index)
        return start, end, gap.kind
    gaps.sort(key=order)
    constraints = tuple(GapConstraint(i, parent, fingerprint) for i in range(len(gaps))) if policy.include_domain_bounds else ()
    return QualityResult("produced", QualityProjection(parent, algorithm, fingerprint,
                         tuple(usable), tuple(excluded), tuple(gaps), constraints, tuple(diagnostics)))
