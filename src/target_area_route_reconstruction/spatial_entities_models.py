"""M2D result wrappers keep entity revision snapshots immutable."""

from __future__ import annotations

from dataclasses import dataclass

from ._m2d_common import canonical_json, strict_load


@dataclass(frozen=True)
class SpatialEntityIssue:
    code: str
    path: str = ""


@dataclass(frozen=True)
class SpatialEntityBundle:
    assessment_json: str
    segment_json: tuple[str, ...]

    @property
    def assessment(self):
        return strict_load(self.assessment_json)

    @property
    def segments(self):
        return tuple(strict_load(item) for item in self.segment_json)

    def to_json(self):
        return canonical_json({
            "spatial_assessment": self.assessment,
            "target_segments": self.segments,
        })


@dataclass(frozen=True)
class SpatialAssemblyResult:
    outcome: str
    bundle: SpatialEntityBundle | None = None
    issues: tuple[SpatialEntityIssue, ...] = ()

    def to_json(self):
        return canonical_json({
            "outcome": self.outcome,
            "spatial_assessment": self.bundle.assessment if self.bundle else None,
            "target_segments": self.bundle.segments if self.bundle else [],
            "issues": [{"code": issue.code, "path": issue.path} for issue in self.issues],
        })


@dataclass(frozen=True)
class SpatialEntityVerification:
    outcome: str
    issues: tuple[SpatialEntityIssue, ...] = ()
