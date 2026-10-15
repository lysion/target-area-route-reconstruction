"""Narrow M2D primitives: strict serialization, schema checks and parent positions.

Geometry regeneration is a *parent-observation* operation, not clipping or
route inference. Both producer and verifier may use these primitives, while
their segment-accounting decisions remain separately implemented.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from functools import lru_cache
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


M2D_NAME = "target-area-route-reconstruction.spatial-assembly"
M2D_VERSION = "0.1.1"
IDENTITY_POLICY = "m2d-prereference-seed-v1"
SNAPSHOT_POLICY = "m2d-canonical-payload-v1"


def canonical_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def position_key(position):
    return (position.part_index, position.observation_index, position.fraction_to_next)


def position_dict(position):
    return asdict(position)


def position_coordinate(observations, position):
    i, fraction = position.observation_index, position.fraction_to_next
    a = observations[i]["position"]
    if fraction == 0:
        return list(a)
    b = observations[i + 1]["position"]
    return [a[k] + fraction * (b[k] - a[k]) for k in range(2)]


def regenerate(track, start, end):
    """Regenerate ordered lineage with all intermediate parent observations.

    Never simplify, round, de-duplicate, or bridge continuity parts.
    """
    if start.part_index != end.part_index or position_key(start) >= position_key(end):
        raise ValueError("M2D_PARENT_RANGE_INVALID")
    observations = track["parts"][start.part_index]["observations"]
    points = [position_coordinate(observations, start)]
    for index in range(start.observation_index + 1, end.observation_index + 1):
        points.append(list(observations[index]["position"]))
    if end.fraction_to_next:
        points.append(position_coordinate(observations, end))
    if len(points) < 2 or all(p == points[0] for p in points[1:]):
        raise ValueError("M2D_SEGMENT_NOT_POSITIVE")
    return {"type": "LineString", "coordinates": points}


@lru_cache(maxsize=1)
def validators():
    # M2D's package-local registry never fetches schemas over the network.
    base = "https://schemas.target-area.invalid/v0.1/"
    registry, docs = Registry(), {}
    for name in ("common", "spatial-assessment", "target-segment"):
        doc = json.loads(files("target_area_route_reconstruction").joinpath(
            "spec", name + ".schema.json").read_text())
        doc["$id"] = base + name + ".schema.json"
        docs[name] = doc
        registry = registry.with_resource(doc["$id"], Resource.from_contents(doc))
    return {
        name: Draft202012Validator(doc, registry=registry, format_checker=FormatChecker())
        for name, doc in docs.items()
    }


def schema_issues(name, instance):
    return tuple((
        "/".join(map(str, err.absolute_path)),
        str(err.validator)
    ) for err in sorted(validators()[name].iter_errors(instance),
                        key=lambda e: (tuple(map(str, e.absolute_path)), str(e.validator))))


# Historical imports retain the same exception class and parse error codes.
from .strict_json import StrictJSONError as BundleJSONError, loads_json


def strict_load(text):
    if type(text) is not str:
        raise BundleJSONError("M2D_BUNDLE_MALFORMED")
    return loads_json(text)


def exact_proof_metadata(proof, quality):
    """Additional type-sensitive provenance check AFTER the mandatory M2C gate.

    Python dataclass equality equates False/0 and 8/8.0. This check does not
    clip, classify or decide any new spatial fact.
    """
    from ._spatial_inputs import algorithm
    if canonical_json(asdict(proof.algorithm)) != canonical_json(asdict(algorithm())):
        return False
    if canonical_json(asdict(proof.authority.quality_algorithm)) != canonical_json(asdict(quality.algorithm)):
        return False
    return all(canonical_json(asdict(item.gap)) == canonical_json(asdict(quality.gaps[item.gap_index]))
               for item in proof.gap_relevance)


def parent_coordinate_scale(track):
    """Compute the invariant full-track coordinate scale once per assembly."""
    return max(abs(value) for part in track["parts"]
               for observation in part["observations"]
               for value in observation["position"])


def geometry_matches_parent(actual, expected, track, *, parent_scale=None):
    """Bounded *semantic* comparison; immutable payload identity is separate.

    Mirror the documented M1 coordinate budget, not its implementation. Vertex
    count/order is exact; no tolerance determines positive length. The M1
    independent oracle and hand-computed witnesses test this shared primitive.
    """
    a, b = actual["coordinates"], expected["coordinates"]
    if actual["type"] != "LineString" or len(a) != len(b):
        return False
    if all(point == a[0] for point in a[1:]):
        return False
    length = math.fsum(math.hypot(y[0] - x[0], y[1] - x[1]) for x, y in zip(b, b[1:]))
    scale = parent_coordinate_scale(track) if parent_scale is None else parent_scale
    return all(abs(x - y) <= min(1e-12, 8 * math.ulp(max(scale, *map(abs, p), *map(abs, q))), length / 4)
               for p, q in zip(a, b) for x, y in zip(p, q))
