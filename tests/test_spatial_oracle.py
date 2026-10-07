"""Adversarial spatial contracts, including the no-edge mutation witness."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import ordered_spatial_oracle as oracle
import validate_schema_fixtures as layer_a
import validate_semantic_fixtures as layer_b

CASES = ROOT / "tests" / "adversarial"


class OrderedSpatialOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((CASES / "manifest.json").read_text())
        cls.documents = layer_a.schema_documents(ROOT / "schemas")
        cls.registry = layer_a.build_registry(cls.documents)

    def load_case(self, name: str) -> dict:
        return json.loads((CASES / f"{name}.json").read_text())

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

    def test_all_six_relation_completeness_combinations(self) -> None:
        combinations = {
            (case["relation"], case["coverage_completeness"])
            for name in ("fully-inside", "fully-outside", "partial-crossing",
                         "partial-incomplete-gap", "relevant-gap-unknown")
            for case in [json.loads((ROOT / "tests/fixtures/scenarios" / name / "spatial-assessment.json").read_text())]
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
            issues = layer_b.validate_linked_scenario(**bundle)
        self.assertIn("TARGET_COVERAGE_NOT_EXHAUSTIVE", {layer_b.issue_code(issue) for issue in issues})


if __name__ == "__main__":
    unittest.main()
