"""Closed supporting-value admission for hash-bearing M2B/M2C snapshots.

Dataclass equality is deliberately NOT a canonical identity predicate: a
subclass can carry additional asdict() fields while comparing equal to its
base class. Numeric equality also conflates 1 with 1.0 and signed zeros.
Reject unsupported structure *before* a JSON digest is computed.
"""
from __future__ import annotations

import math
from dataclasses import fields, is_dataclass

from .models import TrackPosition
from .quality_models import (
    DomainBound, DomainProofParameters, EdgeDiagnostic, ExcludedInterval, Gap,
    GapConstraint, ParentInterval, ParentReference, QualityAlgorithm,
    QualityParameters, QualityPolicy, QualityProjection,
)
from .spatial_models import (
    GapRelevance, SpatialAlgorithm, SpatialAuthority, SpatialParameters,
    SpatialRelationProof, StationaryEvidence,
)

QUALITY_TYPES = frozenset((
    TrackPosition, ParentReference, QualityPolicy, QualityParameters,
    QualityAlgorithm, ParentInterval, ExcludedInterval, EdgeDiagnostic, Gap,
    DomainBound, DomainProofParameters, GapConstraint, QualityProjection,
))
SPATIAL_TYPES = QUALITY_TYPES | frozenset((
    SpatialParameters, SpatialAlgorithm, SpatialAuthority, StationaryEvidence,
    GapRelevance, SpatialRelationProof,
))


def canonical_snapshot(value, allowed_types):
    """Check *exact* nested dataclass/container shape and fixed numeric spells.

    This intentionally does not normalize an untrusted object: silently
    repairing it after another component has hashed its asdict() would retain
    the ambiguity. Producer-created ordinary dataclasses are unaffected.
    Semantic domain/provenance validation remains in the independent verifiers.
    """
    if is_dataclass(value) and not isinstance(value, type):
        if type(value) not in allowed_types:
            return False
        if type(value) is QualityPolicy:
            cap = value.max_implied_speed_mps
            if (cap is not None and
                    (type(cap) is not float or not math.isfinite(cap) or cap <= 0)):
                return False
            if type(value.include_domain_bounds) is not bool:
                return False
        if type(value) is DomainBound:
            if (type(value.bbox) is not tuple or len(value.bbox) != 4 or
                any(type(n) is not float or not math.isfinite(n) or
                    (n == 0.0 and math.copysign(1.0, n) < 0)
                    for n in value.bbox)):
                return False
        if type(value) is QualityParameters:
            guard = value.distance_roundoff_guard_m
            if type(guard) is not float or not math.isfinite(guard):
                return False
        if type(value) is SpatialParameters:
            if (type(value.coordinate_error_cap_deg) is not float or
                    not math.isfinite(value.coordinate_error_cap_deg) or
                    type(value.comparison_ulps) is not int or
                    type(value.local_error_divisor) is not int):
                return False
        return all(canonical_snapshot(getattr(value, f.name), allowed_types)
                   for f in fields(value))
    if type(value) is tuple:
        return all(canonical_snapshot(v, allowed_types) for v in value)
    # Lists/dicts are not part of the closed M2B/M2C supporting-value graph.
    if type(value) in (list, dict, set):
        return False
    return type(value) in (str, int, float, bool, type(None)) and (
        type(value) is not float or math.isfinite(value))
