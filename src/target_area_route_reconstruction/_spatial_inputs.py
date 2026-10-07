"""Offline frozen-schema validation and the mandatory M2B authority gate."""

import copy
import hashlib
import json
from functools import lru_cache
from importlib.resources import files

import shapely
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from shapely.geometry import shape

from .quality_models import ParentReference
from .quality_verifier import verify_quality
from .spatial_models import SpatialAlgorithm, SpatialAuthority, SpatialFailure, SpatialIssue, SpatialParameters


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def algorithm():
    return SpatialAlgorithm(SpatialParameters(shapely.__version__, shapely.geos_version_string))


@lru_cache(maxsize=1)
def _validators():
    base = "https://schemas.target-area.invalid/v0.1/"
    registry = Registry()
    documents = {}
    for name in ("common", "canonical-track", "target-area"):
        document = json.loads(files("target_area_route_reconstruction").joinpath("spec", name + ".schema.json").read_text())
        document["$id"] = base + name + ".schema.json"
        documents[name] = document
        registry = registry.with_resource(document["$id"], Resource.from_contents(document))
    # All references resolve from this registry; no network retrieval exists.
    return {name: Draft202012Validator(doc, registry=registry, format_checker=FormatChecker())
            for name, doc in documents.items()}


def _schema(name, document):
    errors = sorted(_validators()[name].iter_errors(document),
                    key=lambda e: (tuple(map(str, e.absolute_path)), str(e.validator)))
    if errors:
        prefix = "TARGET_AREA" if name == "target-area" else "CANONICAL_TRACK"
        raise SpatialFailure(prefix + "_SCHEMA_INVALID", issues=[
            SpatialIssue(prefix + "_SCHEMA_INVALID", "/".join(map(str, e.absolute_path)) + ":" + e.validator)
            for e in errors])


def prepare(*, evidence, quality_projection, quality_policy, target_area, target_reference):
    # Gate precedes *all* target topology / track geometry operations.
    verified = verify_quality(quality_projection, evidence, policy=quality_policy)
    if verified.outcome != "valid":
        raise SpatialFailure("QUALITY_AUTHORITY_INVALID", issues=[SpatialIssue("QUALITY_AUTHORITY_INVALID")]
                             + [SpatialIssue(i.code, i.path) for i in verified.issues])
    track = copy.deepcopy(evidence.canonical_track)
    target = copy.deepcopy(target_area)
    try:
        _schema("canonical-track", track)
        _schema("target-area", target)
        target_digest = fingerprint(target)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SpatialFailure("SPATIAL_INPUT_NONFINITE_OR_MALFORMED") from exc
    reference = ParentReference(target["id"], target["revision_id"])
    if not isinstance(target_reference, ParentReference) or reference != target_reference:
        raise SpatialFailure("TARGET_REFERENCE_MISMATCH")
    # GEOS accepts unclosed rings by silently closing them; domain inputs may not.
    polygons = [target["geometry"]["coordinates"]] if target["geometry"]["type"] == "Polygon" else target["geometry"]["coordinates"]
    for polygon in polygons:
        for ring in polygon:
            if ring[0] != ring[-1]:
                raise SpatialFailure("TARGET_RING_NOT_CLOSED")
    geometry = shape(target["geometry"])
    if geometry.is_empty or not geometry.is_valid:
        raise SpatialFailure("TARGET_TOPOLOGY_INVALID")
    authority = SpatialAuthority(ParentReference(track["id"], track["revision_id"]), reference, target_digest,
                                 quality_projection.evidence_digest, fingerprint(quality_projection.to_dict()),
                                 quality_projection.algorithm)
    return track, geometry, authority, verified
