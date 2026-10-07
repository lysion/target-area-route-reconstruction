"""Deterministic ingestion, quality projection and supporting spatial proof."""

from .ingestion import ingest_bytes, ingest_file
from .models import Diagnostic, IngestionResult, ObservationSource, SourceLocation, TrackPosition
from .quality import project_quality
from .quality_models import QualityPolicy, QualityProjection, QualityResult, QualityVerification
from .quality_verifier import verify_quality
from .spatial import prove_spatial_relation
from .spatial_models import SpatialRelationProof, SpatialResult, SpatialVerification
from .spatial_verifier import verify_spatial_relation

__all__ = [
    "ingest_bytes", "ingest_file", "Diagnostic", "IngestionResult",
    "ObservationSource", "SourceLocation", "TrackPosition",
    "project_quality", "verify_quality", "QualityPolicy", "QualityProjection",
    "QualityResult", "QualityVerification",
    "prove_spatial_relation", "verify_spatial_relation", "SpatialRelationProof",
    "SpatialResult", "SpatialVerification",
]
