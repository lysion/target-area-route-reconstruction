"""Immutable supporting quality values; all positions belong to the parent."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass

from .models import TrackPosition


class Snapshot:
    def to_dict(self) -> dict:
        return json.loads(self.to_json())

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class ParentReference:
    id: str
    revision_id: str


@dataclass(frozen=True)
class QualityPolicy:
    max_implied_speed_mps: float | None = None
    include_domain_bounds: bool = False

    def __post_init__(self):
        value = self.max_implied_speed_mps
        if value is not None:
            if type(value) not in (int, float):
                raise ValueError("QUALITY_POLICY_INVALID")
            try:
                number = float(value)
            except OverflowError as exc:
                raise ValueError("QUALITY_POLICY_INVALID") from exc
            if not math.isfinite(number) or number <= 0:
                raise ValueError("QUALITY_POLICY_INVALID")
            object.__setattr__(self, "max_implied_speed_mps", number)
        if type(self.include_domain_bounds) is not bool:
            raise ValueError("QUALITY_POLICY_INVALID")


@dataclass(frozen=True)
class QualityParameters:
    policy: QualityPolicy
    distance_method: str = "geographiclib-2.1-wgs84-inverse"
    distance_roundoff_guard_m: float = 0.000001
    temporal_method: str = "exact-utc-seconds-fraction-v1"


@dataclass(frozen=True)
class QualityAlgorithm:
    parameters: QualityParameters
    name: str = "target-area-route-reconstruction.quality"
    version: str = "0.1.0"


@dataclass(frozen=True)
class ParentInterval:
    start: TrackPosition
    end: TrackPosition


@dataclass(frozen=True)
class ExcludedInterval:
    interval: ParentInterval
    reason: str
    # Indices into the fingerprinted M2A observation_sources array, NOT coordinates.
    observation_source_indices: tuple[int, int]


@dataclass(frozen=True)
class EdgeDiagnostic:
    interval: ParentInterval
    code: str


@dataclass(frozen=True)
class Gap:
    canonical_track: ParentReference
    start: TrackPosition | None
    end: TrackPosition | None
    kind: str
    causes: tuple[str, ...]
    diagnostic_indices: tuple[int, ...] = ()
    excluded_interval_index: int | None = None
    state: str = "unresolved"


@dataclass(frozen=True)
class DomainBound:
    # A coordinate-domain envelope, never route geometry.
    bbox: tuple[float, float, float, float] = (-180.0, -90.0, 180.0, 90.0)
    spatial_reference: str = "OGC:CRS84"


@dataclass(frozen=True)
class DomainProofParameters:
    coordinate_contract: str = "core-0.1.0-OGC:CRS84"


@dataclass(frozen=True)
class GapConstraint:
    gap_index: int
    canonical_track: ParentReference
    evidence_digest: str
    bound: DomainBound = DomainBound()
    method: str = "crs84-domain"
    version: str = "1"
    parameters: DomainProofParameters = DomainProofParameters()


@dataclass(frozen=True)
class QualityProjection(Snapshot):
    canonical_track: ParentReference
    algorithm: QualityAlgorithm
    evidence_digest: str
    usable_intervals: tuple[ParentInterval, ...]
    excluded_intervals: tuple[ExcludedInterval, ...]
    gaps: tuple[Gap, ...]
    gap_constraints: tuple[GapConstraint, ...] = ()
    diagnostics: tuple[EdgeDiagnostic, ...] = ()


@dataclass(frozen=True)
class QualityIssue:
    code: str
    path: str = ""


@dataclass(frozen=True)
class QualityResult(Snapshot):
    outcome: str
    projection: QualityProjection | None
    issues: tuple[QualityIssue, ...] = ()


@dataclass(frozen=True)
class QualityVerification(Snapshot):
    outcome: str
    issues: tuple[QualityIssue, ...] = ()
    gap_constraint_statuses: tuple[str, ...] = ()
