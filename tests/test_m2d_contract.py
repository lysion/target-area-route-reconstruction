"""ADR-0011 pre-release amendment acceptance probes from real M2A/M2B/M2C evidence.

The original mismatch remains permanently documented in PR #6. These tests
require faithful open-ended serialization, not fabricated endpoint positions.
"""

import copy
import sys
import unittest
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from target_area_route_reconstruction import (
    QualityPolicy, ingest_bytes, project_quality, verify_quality,
    prove_spatial_relation, verify_spatial_relation,
)
from target_area_route_reconstruction.quality_models import ParentReference

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests/m2d-contract"
sys.path.insert(0, str(ROOT / "scripts"))
from strict_json import load_json
from validate_schema_fixtures import schema_documents, build_registry
from validate_semantic_fixtures import (
    issue_code, validate_spatial_assessment, validate_track_position_against_parent,
)
from generate_synthetic_source_fixtures import build_fit


class M2DContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schemas = schema_documents(ROOT / "schemas")
        cls.validator = Draft202012Validator(
            schemas[ROOT / "schemas/spatial-assessment.schema.json"],
            registry=build_registry(schemas), format_checker=FormatChecker(),
        )

    def verified(self, raw, kind="gpx"):
        evidence = ingest_bytes(raw, source_kind=kind,
                                track_source={"id": "m2d-contract-source", "revision_id": "r1"})
        self.assertEqual(evidence.outcome, "success")
        before = evidence.to_json()
        policy = QualityPolicy()
        quality = project_quality(evidence, policy=policy)
        self.assertEqual(quality.outcome, "produced", quality.issues)
        check = verify_quality(quality.projection, evidence, policy=policy)
        self.assertEqual(check.outcome, "valid", check.issues)
        target = load_json(FIXTURES / "target-area.json")
        args = dict(evidence=evidence, quality_projection=quality.projection,
                    quality_policy=policy, target_area=target,
                    target_reference=ParentReference(target["id"], target["revision_id"]))
        result = prove_spatial_relation(**args)
        self.assertEqual(result.outcome, "produced", result.issues)
        checked = verify_spatial_relation(result.proof, **args)
        self.assertEqual(checked.outcome, "valid", checked.issues)
        self.assertEqual(result.to_json(), prove_spatial_relation(**args).to_json())
        self.assertEqual(before, evidence.to_json())
        proof = result.proof
        self.assertEqual((proof.assessable, proof.relation, proof.coverage_completeness),
                         (True, "unknown", "incomplete"))
        self.assertEqual(proof.target_coverage_intervals, ())
        self.assertTrue(proof.outside_evidence_intervals)
        self.assertEqual(len(proof.gap_relevance), 1)
        self.assertTrue(proof.gap_relevance[0].target_coverage_unresolved)
        self.assertEqual(proof.gap_relevance[0].gap.kind, "source_gap")
        return evidence, proof

    def candidate(self, proof):
        """Negative schema probe: copy gap endpoints faithfully, even when null."""
        gap = proof.gap_relevance[0].gap
        return {
            "schema_version": "0.1.0", "id": "contract-probe", "revision_id": "r1",
            "canonical_track": asdict(proof.authority.canonical_track),
            "target_area": asdict(proof.authority.target_area),
            "relation": proof.relation, "coverage_completeness": proof.coverage_completeness,
            "coverage_uncertainties": [{
                "affected_track_range": {"start": asdict(gap.start) if gap.start is not None else None,
                                         "end": asdict(gap.end) if gap.end is not None else None},
                "relevance": proof.gap_relevance[0].reason,
                "provenance": {"name": "test-only-M2D-contract-probe", "version": "1",
                               "parameters": {"source_gap": asdict(gap)}},
            }],
            "target_segment_refs": [],
            "algorithm": {"name": "test-only-M2D-contract-probe", "version": "1"},
        }

    def failures(self, candidate):
        return {(tuple(error.absolute_path), error.validator)
                for error in self.validator.iter_errors(candidate)}

    def test_leading_gap_proof_valid_and_exact_start_is_schema_representable(self):
        _, proof = self.verified((FIXTURES / "leading-gap.gpx").read_bytes())
        gap = proof.gap_relevance[0].gap
        self.assertIsNone(gap.start)
        self.assertEqual(asdict(gap.end), {"part_index": 0, "observation_index": 0, "fraction_to_next": 0})
        candidate = self.candidate(proof)
        self.assertEqual(self.failures(candidate), set())
        self.assertEqual(validate_spatial_assessment(candidate), [])

    def test_trailing_gap_proof_valid_and_exact_end_is_schema_representable(self):
        _, proof = self.verified((FIXTURES / "trailing-gap.gpx").read_bytes())
        gap = proof.gap_relevance[0].gap
        self.assertIsNone(gap.end)
        self.assertEqual(asdict(gap.start), {"part_index": 0, "observation_index": 1, "fraction_to_next": 0})
        candidate = self.candidate(proof)
        self.assertEqual(self.failures(candidate), set())
        self.assertEqual(validate_spatial_assessment(candidate), [])

    def test_omitting_unavailable_endpoint_is_also_rejected(self):
        for side, missing in (("leading", "start"), ("trailing", "end")):
            with self.subTest(side=side):
                _, proof = self.verified((FIXTURES / (side + "-gap.gpx")).read_bytes())
                candidate = self.candidate(proof)
                del candidate["coverage_uncertainties"][0]["affected_track_range"][missing]
                self.assertEqual(self.failures(candidate), {
                    (("coverage_uncertainties", 0, "affected_track_range"), "required")})

    def test_bounded_gap_control_keeps_both_real_endpoints_and_passes(self):
        evidence, proof = self.verified((FIXTURES / "bounded-gap-control.gpx").read_bytes())
        gap = proof.gap_relevance[0].gap
        self.assertIsNotNone(gap.start)
        self.assertIsNotNone(gap.end)
        candidate = self.candidate(proof)
        self.assertEqual(self.failures(candidate), set())
        self.assertEqual(validate_spatial_assessment(candidate), [])
        for endpoint in (gap.start, gap.end):
            self.assertEqual(validate_track_position_against_parent(
                evidence.canonical_track, asdict(endpoint), label="control"), [])

    def test_same_point_anchor_is_schema_green_but_changes_gap_endpoint_fact(self):
        # This is explicitly a rejected workaround, NOT an accepted M2D mapping.
        # Layer A and the old local oracle cannot certify exact M2B/M2C gap mapping.
        for side, missing, known in (("leading", "start", "end"), ("trailing", "end", "start")):
            with self.subTest(side=side):
                evidence, proof = self.verified((FIXTURES / (side + "-gap.gpx")).read_bytes())
                candidate = self.candidate(proof)
                affected = candidate["coverage_uncertainties"][0]["affected_track_range"]
                actual = copy.deepcopy(affected)
                affected[missing] = copy.deepcopy(affected[known])
                self.assertEqual(self.failures(candidate), set())
                self.assertEqual(validate_spatial_assessment(candidate), [])
                self.assertEqual(validate_track_position_against_parent(
                    evidence.canonical_track, affected[missing], label="fabricated-anchor"), [])
                self.assertIsNone(actual[missing])
                self.assertNotEqual(affected, actual)
                # Even unchanged provenance cannot turn two equal real positions
                # into the missing endpoint under frozen trackRange semantics.
                self.assertIsNone(candidate["coverage_uncertainties"][0]["provenance"]
                                  ["parameters"]["source_gap"][missing])

    def test_out_of_parent_sentinel_is_not_a_legal_unknown_endpoint(self):
        evidence, proof = self.verified((FIXTURES / "trailing-gap.gpx").read_bytes())
        candidate = self.candidate(proof)
        endpoint = {"part_index": 0, "observation_index": 2, "fraction_to_next": 0}
        candidate["coverage_uncertainties"][0]["affected_track_range"]["end"] = endpoint
        self.assertEqual(self.failures(candidate), set())
        failures = validate_track_position_against_parent(evidence.canonical_track, endpoint, label="sentinel")
        self.assertEqual([issue_code(failure) for failure in failures], ["TRACK_POSITION_OUT_OF_BOUNDS"])

    def test_dropping_uncertainty_does_not_satisfy_incomplete_contract(self):
        _, proof = self.verified((FIXTURES / "leading-gap.gpx").read_bytes())
        candidate = self.candidate(proof)
        candidate["coverage_uncertainties"] = []
        self.assertEqual(self.failures(candidate), {(("coverage_uncertainties",), "minItems")})

    def test_fit_missing_position_has_the_same_contract_blocker(self):
        start = datetime(2026, 10, 8, tzinfo=timezone.utc)
        for side, points, endpoint in (
            ("leading", [None, (1, -2), (1, -1)], "start"),
            ("trailing", [(1, -2), (1, -1), None], "end"),
        ):
            with self.subTest(side=side):
                records = [(start + timedelta(seconds=i), xy[0] if xy else None, xy[1] if xy else None)
                           for i, xy in enumerate(points)]
                _, proof = self.verified(build_fit(records), kind="fit")
                candidate = self.candidate(proof)
                self.assertIsNone(candidate["coverage_uncertainties"][0]["affected_track_range"][endpoint])
                self.assertEqual(self.failures(candidate), set())
                self.assertEqual(validate_spatial_assessment(candidate), [])

    def test_both_null_and_extra_fields_are_not_accepted(self):
        _, proof = self.verified((FIXTURES / "leading-gap.gpx").read_bytes())
        candidate = self.candidate(proof)
        affected = candidate["coverage_uncertainties"][0]["affected_track_range"]
        affected["end"] = None
        self.assertIn((("coverage_uncertainties", 0, "affected_track_range"), "oneOf"), self.failures(candidate))
        self.assertIn("COVERAGE_UNCERTAINTY_RANGE_UNANCHORED",
                      [issue_code(error) for error in validate_spatial_assessment(candidate)])
        affected["end"] = {"part_index": 0, "observation_index": 0, "fraction_to_next": 0}
        affected["invented"] = "not-a-range"
        self.assertIn((("coverage_uncertainties", 0, "affected_track_range"), "additionalProperties"), self.failures(candidate))

    def test_malformed_missing_neighbor_cannot_be_a_sentinel(self):
        _, proof = self.verified((FIXTURES / "trailing-gap.gpx").read_bytes())
        candidate = self.candidate(proof)
        affected = candidate["coverage_uncertainties"][0]["affected_track_range"]
        affected["end"] = {"part_index": -1, "observation_index": 0, "fraction_to_next": 0}
        self.assertTrue(self.failures(candidate))
        affected["end"] = {"part_index": 0, "observation_index": 1, "fraction_to_next": float("nan")}
        self.assertTrue(self.failures(candidate))



if __name__ == "__main__":
    unittest.main()
