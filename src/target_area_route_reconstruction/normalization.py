"""One source-neutral normalizer; every break preserves parent index semantics."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from .models import Diagnostic, IngestionResult, ObservationSource, ParsedPart, TrackPosition

NORMALIZER = {"name": "target-area-route-reconstruction.ingestion", "version": "0.1.0"}


def _digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def normalize(parts: tuple[ParsedPart, ...], track_source: dict[str, str], content_hash: dict[str, str]) -> IngestionResult:
    canonical_parts: list[dict[str, Any]] = []
    lineage: list[ObservationSource] = []
    events: list[Diagnostic | TrackPosition] = []
    for index, part in enumerate(parts):
        if index:
            events.append(Diagnostic("SOURCE_CONTINUITY_BREAK", part.source))
        if not part.samples:
            events.append(Diagnostic("EMPTY_SOURCE_PART", part.source))
        current: list[dict[str, Any]] | None = None
        for sample in part.samples:
            events.extend(sample.diagnostics)
            if sample.observation is None:
                current = None  # absence never authorizes the next connecting edge
                continue
            if current is None:
                current = []
                canonical_parts.append({"observations": current})
            position = TrackPosition(len(canonical_parts) - 1, len(current))
            current.append(sample.observation)
            lineage.append(ObservationSource(position, sample.source))
            events.append(position)

    # Fill neighboring *positioned* parent locations, retaining record order.
    following: TrackPosition | None = None
    enriched: list[Diagnostic | TrackPosition] = []
    for event in reversed(events):
        if isinstance(event, TrackPosition):
            following = event
            enriched.append(event)
        else:
            enriched.append(replace(event, next_position=following))
    previous: TrackPosition | None = None
    diagnostics: list[Diagnostic] = []
    for event in reversed(enriched):
        if isinstance(event, TrackPosition):
            previous = event
        else:
            diagnostics.append(replace(event, previous_position=previous))
    if not canonical_parts:
        diagnostics.append(Diagnostic("NO_POSITIONED_OBSERVATIONS"))
        return IngestionResult("no_positioned_observations", content_hash, None, tuple(diagnostics))

    track = {
        "schema_version": "0.1.0",
        "id": "canonical-track:" + _digest(track_source),
        "revision_id": "sha256:" + _digest({"track_source": track_source, "content_hash": content_hash,
                                            "parts": canonical_parts, "normalizer": NORMALIZER}),
        "track_source": dict(track_source),
        "spatial_reference": "OGC:CRS84",
        "parts": canonical_parts,
        "normalizer": dict(NORMALIZER),
    }
    return IngestionResult("success", content_hash, track, tuple(diagnostics), tuple(lineage))
