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
M2D_VERSION = "0.1.0"
IDENTITY_POLICY = "m2d-prereference-seed-v1"


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


def strict_load(text):
    def illegal_constant(value):
        raise ValueError("M2D_NONFINITE_JSON")
    value = json.loads(text, parse_constant=illegal_constant)
    def walk(item):
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("M2D_NONFINITE_JSON")
        if isinstance(item, dict):
            for k, v in item.items():
                walk(v)
        elif isinstance(item, list):
            for v in item:
                walk(v)
    walk(value)
    return value
