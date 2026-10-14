"""Read-only public ingestion, explicit source revision and deterministic failures."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path

from .fit import parse_fit
from .gpx import parse_gpx
from .models import Diagnostic, IngestionResult, SourceFailure
from .normalization import normalize


DEFAULT_SOURCE_BYTES = 64 * 1024 * 1024
MAX_SOURCE_BYTES = 256 * 1024 * 1024
_READ_CHUNK_BYTES = 64 * 1024


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
                expected_sha256: str | None = None,
                max_source_bytes: int = DEFAULT_SOURCE_BYTES) -> IngestionResult:
    """Read a regular FIT/GPX file with a bounded byte budget, without writing.

    Symlinks may resolve to regular files. Admission uses the opened descriptor,
    not a path stat followed by a separate open. No partial-source hash is emitted.
    """
    _reference(track_source)
    if type(max_source_bytes) is not int or not 1 <= max_source_bytes <= MAX_SOURCE_BYTES:
        raise ValueError("INVALID_SOURCE_BYTES_LIMIT")

    def failure(code: str) -> IngestionResult:
        return IngestionResult("failure", None, None, (Diagnostic(code),))

    try:
        # Nonblocking open prevents a FIFO from waiting for a writer before fstat.
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(Path(path), flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                return failure("SOURCE_NOT_REGULAR_FILE")
            if metadata.st_size > max_source_bytes:
                return failure("SOURCE_BYTES_LIMIT_EXCEEDED")
            data = bytearray()
            # Read at most budget + one sentinel byte even if the file grows
            # after fstat. Never hash, parse or return a truncated source.
            while len(data) <= max_source_bytes:
                chunk = os.read(descriptor, min(_READ_CHUNK_BYTES, max_source_bytes + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            if len(data) > max_source_bytes:
                return failure("SOURCE_BYTES_LIMIT_EXCEEDED")
        finally:
            os.close(descriptor)
    except OSError:
        return failure("SOURCE_READ_FAILED")
    return ingest_bytes(bytes(data), source_kind=source_kind, track_source=track_source, expected_sha256=expected_sha256)
