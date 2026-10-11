"""Closed, type-precise admission of M2A/M2B/M2C hash-bearing snapshots.

Python dataclass equality conflates primitive values such as False, 0, 0.0;
asdict()/JSON preserve their different representations. All declared nested
field types must match before an otherwise equivalent claim can be trusted
as identity-bearing evidence.
"""
from __future__ import annotations

import math
from dataclasses import fields, is_dataclass
from functools import lru_cache
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

from .models import Diagnostic, IngestionResult, ObservationSource, SourceLocation, TrackPosition
from .quality_models import (
    DomainBound, DomainProofParameters, EdgeDiagnostic, ExcludedInterval, Gap,
    GapConstraint, ParentInterval, ParentReference, QualityAlgorithm,
    QualityParameters, QualityPolicy, QualityProjection,
)
from .spatial_models import (
    GapRelevance, SpatialAlgorithm, SpatialAuthority, SpatialParameters,
    SpatialRelationProof, StationaryEvidence,
)

EVIDENCE_TYPES = frozenset((
    IngestionResult, Diagnostic, ObservationSource, SourceLocation, TrackPosition,
))
QUALITY_TYPES = frozenset((
    TrackPosition, ParentReference, QualityPolicy, QualityParameters,
    QualityAlgorithm, ParentInterval, ExcludedInterval, EdgeDiagnostic, Gap,
    DomainBound, DomainProofParameters, GapConstraint, QualityProjection,
))
SPATIAL_TYPES = QUALITY_TYPES | frozenset((
    SpatialParameters, SpatialAlgorithm, SpatialAuthority, StationaryEvidence,
    GapRelevance, SpatialRelationProof,
))


@lru_cache(maxsize=None)
def _declared_fields(model_type):
    """Resolve deferred annotations once; a field's declared type is binding."""
    return get_type_hints(model_type)


def _matches_declared_type(value, annotation, allowed_types):
    """Admit only the exact primitive/container/dataclass spelling of a field.

    Checking Python equality alone is insufficient: False == 0 == 0.0,
    and a tuple containing any of these values can compare equal while
    producing a different JSON fingerprint.
    """
    if annotation is Any:
        # Canonical entities use dict[str, Any], but the payload is still
        # native finite JSON. Do not let asdict() silently serialize a foreign
        # dataclass or a container subclass hidden inside the entity snapshot.
        if value is None or type(value) in (str, int, bool):
            return True
        if type(value) is float:
            return math.isfinite(value)
        if type(value) is list:
            return all(_matches_declared_type(item, Any, allowed_types) for item in value)
        if type(value) is dict:
            return all(type(key) is str and _matches_declared_type(item, Any, allowed_types)
                       for key, item in value.items())
        return False
    if annotation is type(None):
        return value is None
    if annotation is int:
        return type(value) is int
    if annotation is bool:
        return type(value) is bool
    if annotation is str:
        return type(value) is str
    if annotation is float:
        return type(value) is float and math.isfinite(value)

    origin = get_origin(annotation)
    members = get_args(annotation)
    if origin in (Union, UnionType):
        return any(_matches_declared_type(value, option, allowed_types)
                   for option in members)
    if origin is tuple:
        if type(value) is not tuple:
            return False
        if len(members) == 2 and members[1] is Ellipsis:
            return all(_matches_declared_type(item, members[0], allowed_types)
                       for item in value)
        return len(value) == len(members) and all(
            _matches_declared_type(item, expected, allowed_types)
            for item, expected in zip(value, members))
    if origin is dict:
        return type(value) is dict and all(
            _matches_declared_type(key, members[0], allowed_types)
            and _matches_declared_type(item, members[1], allowed_types)
            for key, item in value.items())

    # Only explicitly listed identity models may appear in these structures.
    # No isinstance: dataclass subclasses can serialize additional fields.
    return annotation in allowed_types and type(value) is annotation and canonical_snapshot(
        value, allowed_types)


def canonical_snapshot(value, allowed_types):
    """Validate an immutable supporting snapshot against its declared schema.

    This function must never silently normalize untrusted objects. The
    caller's semantic verifier performs provenance, range and authority checks
    separately; this gate ensures their accepted JSON has one representation.
    """
    if type(value) not in allowed_types or not is_dataclass(value):
        return False
    # Only declared data may live on an exact model instance. Otherwise it
    # can shadow __dataclass_fields__ (asdict's field source) OR to_dict /
    # to_json (the pipeline's codec), without changing type or equality.
    # Class-owned enumeration and rejection of shadowing must stay paired.
    model_fields = fields(type(value))
    state = getattr(value, "__dict__", {})
    if (type(state) is not dict or any(type(key) is not str for key in state)
            or not set(state) <= {field.name for field in model_fields}):
        return False
    if type(value) is TrackPosition:
        fraction = value.fraction_to_next
        if (type(fraction) is not float or not math.isfinite(fraction)
                or (fraction == 0.0 and math.copysign(1.0, fraction) < 0)):
            return False
    if type(value) is QualityPolicy:
        cap = value.max_implied_speed_mps
        if cap is not None and (type(cap) is not float or not math.isfinite(cap) or cap <= 0):
            return False
    if type(value) is DomainBound:
        if any(type(n) is not float or not math.isfinite(n)
               or (n == 0.0 and math.copysign(1.0, n) < 0)
               for n in value.bbox) if type(value.bbox) is tuple else True:
            return False

    declared = _declared_fields(type(value))
    try:
        return all(
            field.name in declared and _matches_declared_type(
                getattr(value, field.name), declared[field.name], allowed_types)
            for field in model_fields)
    except AttributeError:
        return False  # a bypassed constructor cannot omit required fields


def canonical_json_value(value):
    """Finite native JSON data, without polymorphic copy/number behavior."""
    return _matches_declared_type(value, Any, frozenset())
