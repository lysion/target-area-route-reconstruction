"""M2D production integration and independent-verifier adversarial tests."""

from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from target_area_route_reconstruction import (
    QualityPolicy, ingest_bytes, project_quality, prove_spatial_relation,
    assemble_spatial_entities, verify_spatial_entities,
)
from target_area_route_reconstruction._m2d_common import canonical_json
from target_area_route_reconstruction.spatial_entities_models import SpatialEntityBundle
from test_spatial_relation import arguments, route, rectangle
from test_quality_projection import metric, POLICY, ROOT, ingest_parts
from strict_json import load_json


class M2DEntityTests(unittest.TestCase):
    def build(self, args):
        result = prove_spatial_relation(**args)
        self.assertEqual(result.outcome, "produced", result.issues)
        proof = result.proof
        assembled = assemble_spatial_entities(proof=proof, **args)
        if not proof.assessable:
            self.assertEqual(assembled.outcome, "non_assessable")
            self.assertIsNone(assembled.bundle)
            return proof, assembled
        self.assertEqual(assembled.outcome, "produced", assembled.issues)
        check = verify_spatial_entities(assembled.bundle, proof=proof, **args)
        self.assertEqual(check.outcome, "valid", check.issues)
        self.assertEqual(assembled.to_json(), assemble_spatial_entities(proof=proof, **args).to_json())
        return proof, assembled

    def tamper(self, bundle, *, assessment=None, segments=None):
        return SpatialEntityBundle(
            canonical_json(assessment if assessment is not None else bundle.assessment),
            tuple(canonical_json(s) for s in
                  (segments if segments is not None else bundle.segments)),
        )

    def test_inside_maximal_and_parent_vertices(self):
        args = arguments(route([(0.25, 1), (0.5, 1), (1.5, 1), (1.75, 1)]))
        proof, result = self.build(args)
        self.assertEqual(proof.relation, "inside")
        self.assertEqual(len(result.bundle.segments), 1)
        line = result.bundle.segments[0]
        self.assertEqual(len(line["geometry"]["coordinates"]), 4)
        self.assertEqual(line["ordinal"], 0)
        self.assertEqual(result.bundle.assessment["target_segment_refs"][0]["id"], line["id"])

    def test_partial_fraction_clip_and_no_reclassification(self):
        args = arguments(route([(-1, 1), (3, 1)]))
        proof, result = self.build(args)
        line = result.bundle.segments[0]
        self.assertEqual(line["start_position"]["fraction_to_next"], 0.25)
        self.assertEqual(line["end_position"]["fraction_to_next"], 0.75)
        self.assertEqual(result.bundle.assessment["relation"], "partial")

    def test_outside_and_point_touch_emit_no_segments(self):
        for track in (route([(-2, -1), (-1, -1)]), route([(-1, 1), (1, -1)])):
            with self.subTest(track=track.canonical_track["revision_id"]):
                proof, result = self.build(arguments(track))
                self.assertEqual(proof.relation, "outside")
                self.assertEqual(result.bundle.segments, ())
                self.assertEqual(result.bundle.assessment["target_segment_refs"], [])

    def test_repeated_entries_and_independent_parts(self):
        for args, count in (
            (arguments(route([(-1, 1), (3, 1), (-1, 1), (3, 1)])), 3),
            (arguments(route([(1, 1), (1.5, 1)], [(1, 1), (1.5, 1)])), 2),
        ):
            with self.subTest(count=count):
                _, result = self.build(args)
                self.assertEqual(len(result.bundle.segments), count)
                ids = [s["id"] for s in result.bundle.segments]
                self.assertEqual(len(set(ids)), count)

    def test_hole_and_multipolygon(self):
        hole = rectangle(-2, -2, 2, 2)
        hole["geometry"]["coordinates"].append([[-.5, -.5], [-.5, .5], [.5, .5], [.5, -.5], [-.5, -.5]])
        multi = rectangle()
        multi["geometry"] = {"type":"MultiPolygon","coordinates":[
            rectangle(0, 0, 1, 2)["geometry"]["coordinates"],
            rectangle(2, 0, 3, 2)["geometry"]["coordinates"]]}
        for args in (arguments(route([(-1, 0), (1, 0)]), hole),
                     arguments(route([(-1, 1), (4, 1)]), multi)):
            with self.subTest(area=args["target_area"]["geometry"]["type"]):
                _, result = self.build(args)
                self.assertEqual(len(result.bundle.segments), 2)

    def test_repeated_observation_vertices_are_not_deduplicated(self):
        args = arguments(route([(1, 1), (1, 1), (1.5, 1), (1.5, 1)]))
        _, result = self.build(args)
        line = result.bundle.segments[0]
        self.assertEqual(line["start_position"]["observation_index"], 0)
        self.assertEqual(line["end_position"]["observation_index"], 3)
        self.assertEqual(len(line["geometry"]["coordinates"]), 4)

    def test_partial_incomplete_retains_known_segment(self):
        args = arguments(route([(-1, 1), (3, 1)], [(4, 1), (5, 1)]))
        proof, result = self.build(args)
        self.assertEqual((proof.relation, proof.coverage_completeness), ("partial", "incomplete"))
        self.assertEqual(len(result.bundle.segments), 1)
        self.assertEqual(len(result.bundle.assessment["coverage_uncertainties"]), 1)

    def test_unknown_incomplete_with_and_without_known_segment(self):
        for args, n in (
            (arguments(route([(1, 1), (1.5, 1)], [(1, 1), (1.5, 1)])), 2),
            (arguments(route([(-2, 1), (-1, 1)], [(3, 1), (4, 1)])), 0),
        ):
            with self.subTest(n=n):
                proof, result = self.build(args)
                self.assertEqual(proof.relation, "unknown")
                self.assertEqual(len(result.bundle.segments), n)
                self.assertEqual(result.bundle.assessment["coverage_completeness"], "incomplete")

    def test_leading_trailing_gpx_uncertainty_exact_null(self):
        for side, field in (("leading", "start"), ("trailing", "end")):
            with self.subTest(side=side):
                raw = (ROOT / "tests/m2d-contract" / (side + "-gap.gpx")).read_bytes()
                evidence = ingest_bytes(raw, source_kind="gpx",
                    track_source={"id":"open-source","revision_id":"r1"})
                self.assertEqual(evidence.outcome, "success")
                proof, result = self.build(arguments(evidence, policy=QualityPolicy()))
                self.assertEqual(proof.relation, "unknown")
                affected = result.bundle.assessment["coverage_uncertainties"][0]["affected_track_range"]
                self.assertIsNone(affected[field])
                self.assertIsNotNone(affected["end" if field == "start" else "start"])

    def test_nonassessable_yields_no_entities(self):
        for args in (arguments(route([(1, 1)])),
                     arguments(route([(1, 1), (1, 1)]))):
            _, result = self.build(args)
            self.assertIsNone(result.bundle)

    def test_stale_proof_and_quality_are_rejected(self):
        args = arguments(route([(1, 1), (1.5, 1)]))
        proof, result = self.build(args)
        stale = replace(proof, relation="outside")
        assembled = assemble_spatial_entities(proof=stale, **args)
        self.assertEqual(assembled.outcome, "invalid_input")
        self.assertIsNone(assembled.bundle)
        bad_args = dict(args)
        bad_args["target_reference"] = replace(args["target_reference"], revision_id="wrong")
        self.assertEqual(assemble_spatial_entities(proof=proof, **bad_args).outcome, "invalid_input")

    def test_verifier_rejects_mutated_relation_geometry_and_refs(self):
        args = arguments(route([(-1, 1), (3, 1)]))
        proof, result = self.build(args)
        assessment = result.bundle.assessment
        segs = list(result.bundle.segments)
        changed = copy.deepcopy(assessment)
        changed["relation"] = "inside"
        self.assertEqual(verify_spatial_entities(self.tamper(result.bundle, assessment=changed), proof=proof, **args).outcome, "invalid")
        changed = copy.deepcopy(segs)
        changed[0]["geometry"]["coordinates"].reverse()
        self.assertEqual(verify_spatial_entities(self.tamper(result.bundle, segments=changed), proof=proof, **args).outcome, "invalid")
        changed = copy.deepcopy(assessment)
        changed["target_segment_refs"] = []
        self.assertEqual(verify_spatial_entities(self.tamper(result.bundle, assessment=changed), proof=proof, **args).outcome, "invalid")
        changed = copy.deepcopy(segs)
        changed[0]["spatial_assessment"]["revision_id"] = "fake"
        self.assertEqual(verify_spatial_entities(self.tamper(result.bundle, segments=changed), proof=proof, **args).outcome, "invalid")

    def test_verifier_rejects_missing_and_duplicate_segment(self):
        args = arguments(route([(-1, 1), (3, 1), (-1, 1)]))
        proof, result = self.build(args)
        for segments in ([], list(result.bundle.segments)[:1],
                         list(result.bundle.segments) * 2):
            with self.subTest(segments=len(segments)):
                bad = self.tamper(result.bundle, segments=segments)
                verified = verify_spatial_entities(bad, proof=proof, **args)
                self.assertEqual(verified.outcome, "invalid")

    def test_verifier_rejects_dropped_relevant_uncertainty(self):
        args = arguments(route([(-1, 1), (3, 1)], [(4, 1), (5, 1)]))
        proof, result = self.build(args)
        bad = result.bundle.assessment
        bad["coverage_uncertainties"] = []
        self.assertEqual(verify_spatial_entities(self.tamper(result.bundle, assessment=bad), proof=proof, **args).outcome, "invalid")

    def test_m1_valid_scenario_relation_and_count(self):
        cases = load_json(ROOT / "tests/fixtures/semantic-scenarios.json")["scenarios"]
        count = 0
        for item in cases:
            if not item["expect_semantic_valid"]:
                continue
            with self.subTest(scenario=item["name"]):
                track = load_json(ROOT / "tests/fixtures" / item["canonical_track"])
                area = load_json(ROOT / "tests/fixtures" / item["target_area"])
                evidence = ingest_parts([part["observations"] for part in track["parts"]])
                args = arguments(evidence, area, QualityPolicy(include_domain_bounds=True))
                proof, result = self.build(args)
                expected = load_json(ROOT / "tests/fixtures" / item["spatial_assessment"])
                self.assertEqual((proof.relation, proof.coverage_completeness),
                                 (expected["relation"], expected["coverage_completeness"]))
                self.assertEqual(len(result.bundle.segments), len(item["target_segments"]))
                count += 1
        self.assertEqual(count, 19)

    def test_mutated_producer_coverage_is_rejected_by_independent_verifier(self):
        # Retain one of two covered visits: this is still schema-valid
        # partial relation, but it fails the independent exhaustive oracle.
        args = arguments(route([(-1, 1), (3, 1), (-1, 1)]))
        proof = prove_spatial_relation(**args).proof
        first = proof.target_coverage_intervals[0]
        with patch("target_area_route_reconstruction.spatial_entities._maximal_covered",
                   return_value=((first.start, first.end),)):
            result = assemble_spatial_entities(proof=proof, **args)
        self.assertEqual(result.outcome, "assembly_failure")
        self.assertIn("M2D_ASSEMBLY_VERIFICATION_FAILED", [i.code for i in result.issues])

    def test_ten_real_production_mutations_are_killed(self):
        """Run original positive integration witnesses against mutated package copies.

        A mutant is killed only by a test assertion, never by an import crash.
        """
        import target_area_route_reconstruction.spatial_entities as producer
        import target_area_route_reconstruction._m2d_common as shared
        producer_source = Path(producer.__file__).read_text()
        shared_source = Path(shared.__file__).read_text()
        mutations = [
            ("spatial_entities.py",
             "elif position_key(current_end) == position_key(start):",
             "elif False and position_key(current_end) == position_key(start):",
             "test_inside_maximal_and_parent_vertices"),
            ("spatial_entities.py",
             "    return tuple(output)",
             "    return ((output[0][0], output[-1][1]),) if len(output) > 1 else tuple(output)",
             "test_repeated_entries_and_independent_parts"),
            ("spatial_entities.py",
             "    return tuple(output)",
             "    return tuple(output[:1])",
             "test_repeated_entries_and_independent_parts"),
            ("spatial_entities.py",
             "                output.append((current_start, current_end))",
             "                pass  # mutant drops target coverage",
             "test_inside_maximal_and_parent_vertices"),
            ("spatial_entities.py",
             "    return tuple(output)",
             "    return tuple(output + output)",
             "test_inside_maximal_and_parent_vertices"),
            ("_m2d_common.py",
             "        points.append(list(observations[index][\"position\"]))",
             "        pass  # mutant erases interior parent observations",
             "test_inside_maximal_and_parent_vertices"),
            ("spatial_entities.py",
             '        "relation": proof.relation,',
             '        "relation": "outside",',
             "test_partial_fraction_clip_and_no_reclassification"),
            ("spatial_entities.py",
             '        "coverage_completeness": proof.coverage_completeness,',
             '        "coverage_completeness": "complete",',
             "test_partial_incomplete_retains_known_segment"),
            ("spatial_entities.py",
             "        if not item.target_coverage_unresolved:",
             "        if True or not item.target_coverage_unresolved:",
             "test_partial_incomplete_retains_known_segment"),
            ("spatial_entities.py",
             "    if not proof.assessable:",
             "    if False and not proof.assessable:",
             "test_nonassessable_yields_no_entities"),
        ]
        for filename, old, new, witness in mutations:
            with self.subTest(filename=filename, witness=witness, replacement=new):
                source = shared_source if filename.startswith("_") else producer_source
                self.assertEqual(source.count(old), 1, (filename, old))
                with tempfile.TemporaryDirectory() as directory:
                    package = Path(directory) / "target_area_route_reconstruction"
                    shutil.copytree(Path(producer.__file__).parent, package,
                                    ignore=shutil.ignore_patterns("__pycache__"))
                    (package / filename).write_text(source.replace(old, new))
                    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                           "PYTHONPATH": os.pathsep.join((directory, str(ROOT / "tests")))}
                    run = subprocess.run(
                        [sys.executable, "-m", "unittest",
                         "test_spatial_entities.M2DEntityTests." + witness],
                        env=env, capture_output=True, text=True, timeout=40,
                    )
                    self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                    self.assertIn("AssertionError", run.stderr)
                    self.assertIn("Ran 1 test", run.stderr)


if __name__ == "__main__":
    unittest.main()
