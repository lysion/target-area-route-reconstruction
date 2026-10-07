"""M2A canonical ingestion; identity and quality decisions remain with callers."""

from .ingestion import ingest_bytes, ingest_file
from .models import Diagnostic, IngestionResult, ObservationSource, SourceLocation, TrackPosition

__all__ = [
    "ingest_bytes", "ingest_file", "Diagnostic", "IngestionResult",
    "ObservationSource", "SourceLocation", "TrackPosition",
]
