"""Mutation tests: the contract gates must reject a wrong *reason* or missing contract."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from strict_json import load_json


class ContractGateMutations(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("scripts", "schemas", "tests"):
            shutil.copytree(ROOT / name, self.root / name, ignore=shutil.ignore_patterns("__pycache__"))

    def document(self, relative: str) -> dict:
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def write(self, relative: str, document: dict) -> None:
        (self.root / relative).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    def gate(self, name: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.root / "scripts" / f"validate_{name}.py")],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            timeout=30,
        )

    def test_schema_negative_cannot_fail_for_wrong_reason(self) -> None:
        path = "tests/fixtures/target-segment/invalid-fraction-one.json"
        segment = self.document(path)
        segment["start_position"]["fraction_to_next"] = 0
        segment["schema_version"] = "WRONG"
        self.write(path, segment)
        result = self.gate("schema_fixtures")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_semantic_negative_cannot_fail_for_wrong_reason(self) -> None:
        base = "tests/fixtures/scenarios/partial-crossing/"
        segment = self.document(base + "target-segment.json")
        segment["canonical_track"]["revision_id"] = "wrong"
        self.write(base + "target-segment-invalid-lineage.json", segment)
        result = self.gate("semantic_fixtures")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_linked_component_must_pass_layer_a(self) -> None:
        base = "tests/fixtures/scenarios/partial-crossing/"
        activity = self.document(base + "activity.json")
        activity["source_native_id"] = "forbidden"
        self.write(base + "unregistered-activity.json", activity)
        path = "tests/fixtures/semantic-scenarios.json"
        manifest = self.document(path)
        manifest["scenarios"][0]["activity"] = "scenarios/partial-crossing/unregistered-activity.json"
        self.write(path, manifest)
        result = self.gate("semantic_fixtures")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_nonfile_case_requires_actual_contract(self) -> None:
        path = "tests/nonfile-contract-cases.json"
        manifest = self.document(path)
        manifest["cases"][0].pop("future_test_shape")
        self.write(path, manifest)
        result = self.gate("edge_case_coverage")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_negative_registration_cannot_point_to_positive(self) -> None:
        path = "tests/edge-case-coverage.json"
        manifest = self.document(path)
        manifest["negative_cross_object_cases"][0]["ref"] = (
            "tests/fixtures/semantic-scenarios.json#fully-inside"
        )
        self.write(path, manifest)
        result = self.gate("edge_case_coverage")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_json_loaders_reject_nonfinite_literals_and_overflow(self) -> None:
        path = self.root / "nonfinite.json"
        for value in ("NaN", "Infinity", "-Infinity", "1e9999"):
            with self.subTest(value=value):
                path.write_text('{"number": ' + value + "}", encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_json(path)


if __name__ == "__main__":
    unittest.main()
