#!/usr/bin/env python3
"""Validate the Milestone 1 edge-case coverage map.

This runner proves that every frozen EC-01..EC-29 case has an explicit
Milestone 1 representation and that all referenced fixtures, linked semantic
scenarios, and non-file contract cases actually exist in their source
manifests.

It does not execute later-milestone non-file cases; it validates that their
test intent and ownership are explicit rather than silently omitted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from strict_json import load_json as strict_load_json


class CoverageError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    try:
        return strict_load_json(path)
    except FileNotFoundError as exc:
        raise CoverageError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CoverageError(
            f"invalid JSON: {path}:{exc.lineno}:{exc.colno}: {exc.msg}"
        ) from exc
    except ValueError as exc:
        raise CoverageError(f"invalid JSON: {path}: {exc}") from exc


def fail(message: str) -> None:
    raise CoverageError(message)


def validate(repo_root: Path) -> None:
    coverage = load_json(repo_root / "tests/edge-case-coverage.json")
    fixture_manifest = load_json(repo_root / "tests/fixtures/manifest.json")
    scenario_manifest = load_json(
        repo_root / "tests/fixtures/semantic-scenarios.json"
    )
    nonfile_manifest = load_json(repo_root / "tests/nonfile-contract-cases.json")

    if coverage.get("schema_version") != "0.1.0":
        fail("edge-case coverage schema_version must be '0.1.0'")

    cases = coverage.get("edge_cases")
    if not isinstance(cases, list):
        fail("edge-case coverage 'edge_cases' must be an array")

    expected_ids = [f"EC-{index:02d}" for index in range(1, 30)]
    actual_ids = [item.get("edge_case") for item in cases]
    if actual_ids != expected_ids:
        fail(
            "edge-case coverage must contain EC-01..EC-29 exactly once "
            "and in order"
        )

    fixture_paths = {
        "tests/fixtures/" + item["path"]
        for item in fixture_manifest.get("fixtures", [])
    }
    scenarios = scenario_manifest.get("scenarios")
    nonfile_cases = nonfile_manifest.get("cases")
    if not isinstance(scenarios, list) or not isinstance(nonfile_cases, list):
        fail("scenario and non-file manifests must contain arrays")
    scenario_by_name = {item["name"]: item for item in scenarios}
    scenario_names = set(scenario_by_name)
    if len(scenario_names) != len(scenarios):
        fail("duplicate linked semantic scenario name")
    nonfile_ids: set[str] = set()
    nonfile_required = (
        "edge_case", "assertion", "execution_milestone",
        "future_test_shape", "reason_not_entity_fixture",
    )
    for index, item in enumerate(nonfile_cases):
        if not isinstance(item, dict):
            fail(f"non-file case {index} must be an object")
        for key in nonfile_required:
            value = item.get(key)
            if not isinstance(value, str) or not value.strip():
                fail(f"non-file case {index} requires non-empty {key}")
        if not item["execution_milestone"].startswith("Milestone "):
            fail(f"non-file case {index} requires a Milestone execution owner")
        case_id = item["edge_case"]
        if case_id in nonfile_ids or case_id not in expected_ids:
            fail(f"duplicate or unknown non-file edge case: {case_id}")
        nonfile_ids.add(case_id)

    fixture_by_path = {
        "tests/fixtures/" + item["path"]: item
        for item in fixture_manifest.get("fixtures", [])
    }

    valid_types = {
        "fixture",
        "linked_semantic_scenario",
        "non_file_contract_case",
    }

    for item in cases:
        edge_case = item["edge_case"]
        reps = item.get("representations")
        if not isinstance(reps, list) or not reps:
            fail(f"{edge_case}: at least one representation is required")

        for rep in reps:
            if not isinstance(rep, dict):
                fail(f"{edge_case}: representation must be an object")
            rep_type = rep.get("type")
            ref = rep.get("ref")
            if rep_type not in valid_types:
                fail(f"{edge_case}: unsupported representation type {rep_type!r}")
            if not isinstance(ref, str) or not ref:
                fail(f"{edge_case}: representation ref must be non-empty")

            if rep_type == "fixture":
                if ref not in fixture_paths:
                    fail(f"{edge_case}: fixture ref not registered: {ref}")
            elif rep_type == "linked_semantic_scenario":
                if ref not in scenario_names:
                    fail(f"{edge_case}: semantic scenario not found: {ref}")
            elif rep_type == "non_file_contract_case":
                prefix = "tests/nonfile-contract-cases.json#"
                if not ref.startswith(prefix):
                    fail(
                        f"{edge_case}: non-file ref must use {prefix}<EC-ID>"
                    )
                anchor = ref[len(prefix):]
                if anchor != edge_case:
                    fail(
                        f"{edge_case}: non-file ref anchor {anchor!r} "
                        "does not match edge-case ID"
                    )
                if anchor not in nonfile_ids:
                    fail(f"{edge_case}: non-file contract case not found")

    negatives = coverage.get("negative_cross_object_cases")
    if not isinstance(negatives, list) or not negatives:
        fail("negative_cross_object_cases must be a non-empty array")

    negative_names: set[str] = set()
    for item in negatives:
        name = item.get("name")
        layer = item.get("layer")
        ref = item.get("ref")
        if not isinstance(name, str) or not name:
            fail("negative cross-object case has invalid name")
        if name in negative_names:
            fail(f"duplicate negative cross-object case: {name}")
        negative_names.add(name)

        if layer == "semantic":
            prefix = "tests/fixtures/semantic-scenarios.json#"
            if not isinstance(ref, str) or not ref.startswith(prefix):
                fail(f"{name}: semantic negative ref must use scenario anchor")
            scenario_name = ref[len(prefix):]
            if scenario_name not in scenario_names:
                fail(f"{name}: semantic scenario not found: {scenario_name}")
            if scenario_by_name[scenario_name].get("expect_semantic_valid") is not False:
                fail(f"{name}: semantic negative ref points to a valid scenario")
            if not scenario_by_name[scenario_name].get("expect_semantic_issue_code"):
                fail(f"{name}: semantic negative ref has no expected issue code")
        elif layer == "schema":
            if ref not in fixture_paths:
                fail(f"{name}: schema fixture not registered: {ref}")
            if fixture_by_path[ref].get("expect_schema_valid") is not False:
                fail(f"{name}: schema negative ref points to a valid fixture")
            if not fixture_by_path[ref].get("expect_schema_error"):
                fail(f"{name}: schema negative ref has no expected failure selector")
        else:
            fail(f"{name}: unsupported negative validation layer {layer!r}")

    # Scenario edge-case annotations must only reference frozen IDs.
    expected_set = set(expected_ids)
    for scenario in scenario_manifest.get("scenarios", []):
        for edge_case in scenario.get("edge_cases", []):
            if edge_case not in expected_set:
                fail(
                    f"scenario {scenario.get('name')}: unknown edge case "
                    f"{edge_case}"
                )

    print(
        "Edge-case coverage: 29/29 frozen cases mapped; "
        f"{len(negatives)} negative cross-object cases registered."
    )
    print(
        "Representation sources: "
        f"{len(fixture_paths)} schema fixtures, "
        f"{len(scenario_names)} linked semantic scenarios, "
        f"{len(nonfile_ids)} explicit non-file contract cases."
    )


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    try:
        validate(repo_root)
    except CoverageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
