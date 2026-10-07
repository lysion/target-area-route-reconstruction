#!/usr/bin/env python3
"""Run semantic validation for Milestone 1 fixtures.

This runner is intentionally separate from JSON Schema validation.

Layer A (scripts/validate_schema_fixtures.py) proves structural/schema
conformance. This runner implements Layer B checks that standard JSON Schema
cannot reliably express, including:

- polygon topology validity and ring closure;
- CanonicalTrack positive-length assessability;
- TargetSegment positive length and ordered lineage;
- TrackPosition bounds against a parent CanonicalTrack;
- TargetSegment geometry regeneration from parent-track lineage;
- exact cross-object revision references;
- spatial-reference consistency;
- linked SpatialAssessment/TargetSegment consistency;
- relation consistency for complete linked scenarios without unresolved target-relevant uncertainty.

The runner consumes semantic expectations already present in
tests/fixtures/manifest.json and linked object bundles declared in
tests/fixtures/semantic-scenarios.json.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from shapely.geometry import LineString, box, shape
from shapely.validation import explain_validity
from strict_json import load_json as strict_load_json
from jsonschema import Draft202012Validator, FormatChecker
from validate_schema_fixtures import build_registry, schema_documents
from ordered_spatial_oracle import (
    POLICY, covered_intervals, observed_facts, position_from_dict,
    positions_match,
)


class RunnerError(RuntimeError):
    """Raised when repository/manifest state prevents trustworthy validation."""


def issue(code: str, detail: str) -> str:
    """Stable machine-readable identity followed by diagnostic prose."""
    return f"{code}: {detail}"


def issue_code(error: str) -> str:
    return error.split(":", 1)[0]


@dataclass(frozen=True)
class LocalSemanticResult:
    path: Path
    expected_valid: bool | None
    actual_valid: bool
    errors: tuple[str, ...]
    expected_assessable: bool | None
    actual_assessable: bool | None
    expected_issue_code: str | None

    @property
    def semantic_expectation_matched(self) -> bool:
        return (
            self.expected_valid is None
            or (
                self.expected_valid == self.actual_valid
                and (
                    self.expected_valid
                    or self.expected_issue_code in {issue_code(error) for error in self.errors}
                )
            )
        )

    @property
    def assessability_expectation_matched(self) -> bool:
        return (
            self.expected_assessable is None
            or self.expected_assessable == self.actual_assessable
        )

    @property
    def matched(self) -> bool:
        return (
            self.semantic_expectation_matched
            and self.assessability_expectation_matched
        )


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    expected_valid: bool
    actual_valid: bool
    errors: tuple[str, ...]
    expected_issue_code: str | None

    @property
    def matched(self) -> bool:
        return self.expected_valid == self.actual_valid and (
            self.expected_valid
            or self.expected_issue_code in {issue_code(error) for error in self.errors}
        )


def load_json(path: Path) -> Any:
    try:
        return strict_load_json(path)
    except FileNotFoundError as exc:
        raise RunnerError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerError(
            f"invalid JSON: {path}:{exc.lineno}:{exc.colno}: {exc.msg}"
        ) from exc
    except ValueError as exc:
        raise RunnerError(f"invalid JSON: {path}: {exc}") from exc


def resolve_under(root: Path, raw_path: str, *, label: str) -> Path:
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise RunnerError(
            f"{label} path escapes fixture root: {raw_path!r}"
        ) from exc
    return candidate


def position_key(position: dict[str, Any]) -> tuple[int, int, float]:
    return (
        int(position["part_index"]),
        int(position["observation_index"]),
        float(position["fraction_to_next"]),
    )


def track_position_ordered(
    start: dict[str, Any],
    end: dict[str, Any],
    *,
    allow_equal: bool,
) -> bool:
    left = position_key(start)
    right = position_key(end)
    return left <= right if allow_equal else left < right


def validate_activity(_: dict[str, Any]) -> list[str]:
    return []


def validate_track_source(_: dict[str, Any]) -> list[str]:
    return []


def canonical_track_assessable(track: dict[str, Any]) -> bool:
    for part in track.get("parts", []):
        observations = part.get("observations", [])
        if len(observations) < 2:
            continue
        coordinates = [item["position"] for item in observations]
        if LineString(coordinates).length > 0:
            return True
    return False


def validate_canonical_track(_: dict[str, Any]) -> list[str]:
    # Structural observation/continuity requirements are already Layer A.
    # A schema-valid singleton or all-coincident track remains legitimate
    # canonical evidence; assessability is an independent semantic result.
    return []


def iter_polygon_rings(geometry: dict[str, Any]) -> Iterable[list[list[float]]]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])

    if geometry_type == "Polygon":
        yield from coordinates
    elif geometry_type == "MultiPolygon":
        for polygon in coordinates:
            yield from polygon


def validate_target_area(area: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    geometry_data = area["geometry"]

    for ring_index, ring in enumerate(iter_polygon_rings(geometry_data)):
        if not ring or ring[0] != ring[-1]:
            errors.append(issue("TARGET_AREA_RING_UNCLOSED", f"polygon ring {ring_index} is not explicitly closed"))

    try:
        geometry = shape(geometry_data)
    except Exception as exc:  # Shapely raises several geometry-specific types.
        errors.append(issue("TARGET_AREA_GEOMETRY_INVALID", f"geometry construction failed: {exc}"))
        return errors

    if geometry.is_empty:
        errors.append(issue("TARGET_AREA_GEOMETRY_INVALID", "TargetArea geometry is empty"))

    if geometry.area <= 0:
        errors.append(issue("TARGET_AREA_GEOMETRY_INVALID", "TargetArea geometry has no positive area"))

    if not geometry.is_valid:
        errors.append(issue("TARGET_AREA_TOPOLOGY_INVALID", "TargetArea topology is invalid: " + explain_validity(geometry)))

    return errors


def validate_spatial_assessment(assessment: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for index, uncertainty in enumerate(
        assessment.get("coverage_uncertainties", [])
    ):
        affected = uncertainty["affected_track_range"]
        if not track_position_ordered(
            affected["start"], affected["end"], allow_equal=True
        ):
            errors.append(issue("COVERAGE_UNCERTAINTY_RANGE_REVERSED", f"coverage_uncertainties[{index}] track range is reversed"))

    return errors


def validate_target_segment(segment: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    start = segment["start_position"]
    end = segment["end_position"]

    if start["part_index"] != end["part_index"]:
        errors.append(issue("TARGET_SEGMENT_CROSSES_PART", "TargetSegment endpoints must belong to one continuity part"))
    elif not track_position_ordered(start, end, allow_equal=False):
        errors.append(issue("TARGET_SEGMENT_ORDER_INVALID", "TargetSegment start_position must precede end_position"))

    try:
        geometry = shape(segment["geometry"])
    except Exception as exc:
        errors.append(issue("TARGET_SEGMENT_GEOMETRY_INVALID", f"TargetSegment geometry construction failed: {exc}"))
        return errors

    if geometry.is_empty or geometry.length <= 0:
        errors.append(issue("TARGET_SEGMENT_ZERO_LENGTH", "TargetSegment geometry must have positive length"))

    return errors


LOCAL_VALIDATORS: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    "activity.schema.json": validate_activity,
    "track-source.schema.json": validate_track_source,
    "canonical-track.schema.json": validate_canonical_track,
    "target-area.schema.json": validate_target_area,
    "spatial-assessment.schema.json": validate_spatial_assessment,
    "target-segment.schema.json": validate_target_segment,
}


def load_fixture_manifest(
    fixtures_root: Path,
    manifest_path: Path,
) -> list[dict[str, Any]]:
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise RunnerError("fixture manifest root must be an object")
    if manifest.get("schema_version") != "0.1.0":
        raise RunnerError(
            "fixture manifest schema_version must be exactly '0.1.0'"
        )

    entries = manifest.get("fixtures")
    if not isinstance(entries, list):
        raise RunnerError("fixture manifest 'fixtures' must be an array")

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise RunnerError(
                f"fixture manifest entry {index} must be an object"
            )
        if "path" not in entry or "schema" not in entry:
            raise RunnerError(
                f"fixture manifest entry {index} must contain path and schema"
            )

        semantic_expected = entry.get("expect_semantic_valid")
        if semantic_expected is not None and not isinstance(
            semantic_expected, bool
        ):
            raise RunnerError(
                f"{entry['path']}: expect_semantic_valid must be boolean"
            )

        assessable_expected = entry.get("expect_assessable")
        if assessable_expected is not None and not isinstance(
            assessable_expected, bool
        ):
            raise RunnerError(
                f"{entry['path']}: expect_assessable must be boolean"
            )

        if (
            semantic_expected is not None
            or assessable_expected is not None
        ):
            expected_schema = entry.get("expect_schema_valid")
            if expected_schema is not True:
                raise RunnerError(
                    f"{entry['path']}: semantic expectations require "
                    "expect_schema_valid=true"
                )

        issue_expectation = entry.get("expect_semantic_issue_code")
        if semantic_expected is False:
            if not isinstance(issue_expectation, str) or not issue_expectation:
                raise RunnerError(f"{entry['path']}: expected-invalid semantic fixture requires expect_semantic_issue_code")
        elif issue_expectation is not None:
            raise RunnerError(f"{entry['path']}: semantic issue code requires expect_semantic_valid=false")

        resolve_under(
            fixtures_root, entry["path"], label="fixture"
        )

    return entries


def schema_basename_from_manifest_entry(
    fixture_path: Path,
    raw_schema: str,
) -> str:
    return (fixture_path.parent / raw_schema).resolve().name


def run_local_semantic_checks(
    fixtures_root: Path,
    entries: list[dict[str, Any]],
) -> list[LocalSemanticResult]:
    results: list[LocalSemanticResult] = []

    for entry in entries:
        expected_valid = entry.get("expect_semantic_valid")
        expected_assessable = entry.get("expect_assessable")

        if expected_valid is None and expected_assessable is None:
            continue

        fixture_path = resolve_under(
            fixtures_root, entry["path"], label="fixture"
        )
        document = load_json(fixture_path)

        schema_name = schema_basename_from_manifest_entry(
            fixture_path, entry["schema"]
        )
        validator = LOCAL_VALIDATORS.get(schema_name)
        if validator is None:
            raise RunnerError(
                f"{entry['path']}: no semantic validator registered for "
                f"{schema_name}"
            )

        errors = tuple(validator(document))
        actual_valid = not errors

        actual_assessable: bool | None = None
        if expected_assessable is not None:
            if schema_name != "canonical-track.schema.json":
                raise RunnerError(
                    f"{entry['path']}: expect_assessable is only valid for "
                    "CanonicalTrack fixtures"
                )
            actual_assessable = canonical_track_assessable(document)

        results.append(
            LocalSemanticResult(
                path=fixture_path,
                expected_valid=expected_valid,
                actual_valid=actual_valid,
                errors=errors,
                expected_assessable=expected_assessable,
                actual_assessable=actual_assessable,
                expected_issue_code=entry.get("expect_semantic_issue_code"),
            )
        )

    return results


def exact_revision_ref(document: dict[str, Any]) -> dict[str, str]:
    return {
        "id": document["id"],
        "revision_id": document["revision_id"],
    }


def validate_track_position_against_parent(
    track: dict[str, Any],
    position: dict[str, Any],
    *,
    label: str,
) -> list[str]:
    errors: list[str] = []
    part_index = position["part_index"]
    observation_index = position["observation_index"]
    fraction = position["fraction_to_next"]

    parts = track["parts"]
    if part_index >= len(parts):
        return [
            issue("TRACK_POSITION_OUT_OF_BOUNDS", f"{label}: part_index {part_index} is out of bounds for {len(parts)} part(s)")
        ]

    observations = parts[part_index]["observations"]
    if observation_index >= len(observations):
        return [
            issue("TRACK_POSITION_OUT_OF_BOUNDS", f"{label}: observation_index {observation_index} is out of bounds for part {part_index} with {len(observations)} observation(s)")
        ]

    if fraction > 0 and observation_index + 1 >= len(observations):
        errors.append(issue("TRACK_POSITION_OUT_OF_BOUNDS", f"{label}: non-zero fraction_to_next requires a next observation"))

    return errors


def interpolate_track_position(
    track: dict[str, Any],
    position: dict[str, Any],
) -> tuple[float, float]:
    part = track["parts"][position["part_index"]]["observations"]
    index = position["observation_index"]
    fraction = float(position["fraction_to_next"])
    left = part[index]["position"]

    if fraction == 0:
        return float(left[0]), float(left[1])

    right = part[index + 1]["position"]
    return (
        float(left[0]) + fraction * (float(right[0]) - float(left[0])),
        float(left[1]) + fraction * (float(right[1]) - float(left[1])),
    )


def reconstruct_segment_coordinates(
    track: dict[str, Any],
    start: dict[str, Any],
    end: dict[str, Any],
) -> list[tuple[float, float]]:
    if start["part_index"] != end["part_index"]:
        raise RunnerError(
            "cannot reconstruct one TargetSegment across continuity parts"
        )

    part_index = start["part_index"]
    observations = track["parts"][part_index]["observations"]
    start_index = start["observation_index"]
    end_index = end["observation_index"]

    coordinates: list[tuple[float, float]] = [
        interpolate_track_position(track, start)
    ]

    if start_index == end_index:
        coordinates.append(interpolate_track_position(track, end))
        return coordinates

    for index in range(start_index + 1, end_index + 1):
        position = observations[index]["position"]
        coordinates.append((float(position[0]), float(position[1])))

    if end["fraction_to_next"] > 0:
        coordinates.append(interpolate_track_position(track, end))

    return coordinates


def validate_segment_against_parent(
    segment: dict[str, Any],
    track: dict[str, Any],
    area_geometry: Any,
) -> list[str]:
    errors = validate_target_segment(segment)
    if errors:
        return errors

    start = segment["start_position"]
    end = segment["end_position"]

    errors.extend(
        validate_track_position_against_parent(
            track, start, label="start_position"
        )
    )
    errors.extend(
        validate_track_position_against_parent(
            track, end, label="end_position"
        )
    )
    if errors:
        return errors

    reconstructed_coordinates = reconstruct_segment_coordinates(
        track, start, end
    )
    expected_line = LineString(reconstructed_coordinates)
    actual_line = shape(segment["geometry"])

    # Vertex sequence is the domain lineage, including repeated observations.
    # Hausdorff distance and total length lose traversal order and multiplicity.
    actual_coordinates = list(actual_line.coords)
    if len(actual_coordinates) != len(reconstructed_coordinates) or any(
        not POLICY.coordinates_close(actual, expected, local_length=expected_line.length)
        for actual, expected in zip(actual_coordinates, reconstructed_coordinates)
    ):
        errors.append(issue("TARGET_SEGMENT_LINEAGE_MISMATCH", "TargetSegment geometry differs from ordered parent-track regeneration"))

    return errors


def validate_linked_scenario(
    *,
    activity: dict[str, Any],
    track_source: dict[str, Any],
    canonical_track: dict[str, Any],
    target_area: dict[str, Any],
    spatial_assessment: dict[str, Any],
    target_segments: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []

    # Local semantic validity is required for every linked object.
    for label, document, validator in (
        ("activity", activity, validate_activity),
        ("track_source", track_source, validate_track_source),
        ("canonical_track", canonical_track, validate_canonical_track),
        ("target_area", target_area, validate_target_area),
        (
            "spatial_assessment",
            spatial_assessment,
            validate_spatial_assessment,
        ),
    ):
        for error in validator(document):
            errors.append(issue(issue_code(error), f"{label}: {error.split(': ', 1)[-1]}"))

    if not canonical_track_assessable(canonical_track):
        errors.append(issue("TRACK_NOT_ASSESSABLE", "canonical_track: linked assessment requires positive-length assessable route geometry"))

    if track_source["activity"] != {"id": activity["id"]}:
        errors.append(issue("SOURCE_ACTIVITY_MISMATCH", "track_source.activity does not reference the linked Activity"))

    if canonical_track["track_source"] != exact_revision_ref(track_source):
        errors.append(issue("TRACK_SOURCE_REVISION_MISMATCH", "canonical_track.track_source does not reference the exact linked TrackSource revision"))

    if spatial_assessment["canonical_track"] != exact_revision_ref(
        canonical_track
    ):
        errors.append(issue("ASSESSMENT_TRACK_REVISION_MISMATCH", "spatial_assessment.canonical_track does not reference the exact linked CanonicalTrack revision"))

    if spatial_assessment["target_area"] != exact_revision_ref(target_area):
        errors.append(issue("ASSESSMENT_AREA_REVISION_MISMATCH", "spatial_assessment.target_area does not reference the exact linked TargetArea revision"))

    if canonical_track["spatial_reference"] != target_area["spatial_reference"]:
        errors.append(issue("SPATIAL_REFERENCE_MISMATCH", "CanonicalTrack and TargetArea spatial references do not match"))

    for index, uncertainty in enumerate(
        spatial_assessment.get("coverage_uncertainties", [])
    ):
        affected = uncertainty["affected_track_range"]
        for endpoint_name in ("start", "end"):
            for error in validate_track_position_against_parent(
                canonical_track,
                affected[endpoint_name],
                label=(
                    f"coverage_uncertainties[{index}].affected_track_range."
                    f"{endpoint_name}"
                ),
            ):
                errors.append(error)

    area_geometry = shape(target_area["geometry"])

    # Evidence is assessed before the submitted relation. An uncertainty may
    # leave further coverage unknown, but cannot erase an established partial.
    facts = observed_facts(canonical_track, area_geometry)
    complete = spatial_assessment["coverage_completeness"] == "complete"
    if facts.inside and facts.outside:
        required_relation = "partial"
    elif complete:
        required_relation = "inside" if facts.inside else "outside"
    elif facts.inside:
        # Without an independently bounded quality corridor, only a TargetArea
        # covering every canonical CRS84 position proves an unobserved path
        # cannot leave. Ordinary inside+incomplete needs a later quality result.
        required_relation = "inside" if area_geometry.covers(box(-180, -90, 180, 90)) else "unknown"
    else:
        required_relation = "unknown"
    if spatial_assessment["relation"] != required_relation:
        errors.append(issue("ASSESSMENT_RELATION_CONTRADICTS_EVIDENCE", f"observed evidence requires {required_relation!r}, got {spatial_assessment['relation']!r}"))

    sorted_segments = sorted(target_segments, key=lambda item: item["ordinal"])
    expected_ordinals = list(range(len(sorted_segments)))
    actual_ordinals = [item["ordinal"] for item in sorted_segments]
    if actual_ordinals != expected_ordinals:
        errors.append(issue("TARGET_SEGMENT_ORDER_INVALID", "TargetSegment ordinals must be contiguous from zero within the linked SpatialAssessment"))

    expected_refs = [
        exact_revision_ref(segment) for segment in sorted_segments
    ]
    if spatial_assessment["target_segment_refs"] != expected_refs:
        errors.append(issue("TARGET_SEGMENT_REFERENCE_MISMATCH", "spatial_assessment.target_segment_refs do not exactly match the linked TargetSegment revisions in ordinal order"))

    for previous, current in zip(sorted_segments, sorted_segments[1:]):
        if not track_position_ordered(
            previous["end_position"],
            current["start_position"],
            allow_equal=False,
        ):
            errors.append(issue("TARGET_SEGMENT_ORDER_INVALID", "TargetSegments are not strictly ordered and non-overlapping by parent CanonicalTrack position"))
            break

    for index, segment in enumerate(sorted_segments):
        prefix = f"target_segments[{index}]"

        if segment["spatial_assessment"] != exact_revision_ref(
            spatial_assessment
        ):
            errors.append(issue("SEGMENT_ASSESSMENT_REVISION_MISMATCH", f"{prefix}.spatial_assessment does not reference the exact linked SpatialAssessment revision"))

        if segment["canonical_track"] != exact_revision_ref(canonical_track):
            errors.append(issue("SEGMENT_TRACK_REVISION_MISMATCH", f"{prefix}.canonical_track does not reference the exact linked CanonicalTrack revision"))

        if segment["spatial_reference"] != canonical_track["spatial_reference"]:
            errors.append(issue("SPATIAL_REFERENCE_MISMATCH", f"{prefix}.spatial_reference does not match CanonicalTrack"))

        for error in validate_segment_against_parent(
            segment, canonical_track, area_geometry
        ):
            errors.append(issue(issue_code(error), f"{prefix}: {error.split(': ', 1)[-1]}"))

    # All reliable observed covered portions are known even if an uncertainty
    # can hide more coverage. Compare ordered parameter intervals one by one.
    expected = covered_intervals(canonical_track, area_geometry)
    if len(expected) != len(sorted_segments) or any(
        not positions_match(canonical_track, position_from_dict(segment["start_position"]), interval.start)
        or not positions_match(canonical_track, position_from_dict(segment["end_position"]), interval.end)
        for segment, interval in zip(sorted_segments, expected)
        if validate_target_segment(segment) == []
        and not validate_track_position_against_parent(canonical_track, segment["start_position"], label="start_position")
        and not validate_track_position_against_parent(canonical_track, segment["end_position"], label="end_position")
    ):
        errors.append(issue("TARGET_COVERAGE_NOT_EXHAUSTIVE", "TargetSegments do not equal maximal observed covered intervals in parent-track order"))

    return errors


def load_scenario_manifest(
    fixtures_root: Path,
    scenario_manifest_path: Path,
) -> list[dict[str, Any]]:
    manifest = load_json(scenario_manifest_path)
    if not isinstance(manifest, dict):
        raise RunnerError("semantic scenario manifest root must be an object")
    if manifest.get("schema_version") != "0.1.0":
        raise RunnerError(
            "semantic scenario manifest schema_version must be exactly '0.1.0'"
        )

    scenarios = manifest.get("scenarios")
    if not isinstance(scenarios, list):
        raise RunnerError(
            "semantic scenario manifest 'scenarios' must be an array"
        )

    seen: set[str] = set()
    required = (
        "name",
        "expect_semantic_valid",
        "activity",
        "track_source",
        "canonical_track",
        "target_area",
        "spatial_assessment",
        "target_segments",
    )

    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            raise RunnerError(f"semantic scenario {index} must be an object")
        missing = [key for key in required if key not in scenario]
        if missing:
            raise RunnerError(
                f"semantic scenario {index} missing keys: {', '.join(missing)}"
            )

        name = scenario["name"]
        if not isinstance(name, str) or not name:
            raise RunnerError(f"semantic scenario {index} has invalid name")
        if name in seen:
            raise RunnerError(f"duplicate semantic scenario name: {name}")
        seen.add(name)

        if not isinstance(scenario["expect_semantic_valid"], bool):
            raise RunnerError(
                f"semantic scenario {name}: expect_semantic_valid must be boolean"
            )
        expected_issue_code = scenario.get("expect_semantic_issue_code")
        if scenario["expect_semantic_valid"] is False:
            if not isinstance(expected_issue_code, str) or not expected_issue_code:
                raise RunnerError(f"semantic scenario {name}: expected-invalid scenario requires expect_semantic_issue_code")
        elif expected_issue_code is not None:
            raise RunnerError(f"semantic scenario {name}: valid scenario must not specify expect_semantic_issue_code")

        for key in (
            "activity",
            "track_source",
            "canonical_track",
            "target_area",
            "spatial_assessment",
        ):
            if not isinstance(scenario[key], str) or not scenario[key]:
                raise RunnerError(
                    f"semantic scenario {name}: {key} must be a non-empty path"
                )
            resolve_under(
                fixtures_root, scenario[key], label=f"scenario {name}"
            )

        segments = scenario["target_segments"]
        if not isinstance(segments, list):
            raise RunnerError(
                f"semantic scenario {name}: target_segments must be an array"
            )
        for path in segments:
            if not isinstance(path, str) or not path:
                raise RunnerError(
                    f"semantic scenario {name}: invalid target segment path"
                )
            resolve_under(
                fixtures_root, path, label=f"scenario {name}"
            )

    return scenarios


def run_scenarios(
    fixtures_root: Path,
    scenarios: list[dict[str, Any]],
) -> list[ScenarioResult]:
    results: list[ScenarioResult] = []

    for scenario in scenarios:
        def read(key: str) -> dict[str, Any]:
            return load_json(
                resolve_under(
                    fixtures_root,
                    scenario[key],
                    label=f"scenario {scenario['name']}",
                )
            )

        target_segments = [
            load_json(
                resolve_under(
                    fixtures_root,
                    path,
                    label=f"scenario {scenario['name']}",
                )
            )
            for path in scenario["target_segments"]
        ]

        errors = tuple(
            validate_linked_scenario(
                activity=read("activity"),
                track_source=read("track_source"),
                canonical_track=read("canonical_track"),
                target_area=read("target_area"),
                spatial_assessment=read("spatial_assessment"),
                target_segments=target_segments,
            )
        )

        results.append(
            ScenarioResult(
                name=scenario["name"],
                expected_valid=scenario["expect_semantic_valid"],
                actual_valid=not errors,
                errors=errors,
                expected_issue_code=scenario.get("expect_semantic_issue_code"),
            )
        )

    return results


def render_local(
    result: LocalSemanticResult,
    repo_root: Path,
    *,
    verbose: bool,
) -> None:
    rel = result.path.relative_to(repo_root)
    status = "PASS" if result.matched else "FAIL"

    details: list[str] = []
    if result.expected_valid is not None:
        details.append(
            "semantic expected="
            + ("valid" if result.expected_valid else "invalid")
            + " actual="
            + ("valid" if result.actual_valid else "invalid")
        )
    if result.expected_assessable is not None:
        details.append(
            "assessable expected="
            + str(result.expected_assessable).lower()
            + " actual="
            + str(result.actual_assessable).lower()
        )

    print(f"{status:4} {rel}  " + "; ".join(details))

    if (verbose or not result.matched) and result.errors:
        for error in result.errors:
            print(f"     {error}")


def render_scenario(result: ScenarioResult, *, verbose: bool) -> None:
    status = "PASS" if result.matched else "FAIL"
    expected = "valid" if result.expected_valid else "invalid"
    actual = "valid" if result.actual_valid else "invalid"
    print(
        f"{status:4} scenario:{result.name}  "
        f"expected={expected} actual={actual}"
    )

    if (verbose or not result.matched) and result.errors:
        for error in result.errors:
            print(f"     {error}")


def run(
    repo_root: Path,
    fixture_manifest_path: Path,
    scenario_manifest_path: Path,
    *,
    verbose: bool,
) -> int:
    fixtures_root = fixture_manifest_path.parent

    entries = load_fixture_manifest(fixtures_root, fixture_manifest_path)
    scenarios = load_scenario_manifest(
        fixtures_root, scenario_manifest_path
    )

    # The semantic runner is independently safe to invoke: every object it
    # consumes must be a registered Layer A-valid fixture of the right type.
    repo_schema_dir = repo_root / "schemas"
    documents = schema_documents(repo_schema_dir)
    registry = build_registry(documents)
    registered = {entry["path"]: entry for entry in entries}
    checked: set[tuple[str, str]] = set()

    def require_layer_a(raw_path: str, expected_schema: str) -> None:
        entry = registered.get(raw_path)
        if entry is None:
            raise RunnerError(f"linked semantic component is not registered in fixture manifest: {raw_path}")
        fixture_path = resolve_under(fixtures_root, raw_path, label="linked component")
        schema_path = (fixture_path.parent / entry["schema"]).resolve()
        expected_path = (repo_schema_dir / expected_schema).resolve()
        if schema_path != expected_path or entry.get("expect_schema_valid") is not True:
            raise RunnerError(f"{raw_path}: linked semantic component has wrong schema or is not expected schema-valid")
        key = (raw_path, expected_schema)
        if key in checked:
            return
        validator = Draft202012Validator(documents[schema_path], registry=registry, format_checker=FormatChecker())
        errors = list(validator.iter_errors(load_json(fixture_path)))
        if errors:
            raise RunnerError(f"{raw_path}: linked semantic component fails Layer A: {errors[0].message}")
        checked.add(key)

    for entry in entries:
        if entry.get("expect_semantic_valid") is not None or entry.get("expect_assessable") is not None:
            fixture_path = resolve_under(fixtures_root, entry["path"], label="local semantic component")
            require_layer_a(entry["path"], schema_basename_from_manifest_entry(fixture_path, entry["schema"]))
    for scenario in scenarios:
        for key, name in (
            ("activity", "activity.schema.json"),
            ("track_source", "track-source.schema.json"),
            ("canonical_track", "canonical-track.schema.json"),
            ("target_area", "target-area.schema.json"),
            ("spatial_assessment", "spatial-assessment.schema.json"),
        ):
            require_layer_a(scenario[key], name)
        for segment_path in scenario["target_segments"]:
            require_layer_a(segment_path, "target-segment.schema.json")

    local_results = run_local_semantic_checks(fixtures_root, entries)
    scenario_results = run_scenarios(fixtures_root, scenarios)

    for result in local_results:
        render_local(result, repo_root, verbose=verbose)
    for result in scenario_results:
        render_scenario(result, verbose=verbose)

    local_matched = sum(result.matched for result in local_results)
    scenario_matched = sum(result.matched for result in scenario_results)
    total = len(local_results) + len(scenario_results)
    matched = local_matched + scenario_matched
    failed = total - matched

    semantic_expectations = sum(
        result.expected_valid is not None for result in local_results
    )
    assessability_expectations = sum(
        result.expected_assessable is not None for result in local_results
    )

    print()
    print(
        f"Semantic expectations: {matched}/{total} matched; "
        f"{failed} mismatch(es)."
    )
    print(
        "Local fixture checks: "
        f"semantic={semantic_expectations}, "
        f"assessability={assessability_expectations}; "
        f"linked scenarios={len(scenario_results)}."
    )

    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Milestone 1 semantic fixture expectations independently "
            "of JSON Schema validation."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("tests/fixtures/manifest.json"),
        help="fixture manifest (default: tests/fixtures/manifest.json)",
    )
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=Path("tests/fixtures/semantic-scenarios.json"),
        help=(
            "linked semantic scenario manifest "
            "(default: tests/fixtures/semantic-scenarios.json)"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="show semantic errors for expected-invalid passing cases",
    )
    args = parser.parse_args(argv)

    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent

    fixture_manifest = args.manifest
    if not fixture_manifest.is_absolute():
        fixture_manifest = (repo_root / fixture_manifest).resolve()

    scenario_manifest = args.scenarios
    if not scenario_manifest.is_absolute():
        scenario_manifest = (repo_root / scenario_manifest).resolve()

    try:
        return run(
            repo_root,
            fixture_manifest,
            scenario_manifest,
            verbose=args.verbose,
        )
    except RunnerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
