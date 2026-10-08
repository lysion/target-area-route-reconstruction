"""M2E GeoJSON projection of verified spatial authority.

GeoJSON is an export, not a second spatial classifier. Features come only
from existing parent evidence or accepted M2D target segments. In particular,
a GPS gap has known endpoints but NEVER a drawable connecting geometry.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from ._m2d_common import canonical_json, position_coordinate, regenerate
from .spatial_verifier import verify_spatial_relation
from .spatial_entities_verifier import verify_spatial_entities


@dataclass(frozen=True)
class GeoJSONIssue:
    code: str
    path: str = ""


@dataclass(frozen=True)
class GeoJSONExportResult:
    outcome: str
    geojson_json: str | None = None
    issues: tuple[GeoJSONIssue, ...] = ()

    def to_json(self) -> str:
        """Structured status does not silently coerce invalid output to empty coverage."""
        return canonical_json({
            "outcome": self.outcome,
            "geojson": self.geojson_json,
            "issues": [{"code": e.code, "path": e.path} for e in self.issues],
        })


def _feature(geometry, properties):
    # Geometry is copied rather than shared with the source TargetArea or
    # detached M2D entity snapshots. Display never mutates spatial authority.
    return {"type": "Feature", "geometry": copy.deepcopy(geometry),
            "properties": copy.deepcopy(properties)}


def _build(*, bundle, proof, evidence, target_area, include_outside):
    parent = {
        "id": proof.authority.canonical_track.id,
        "revision_id": proof.authority.canonical_track.revision_id,
    }
    target_ref = {
        "id": proof.authority.target_area.id,
        "revision_id": proof.authority.target_area.revision_id,
    }
    assessment = bundle.assessment if bundle is not None else None
    assessment_ref = ({"id": assessment["id"], "revision_id": assessment["revision_id"]}
                      if assessment is not None else None)

    features = [
        _feature(target_area["geometry"], {
            "layer": "target_area",
            "target_area": target_ref,
            "spatial_reference": "OGC:CRS84",
        }),
    ]

    # The only accepted geometry for target segments is the exact M2D output.
    # Do not clip or coalesce by geometry, even for duplicate visits.
    if bundle is not None:
        for segment in bundle.segments:
            features.append(_feature(segment["geometry"], {
                "layer": "target_segment",
                "evidence_class": "observed_quality_admitted",
                "ordinal": segment["ordinal"],
                "target_segment": {
                    "id": segment["id"], "revision_id": segment["revision_id"],
                },
                "canonical_track": parent,
                "spatial_assessment": assessment_ref,
                "start_position": segment["start_position"],
                "end_position": segment["end_position"],
            }))

    if include_outside:
        # Outside evidence is an optional diagnostic/context layer. Preserve
        # original parent intervals; never connect even adjacent GIS pieces
        # into a purported reconstructed route.
        for ordinal, span in enumerate(proof.outside_evidence_intervals):
            features.append(_feature(
                regenerate(evidence.canonical_track, span.start, span.end),
                {
                    "layer": "observed_outside",
                    "evidence_class": "observed_quality_admitted",
                    "ordinal": ordinal,
                    "canonical_track": parent,
                    "start_position": {
                        "part_index": span.start.part_index,
                        "observation_index": span.start.observation_index,
                        "fraction_to_next": span.start.fraction_to_next,
                    },
                    "end_position": {
                        "part_index": span.end.part_index,
                        "observation_index": span.end.observation_index,
                        "fraction_to_next": span.end.fraction_to_next,
                    },
                }))

    gaps = []
    for item in proof.gap_relevance:
        gap = item.gap
        gap_description = {
            "gap_index": item.gap_index,
            "kind": gap.kind,
            "causes": list(gap.causes),
            "diagnostic_indices": list(gap.diagnostic_indices),
            "target_coverage_unresolved": item.target_coverage_unresolved,
            "bound_relation": item.bound_relation,
            "start": None if gap.start is None else {
                "part_index": gap.start.part_index,
                "observation_index": gap.start.observation_index,
                "fraction_to_next": gap.start.fraction_to_next,
            },
            "end": None if gap.end is None else {
                "part_index": gap.end.part_index,
                "observation_index": gap.end.observation_index,
                "fraction_to_next": gap.end.fraction_to_next,
            },
        }
        gaps.append(gap_description)
        for side, position in (("start", gap.start), ("end", gap.end)):
            if position is None:
                continue
            points = evidence.canonical_track["parts"][position.part_index]["observations"]
            coordinate = position_coordinate(points, position)
            features.append(_feature(
                {"type": "Point", "coordinates": coordinate},
                {
                    "layer": "gap_endpoint",
                    "evidence_class": "observed_endpoint_only",
                    "side": side,
                    "gap_index": item.gap_index,
                    "gap_kind": gap.kind,
                    "target_coverage_unresolved": item.target_coverage_unresolved,
                    "canonical_track": parent,
                }))

    # RFC 7946 permits foreign FeatureCollection members. These support
    # auditability, without defining new route geometry or core entity fields.
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "export_version": "m2e-geojson-v1",
            "spatial_reference": "OGC:CRS84",
            "canonical_track": parent,
            "target_area": target_ref,
            "spatial_assessment": assessment_ref,
            "assessable": bool(proof.assessable),
            "relation": None if assessment is None else assessment["relation"],
            "coverage_completeness": None if assessment is None else assessment["coverage_completeness"],
            "gaps": gaps,
            "warning": "Unobserved gaps are not route geometry; gap points must never be connected.",
        },
    }


def export_geojson(*, bundle, proof, evidence, quality_projection, quality_policy,
                   target_area, target_reference, include_outside=True):
    """Project verified authority into RFC 7946 FeatureCollection JSON.

    A non-assessable proof still permits target-area and known gap diagnostics,
    explicitly *without* a SpatialAssessment or inferred missing route.
    """
    if type(include_outside) is not bool:
        return GeoJSONExportResult("invalid_input", issues=(
            GeoJSONIssue("M2E_EXPORT_OPTION_INVALID", "include_outside"),))
    try:
        # No features can be produced before the independent M2C authority gate.
        upstream = verify_spatial_relation(
            proof, evidence=evidence, quality_projection=quality_projection,
            quality_policy=quality_policy, target_area=target_area,
            target_reference=target_reference)
        if upstream.outcome != "valid":
            return GeoJSONExportResult("invalid_input", issues=(
                GeoJSONIssue("M2E_SPATIAL_PROOF_INVALID"),))
        entities = verify_spatial_entities(
            bundle, proof=proof, evidence=evidence,
            quality_projection=quality_projection, quality_policy=quality_policy,
            target_area=target_area, target_reference=target_reference)
        if entities.outcome != "valid":
            return GeoJSONExportResult("invalid_input", issues=(
                GeoJSONIssue("M2E_SPATIAL_ENTITIES_INVALID"),
                *(GeoJSONIssue(e.code, e.path) for e in entities.issues),
            ))
        if bool(proof.assessable) != (bundle is not None):
            return GeoJSONExportResult("invalid_input", issues=(
                GeoJSONIssue("M2E_ASSESSABILITY_MISMATCH"),))
    except Exception:
        return GeoJSONExportResult("invalid_input", issues=(
            GeoJSONIssue("M2E_AUTHORITY_CHECK_FAILED"),))
    try:
        collection = _build(bundle=bundle, proof=proof, evidence=evidence,
                            target_area=target_area, include_outside=include_outside)
        return GeoJSONExportResult("produced", canonical_json(collection))
    except Exception:
        # Never downgrade export errors into a valid empty map.
        return GeoJSONExportResult("export_failure", issues=(
            GeoJSONIssue("M2E_EXPORT_FAILURE"),))
