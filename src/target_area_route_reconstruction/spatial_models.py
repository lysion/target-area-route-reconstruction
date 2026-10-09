"""M2C supporting proof values; no entity identity or entity assembly."""

from dataclasses import dataclass

from .quality_models import Gap, ParentInterval, ParentReference, QualityAlgorithm, Snapshot


@dataclass(frozen=True)
class SpatialParameters:
    shapely_version: str
    geos_version: str
    interpolation: str = "planar-crs84-linear"
    fraction_method: str = "dominant-axis-binary64-v1"
    coordinate_error_cap_deg: float = 1e-12
    comparison_ulps: int = 8
    local_error_divisor: int = 4
    boundary: str = "positive-length-covered;point-contact-excluded"


@dataclass(frozen=True)
class SpatialAlgorithm:
    parameters: SpatialParameters
    name: str = "target-area-route-reconstruction.spatial-proof"
    version: str = "0.1.1"


@dataclass(frozen=True)
class SpatialAuthority:
    canonical_track: ParentReference
    target_area: ParentReference
    target_digest: str
    evidence_digest: str
    quality_projection_digest: str
    quality_algorithm: QualityAlgorithm


@dataclass(frozen=True)
class StationaryEvidence:
    interval: ParentInterval
    target_covered: bool


@dataclass(frozen=True)
class GapRelevance:
    gap_index: int
    gap: Gap
    constraint_index: int | None
    bound_relation: str
    target_coverage_unresolved: bool
    possible_outside: bool
    reason: str


@dataclass(frozen=True)
class SpatialRelationProof(Snapshot):
    authority: SpatialAuthority
    algorithm: SpatialAlgorithm
    assessable: bool
    relation: str | None
    coverage_completeness: str | None
    reason: str | None
    target_coverage_intervals: tuple[ParentInterval, ...]
    outside_evidence_intervals: tuple[ParentInterval, ...]
    stationary_evidence: tuple[StationaryEvidence, ...]
    gap_relevance: tuple[GapRelevance, ...]


@dataclass(frozen=True)
class SpatialIssue:
    code: str
    path: str = ""


@dataclass(frozen=True)
class SpatialResult(Snapshot):
    outcome: str
    proof: SpatialRelationProof | None
    issues: tuple[SpatialIssue, ...] = ()


@dataclass(frozen=True)
class SpatialVerification(Snapshot):
    outcome: str
    issues: tuple[SpatialIssue, ...] = ()


class SpatialFailure(Exception):
    def __init__(self, code, path="", *, issues=None):
        self.issues = tuple(issues) if issues is not None else (SpatialIssue(code, path),)
        super().__init__(code)
