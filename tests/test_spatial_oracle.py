"""Adversarial spatial contracts, including the no-edge mutation witness."""

from __future__ import annotations

import sys
import math
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker
from shapely.geometry import LineString, box

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import ordered_spatial_oracle as oracle
import validate_schema_fixtures as layer_a
import validate_semantic_fixtures as layer_b
from strict_json import load_json

CASES = ROOT / "tests" / "adversarial"


class OrderedSpatialOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_json(CASES / "manifest.json")
        cls.scenarios = {entry["name"]: entry for entry in load_json(ROOT / "tests/fixtures/semantic-scenarios.json")["scenarios"]}
        cls.documents = layer_a.schema_documents(ROOT / "schemas")
        cls.registry = layer_a.build_registry(cls.documents)

    def load_case(self, name: str) -> dict:
        scenario = self.scenarios["audit-" + name]
        bundle = {key: load_json(ROOT / "tests/fixtures" / scenario[key]) for key in (
            "activity", "track_source", "canonical_track", "target_area", "spatial_assessment",
        )}
        bundle["target_segments"] = [load_json(ROOT / "tests/fixtures" / path) for path in scenario["target_segments"]]
        return bundle

    def test_adversarial_bundles(self) -> None:
        schemas = {
            "activity": "activity", "track_source": "track-source",
            "canonical_track": "canonical-track", "target_area": "target-area",
            "spatial_assessment": "spatial-assessment", "target_segments": "target-segment",
        }
        for case in self.manifest["cases"]:
            with self.subTest(case=case["name"]):
                bundle = self.load_case(case["name"])
                for key, schema_name in schemas.items():
                    schema = self.documents[ROOT / "schemas" / f"{schema_name}.schema.json"]
                    validator = Draft202012Validator(schema, registry=self.registry, format_checker=FormatChecker())
                    values = bundle[key] if key == "target_segments" else [bundle[key]]
                    for value in values:
                        self.assertEqual(list(validator.iter_errors(value)), [], f"{case['name']} {key}")
                errors = layer_b.validate_linked_scenario(**bundle)
                self.assertEqual(not errors, case["expect_semantic_valid"], errors)
                if not case["expect_semantic_valid"]:
                    self.assertIn(case["expect_semantic_issue_code"], {layer_b.issue_code(error) for error in errors})

    def test_r2_geos_runtime_warning_never_counts_as_oracle_fact(self) -> None:
        # M1's legacy oracle is itself GEOS-backed, not a second numeric
        # implementation. It cannot certify the second independent Codex
        # full-repo P1 attack simply by sharing the engine's wrong result.
        x = 8e-200
        area = box(x, -1, math.nextafter(x, math.inf), 1)
        track = {"parts": [{"observations": [
            {"position": [-9e-200, 0]},
            {"position": [1.8e-199, 0]},
        ]}]}
        with self.assertRaisesRegex(ValueError, "ORACLE_NUMERICAL_FAILURE"):
            oracle.observed_facts(track, area)
        with self.assertRaisesRegex(ValueError, "ORACLE_NUMERICAL_FAILURE"):
            oracle.covered_intervals(track, area)

    def test_all_six_relation_completeness_combinations(self) -> None:
        combinations = {
            (case["relation"], case["coverage_completeness"])
            for name in ("fully-inside", "fully-outside", "partial-crossing",
                         "partial-incomplete-gap", "relevant-gap-unknown")
            for case in [load_json(ROOT / "tests/fixtures/scenarios" / name / "spatial-assessment.json")]
        }
        new = self.load_case("inside_incomplete_world")["spatial_assessment"]
        combinations.add((new["relation"], new["coverage_completeness"]))
        self.assertEqual(combinations, {
            ("inside", "complete"), ("inside", "incomplete"),
            ("partial", "complete"), ("partial", "incomplete"),
            ("outside", "complete"), ("unknown", "incomplete"),
        })

    def test_connecting_continuity_parts_mutation_is_killed(self) -> None:
        bundle = self.load_case("identical_multipart_unknown_incomplete")
        self.assertEqual(layer_b.validate_linked_scenario(**bundle), [])
        original = oracle.observed_edges

        def incorrectly_bridged(track):
            parts = track["parts"]
            for part_index, edge_index, edge in original(track):
                yield part_index, edge_index, edge
                if edge_index == len(parts[part_index]["observations"]) - 2 and part_index + 1 < len(parts):
                    yield part_index, edge_index + 1, LineString((
                        parts[part_index]["observations"][-1]["position"],
                        parts[part_index + 1]["observations"][0]["position"],
                    ))

        with patch.object(oracle, "observed_edges", incorrectly_bridged):
            try:
                issues = layer_b.validate_linked_scenario(**bundle)
            except IndexError:
                # A bridge creates a nonexistent parent edge. Failing closed
                # on that invalid lineage also kills the deliberate mutation.
                return
        self.assertIn("TARGET_COVERAGE_NOT_EXHAUSTIVE", {layer_b.issue_code(issue) for issue in issues})


if __name__ == "__main__":
    unittest.main()
