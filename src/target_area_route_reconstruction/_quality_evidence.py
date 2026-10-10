"""Input boundary checks shared by producer/verifier, never quality decisions.

The caller supplies trusted M2A evidence. Fingerprints bind snapshots; they are
not signatures and do not authenticate raw bytes without the ingestion layer.
"""

import hashlib
import json
import math
import re
from bisect import bisect_left

from .models import IngestionResult, TrackPosition
from .quality_models import QualityIssue

GAP_CODES = frozenset({"SOURCE_CONTINUITY_BREAK", "EMPTY_SOURCE_PART",
                       "POSITION_MISSING", "POSITION_INVALID_SENTINEL"})


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def evidence_digest(evidence: IngestionResult) -> str:
    return digest(evidence.to_dict())


def _canonical_source_vertex(position) -> bool:
    """Admit only original M2A vertices with one stable typed JSON identity.

    Dataclass equality alone conflates 0, 0.0 and -0.0 even though serialized
    evidence SHA-256 does not. Source mappings and ingestion diagnostics are
    both included in the M2A fingerprint, so guard both before hashing.
    """
    return (isinstance(position, TrackPosition)
            and type(position.part_index) is int
            and type(position.observation_index) is int
            and type(position.fraction_to_next) is float
            and position.fraction_to_next == 0.0
            and math.copysign(1.0, position.fraction_to_next) == 1.0)


def evidence_issues(evidence: IngestionResult) -> tuple[QualityIssue, ...]:
    """Check the supported M2A hand-off, including unchanged revision content."""
    if not isinstance(evidence, IngestionResult):
        return (QualityIssue("QUALITY_EVIDENCE_INVALID"),)
    if evidence.outcome != "success" or evidence.canonical_track is None:
        return (QualityIssue("QUALITY_EVIDENCE_UNAVAILABLE"),)
    try:
        track = evidence.canonical_track
        if (track["schema_version"] != "0.1.0" or track["spatial_reference"] != "OGC:CRS84"
                or track["normalizer"] != {"name": "target-area-route-reconstruction.ingestion", "version": "0.1.0"}):
            return (QualityIssue("QUALITY_EVIDENCE_UNSUPPORTED"),)
        if (evidence.content_hash["algorithm"] != "sha256"
                or re.fullmatch("[0-9a-f]{64}", evidence.content_hash["digest"]) is None):
            return (QualityIssue("QUALITY_EVIDENCE_INVALID"),)
        if (track["id"] != "canonical-track:" + digest(track["track_source"])
                or track["revision_id"] != "sha256:" + digest({
                    "track_source": track["track_source"], "content_hash": evidence.content_hash,
                    "parts": track["parts"], "normalizer": track["normalizer"]})):
            return (QualityIssue("PARENT_CONTENT_REVISION_MISMATCH"),)
        expected_positions = []
        if not track["parts"]:
            return (QualityIssue("QUALITY_EVIDENCE_INVALID"),)
        for p, part in enumerate(track["parts"]):
            if not part["observations"]:
                return (QualityIssue("QUALITY_EVIDENCE_INVALID"),)
            for i, obs in enumerate(part["observations"]):
                xy = obs["position"]
                if (len(xy) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in xy)
                        or not -180 <= xy[0] <= 180 or not -90 <= xy[1] <= 90):
                    return (QualityIssue("QUALITY_EVIDENCE_INVALID"),)
                expected_positions.append(TrackPosition(p, i))
        mappings = evidence.observation_sources
        if (any(not _canonical_source_vertex(m.position) for m in mappings)
                or [m.position for m in mappings] != expected_positions):
            return (QualityIssue("SOURCE_MAPPING_INVALID"),)
        # Every diagnostic, including a non-gap warning, contributes to the
        # source-evidence digest. Check its optional endpoint representations
        # before dataclass-equality provenance checks or any derived identity.
        if any(pos is not None and not _canonical_source_vertex(pos)
               for diag in evidence.diagnostics
               for pos in (diag.previous_position, diag.next_position)):
            return (QualityIssue("SOURCE_DIAGNOSTIC_POSITION_INVALID"),)
        records = [m.source.record_index for m in mappings]
        if (any(type(n) is not int or n < 0 for n in records)
                or any(a >= b for a, b in zip(records, records[1:]))):
            return (QualityIssue("SOURCE_MAPPING_INVALID"),)
        kinds = {m.source.source_kind for m in mappings}
        if len(kinds) != 1 or not kinds <= {"fit", "gpx"}:
            return (QualityIssue("QUALITY_EVIDENCE_UNSUPPORTED"),)
        locations = [(m.source.track_index, m.source.segment_index, m.source.point_index) for m in mappings]
        if "gpx" in kinds and (any(type(n) is not int or n < 0 for loc in locations for n in loc)
                               or any(a >= b for a, b in zip(locations, locations[1:]))):
            return (QualityIssue("SOURCE_MAPPING_INVALID"),)
        record_set = set(records)
        boundaries = set()
        missing_records = []
        for diag in evidence.diagnostics:
            if diag.code not in GAP_CODES:
                continue
            source = diag.source
            if source is None or source.source_kind not in kinds:
                return (QualityIssue("SOURCE_GAP_EVIDENCE_INVALID"),)
            if diag.code in {"POSITION_MISSING", "POSITION_INVALID_SENTINEL"}:
                if (source.source_kind != "fit" or type(source.record_index) is not int
                        or source.record_index < 0 or source.record_index in record_set):
                    return (QualityIssue("SOURCE_GAP_EVIDENCE_INVALID"),)
                missing_records.append(source.record_index)
                insertion = bisect_left(records, source.record_index)
            else:
                if source.source_kind != "gpx":
                    return (QualityIssue("SOURCE_GAP_EVIDENCE_INVALID"),)
                boundary = (source.track_index, source.segment_index, -1)
                insertion = bisect_left(locations, boundary)
            prev = mappings[insertion - 1].position if insertion else None
            following = mappings[insertion].position if insertion < len(mappings) else None
            if (diag.previous_position, diag.next_position) != (prev, following):
                return (QualityIssue("SOURCE_GAP_EVIDENCE_INVALID"),)
            if prev is not None and following is not None:
                if following.part_index != prev.part_index + 1:
                    return (QualityIssue("SOURCE_GAP_EVIDENCE_INVALID"),)
                boundaries.add(prev.part_index)
        if boundaries != set(range(len(track["parts"]) - 1)):
            return (QualityIssue("SOURCE_GAP_EVIDENCE_MISSING"),)
        accounted = records + missing_records
        if sorted(accounted) != list(range(len(accounted))):
            return (QualityIssue("SOURCE_MAPPING_INVALID"),)
        evidence_digest(evidence)  # fail closed on any non-finite serialized value
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return (QualityIssue("QUALITY_EVIDENCE_INVALID"),)
    return ()
