"""Non-identity parser/result values. Canonical entities retain frozen JSON shapes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SourceLocation:
    source_kind: str
    record_index: int | None
    track_index: int | None = None
    segment_index: int | None = None
    point_index: int | None = None


@dataclass(frozen=True)
class TrackPosition:
    part_index: int
    observation_index: int
    fraction_to_next: float = 0.0

    def __post_init__(self):
        # Representation-independent *identity* requires one canonical form
        # for a vertex: {0, 0.0, -0.0} all designate the exact same parent
        # observation and must never yield different quality / assessment
        # digests. Keep nonzero, NaN and out-of-range values untouched so
        # the independent verifier can report their precise invalidity.
        fraction = self.fraction_to_next
        if type(fraction) in (int, float) and fraction == 0:
            object.__setattr__(self, "fraction_to_next", 0.0)


@dataclass(frozen=True)
class Diagnostic:
    code: str
    source: SourceLocation | None = None
    field: str | None = None
    previous_position: TrackPosition | None = None
    next_position: TrackPosition | None = None


@dataclass(frozen=True)
class ObservationSource:
    position: TrackPosition
    source: SourceLocation


@dataclass(frozen=True)
class IngestionResult:
    outcome: str
    content_hash: dict[str, str] | None
    canonical_track: dict[str, Any] | None
    diagnostics: tuple[Diagnostic, ...]
    observation_sources: tuple[ObservationSource, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible snapshot."""
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class ParsedSample:
    source: SourceLocation
    observation: dict[str, Any] | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True)
class ParsedPart:
    source: SourceLocation
    samples: tuple[ParsedSample, ...]


class SourceFailure(Exception):
    """Stable parse failure; library exception prose never enters output."""

    def __init__(self, code: str, source: SourceLocation | None = None, field: str | None = None):
        self.diagnostic = Diagnostic(code, source, field)
        super().__init__(code)
