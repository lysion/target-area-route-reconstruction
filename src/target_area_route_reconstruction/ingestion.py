"""Read-only public ingestion, explicit source revision and deterministic failures."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .fit import parse_fit
from .gpx import parse_gpx
from .models import Diagnostic, IngestionResult, SourceFailure
from .normalization import normalize


def _reference(track_source: dict[str, str]) -> dict[str, str]:
    if not isinstance(track_source, dict) or set(track_source) != {"id", "revision_id"} or any(
        not isinstance(value, str) or not 1 <= len(value) <= 256 for value in track_source.values()
    ):
        raise ValueError("INVALID_TRACK_SOURCE_REFERENCE")
    return dict(track_source)


def ingest_bytes(data: bytes, *, source_kind: str, track_source: dict[str, str],
                 expected_sha256: str | None = None) -> IngestionResult:
    """Normalize one preserved source. Activity/TrackSource identity is caller-owned."""
    reference = _reference(track_source)
    if not isinstance(data, bytes):
        raise TypeError("SOURCE_BYTES_REQUIRED")
    content_hash = {"algorithm": "sha256", "digest": hashlib.sha256(data).hexdigest()}
    if expected_sha256 is not None and (
        not isinstance(expected_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
        or expected_sha256 != content_hash["digest"]
    ):
        return IngestionResult("failure", content_hash, None, (Diagnostic("SOURCE_HASH_MISMATCH"),))
    parsers = {"fit": parse_fit, "gpx": parse_gpx}
    if source_kind not in parsers:
        return IngestionResult("failure", content_hash, None, (Diagnostic("UNSUPPORTED_SOURCE_KIND"),))
    try:
        parts = parsers[source_kind](data)
    except SourceFailure as exc:
        return IngestionResult("failure", content_hash, None, (exc.diagnostic,))
    return normalize(parts, reference, content_hash)


def ingest_file(path: str | Path, *, source_kind: str, track_source: dict[str, str],
                expected_sha256: str | None = None) -> IngestionResult:
    """Read bytes once without modifying the file or inferring identity from its name."""
    _reference(track_source)
    try:
        data = Path(path).read_bytes()
    except OSError:
        return IngestionResult("failure", None, None, (Diagnostic("SOURCE_READ_FAILED"),))
    return ingest_bytes(data, source_kind=source_kind, track_source=track_source, expected_sha256=expected_sha256)
