"""Production M2C contracts, manual claims and eight source-code mutations."""

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

from target_area_route_reconstruction import (
    QualityPolicy, TrackPosition, ingest_bytes, project_quality,
    prove_spatial_relation, verify_spatial_relation,
)
from target_area_route_reconstruction import spatial, _spatial_geometry
from target_area_route_reconstruction.quality_models import ParentInterval, ParentReference
from target_area_route_reconstruction.spatial_models import SpatialRelationProof, SpatialFailure
from test_quality_projection import ingest_parts, metric, interval, DISABLED, POLICY, ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from strict_json import load_json
from generate_synthetic_source_fixtures import build_fit


def rectangle(x0=0, y0=0, x1=2, y1=2):
    return {"schema_version": "0.1.0", "id": "target", "revision_id": "r1", "spatial_reference": "OGC:CRS84",
            "geometry": {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]},
            "definition_provenance": {"description": "Synthetic M2C test target"}}


def route(*parts):
    return ingest_parts([[{"position": xy} for xy in part] for part in parts])


def arguments(evidence, area=None, policy=DISABLED):
    area = rectangle() if area is None else area
    result = project_quality(evidence, policy=policy)
    assert result.outcome == "produced", result.issues
    return dict(evidence=evidence, quality_projection=result.projection, quality_policy=policy,
                target_area=area, target_reference=ParentReference(area["id"], area["revision_id"]))


class SpatialRelationTests(unittest.TestCase):
    def checked(self, args):
        result = prove_spatial_relation(**args)
        self.assertEqual(result.outcome, "produced", result.issues)
        verification = verify_spatial_relation(result.proof, **args)
        self.assertEqual(verification.outcome, "valid", verification.issues)
        return result.proof

    def rejected(self, proof, args, code):
        result = verify_spatial_relation(proof, **args)
        self.assertEqual(result.outcome, "invalid")
        self.assertIn(code, [i.code for i in result.issues], result)

    def input_rejected(self, args, code):
        result = prove_spatial_relation(**args)
        self.assertEqual(result.outcome, "invalid_input", result)
        self.assertIsNone(result.proof)
        self.assertIn(code, [i.code for i in result.issues], result)

    def test_inside_continuous(self):
        args = arguments(route([(0.25, 1), (1, 1), (1.75, 1)]))
        proof = self.checked(args)
        self.assertEqual((proof.assessable, proof.relation, proof.coverage_completeness), (True, "inside", "complete"))
        self.assertEqual(proof.target_coverage_intervals, (interval(0, 0, 1), interval(0, 1, 2)))
        self.assertEqual(proof.outside_evidence_intervals, ())

    def test_outside_continuous(self):
        proof = self.checked(arguments(route([(-2, -1), (-1, -1)])))
        self.assertEqual((proof.relation, proof.coverage_completeness), ("outside", "complete"))
        self.assertEqual(proof.target_coverage_intervals, ())
        self.assertEqual(proof.outside_evidence_intervals, (interval(0, 0, 1),))

    def test_crossing_fraction_lineage(self):
        args = arguments(route([(-1, 1), (3, 1)]))
        before = args["evidence"].to_json()
        proof = self.checked(args)
        self.assertEqual(proof.relation, "partial")
        self.assertEqual(proof.target_coverage_intervals, (ParentInterval(TrackPosition(0, 0, .25), TrackPosition(0, 0, .75)),))
        self.assertEqual(proof.outside_evidence_intervals,
                         (ParentInterval(TrackPosition(0, 0), TrackPosition(0, 0, .25)),
                          ParentInterval(TrackPosition(0, 0, .75), TrackPosition(0, 1))))
        self.assertEqual(args["evidence"].to_json(), before)

    def test_repeated_entry_and_direction_preserved(self):
        proof = self.checked(arguments(route([(-1, 1), (3, 1), (-1, 1), (3, 1)])))
        self.assertEqual(proof.relation, "partial")
        self.assertEqual([p.start.observation_index for p in proof.target_coverage_intervals], [0, 1, 2])
        self.assertEqual(len(proof.outside_evidence_intervals), 6)

    def test_identical_geometry_parts_retain_occurrences(self):
        proof = self.checked(arguments(route([(1, 1), (1.5, 1)], [(1, 1), (1.5, 1)])))
        self.assertEqual([r.start.part_index for r in proof.target_coverage_intervals], [0, 1])
        self.assertEqual(proof.relation, "unknown")

    def test_starts_inside_then_exits(self):
        proof = self.checked(arguments(route([(1, 1), (3, 1)])))
        self.assertEqual(proof.relation, "partial")
        self.assertEqual(proof.target_coverage_intervals[0].end, TrackPosition(0, 0, .5))

    def test_point_touch_witness(self):
        proof = self.checked(arguments(route([(-1, 1), (1, -1)])))
        self.assertEqual((proof.assessable, proof.relation, proof.coverage_completeness), (True, "outside", "complete"))
        self.assertEqual(proof.target_coverage_intervals, ())

    def test_boundary_overlap_and_boundary_only(self):
        partial = self.checked(arguments(route([(-1, 0), (3, 0)])))
        inside = self.checked(arguments(route([(0, 0), (2, 0)])))
        self.assertEqual(partial.relation, "partial")
        self.assertEqual(inside.relation, "inside")
        self.assertEqual(inside.target_coverage_intervals, (interval(0, 0, 1),))

    def test_polygon_hole(self):
        area = rectangle(-2, -2, 2, 2)
        area["geometry"]["coordinates"].append([[-.5, -.5], [-.5, .5], [.5, .5], [.5, -.5], [-.5, -.5]])
        proof = self.checked(arguments(route([(-1, 0), (1, 0)]), area))
        self.assertEqual(proof.relation, "partial")
        self.assertEqual(len(proof.target_coverage_intervals), 2)
        self.assertEqual(proof.outside_evidence_intervals, (ParentInterval(TrackPosition(0, 0, .25), TrackPosition(0, 0, .75)),))

    def test_multipolygon(self):
        area = rectangle()
        area["geometry"] = {"type": "MultiPolygon", "coordinates": [rectangle(0, 0, 1, 2)["geometry"]["coordinates"],
                                                                     rectangle(2, 0, 3, 2)["geometry"]["coordinates"]]}
        proof = self.checked(arguments(route([(-1, 1), (4, 1)]), area))
        self.assertEqual(proof.relation, "partial")
        self.assertEqual(len(proof.target_coverage_intervals), 2)

    def test_source_gap_chord_never_becomes_geometry(self):
        proof = self.checked(arguments(route([(-2, 1), (-1, 1)], [(3, 1), (4, 1)])))
        self.assertEqual(proof.target_coverage_intervals, ())
        self.assertEqual((proof.relation, proof.coverage_completeness), ("unknown", "incomplete"))
        self.assertEqual(proof.gap_relevance[0].reason, "SOURCE_GAP_TARGET_UNRESOLVED")

    def test_quality_gap_witness(self):
        proof = self.checked(arguments(metric("gps-jump"), rectangle(.2, -1, .8, 1), POLICY))
        self.assertEqual(proof.target_coverage_intervals, ())
        self.assertEqual(proof.outside_evidence_intervals, (interval(0, 0, 1), interval(0, 2, 3)))
        self.assertEqual((proof.relation, proof.coverage_completeness), ("unknown", "incomplete"))
        self.assertEqual(proof.gap_relevance[0].reason, "QUALITY_GAP_TARGET_UNRESOLVED")

    def test_partial_with_gap_witness(self):
        proof = self.checked(arguments(route([(-1, 1), (3, 1)], [(4, 1), (5, 1)])))
        self.assertEqual((proof.relation, proof.coverage_completeness), ("partial", "incomplete"))

    def test_endpoint_inside_fallacy(self):
        proof = self.checked(arguments(route([(.1, 1), (.2, 1)], [(1.8, 1), (1.9, 1)])))
        self.assertEqual(proof.outside_evidence_intervals, ())
        self.assertEqual((proof.relation, proof.coverage_completeness), ("unknown", "incomplete"))

    def test_domain_bound_local_witness(self):
        args = arguments(route([(-2, 1), (-1, 1)], [(3, 1), (4, 1)]), policy=QualityPolicy(include_domain_bounds=True))
        proof = self.checked(args)
        self.assertEqual(proof.gap_relevance[0].bound_relation, "intersects")
        self.assertEqual((proof.relation, proof.coverage_completeness), ("unknown", "incomplete"))

    def test_world_bound_proves_inside_but_incomplete(self):
        args = arguments(route([(0, 0), (1, 0)], [(2, 0), (3, 0)]), rectangle(-180, -90, 180, 90), QualityPolicy(include_domain_bounds=True))
        proof = self.checked(args)
        self.assertEqual((proof.relation, proof.coverage_completeness), ("inside", "incomplete"))
        self.assertEqual(proof.gap_relevance[0].bound_relation, "covered")
        self.assertTrue(proof.gap_relevance[0].target_coverage_unresolved)

    def test_absent_world_constraint_is_not_silently_created(self):
        proof = self.checked(arguments(route([(0, 0), (1, 0)], [(2, 0), (3, 0)]), rectangle(-180, -90, 180, 90)))
        self.assertEqual(proof.relation, "unknown")
        self.assertEqual(proof.gap_relevance[0].bound_relation, "unavailable")

    def test_leading_and_trailing_fit_gaps(self):
        now = datetime(2026, 10, 7, tzinfo=timezone.utc)
        for points, leading in (([None, (1, .1), (1, .2)], True), ([(1, .1), (1, .2), None], False)):
            with self.subTest(leading=leading):
                records = [(now + timedelta(seconds=i), xy[0] if xy else None, xy[1] if xy else None) for i, xy in enumerate(points)]
                e = ingest_bytes(build_fit(records), source_kind="fit", track_source={"id": "fit", "revision_id": "r1"})
                proof = self.checked(arguments(e, policy=QualityPolicy(include_domain_bounds=True)))
                self.assertEqual((proof.relation, proof.coverage_completeness), ("unknown", "incomplete"))
                gap = proof.gap_relevance[0].gap
                self.assertIsNone(gap.start if leading else gap.end)
                self.assertEqual(gap.diagnostic_indices, (0,))

    def test_singleton_nonassessable_witness(self):
        proof = self.checked(arguments(route([(1, 1)])))
        self.assertFalse(proof.assessable)
        self.assertIsNone(proof.relation)
        self.assertIsNone(proof.coverage_completeness)
        self.assertEqual(proof.reason, "NO_POSITIVE_LENGTH_USABLE_GEOMETRY")
        self.assertEqual(proof.target_coverage_intervals, ())

    def test_zero_length_nonassessable_and_stationary_evidence(self):
        proof = self.checked(arguments(route([(1, 1), (1, 1), (1, 1)])))
        self.assertFalse(proof.assessable)
        self.assertIsNone(proof.relation)
        self.assertEqual([e.interval for e in proof.stationary_evidence], [interval(0, 0, 1), interval(0, 1, 2)])
        self.assertTrue(all(e.target_covered for e in proof.stationary_evidence))

    def test_all_excluded_nonassessable(self):
        proof = self.checked(arguments(metric("gps-jump"), policy=QualityPolicy(max_implied_speed_mps=1)))
        self.assertFalse(proof.assessable)
        self.assertEqual(len(proof.gap_relevance), 3)
        self.assertIsNone(proof.relation)

    def test_repeated_coordinates_support_future_maximality(self):
        proof = self.checked(arguments(route([(1, 1), (1, 1), (1.5, 1), (1.5, 1)])))
        self.assertEqual(proof.target_coverage_intervals, (interval(0, 1, 2),))
        self.assertEqual([s.interval for s in proof.stationary_evidence], [interval(0, 0, 1), interval(0, 2, 3)])
        self.assertEqual(proof.relation, "inside")

    def test_tiny_positive_evidence_not_erased(self):
        for size in (5e-13, 1e-200):
            with self.subTest(size=size):
                proof = self.checked(arguments(route([(0, 0), (size, 0)]), rectangle(-1, -1, 1, 1)))
                self.assertTrue(proof.assessable)
                self.assertEqual(proof.relation, "inside")
                self.assertEqual(proof.target_coverage_intervals, (interval(0, 0, 1),))

    def test_fraction_one_canonicalizes_to_original_observation(self):
        proof = self.checked(arguments(route([(-1, 1), (0, 1), (1, 1)])))
        self.assertEqual(proof.target_coverage_intervals, (interval(0, 1, 2),))
        self.assertEqual(proof.outside_evidence_intervals, (interval(0, 0, 1),))

    def test_all_valid_m1_scenarios_through_production_api(self):
        root = ROOT / "tests/fixtures"
        cases = load_json(root / "semantic-scenarios.json")["scenarios"]
        count = 0
        for case in cases:
            if not case["expect_semantic_valid"]:
                continue
            with self.subTest(case=case["name"]):
                track = load_json(root / case["canonical_track"])
                area = load_json(root / case["target_area"])
                expected = load_json(root / case["spatial_assessment"])
                evidence = ingest_parts([part["observations"] for part in track["parts"]])
                proof = self.checked(arguments(evidence, area, QualityPolicy(include_domain_bounds=True)))
                self.assertEqual((proof.relation, proof.coverage_completeness), (expected["relation"], expected["coverage_completeness"]))
                count += 1
        self.assertEqual(count, 19)

    def test_quality_gate_precedes_target_geometry(self):
        args = arguments(route([(1, 1), (1.5, 1)]))
        args["quality_projection"] = replace(args["quality_projection"], evidence_digest="stale")
        with patch("target_area_route_reconstruction._spatial_inputs.shape", side_effect=AssertionError("geometry before authority")):
            self.input_rejected(args, "QUALITY_AUTHORITY_INVALID")
        args = arguments(route([(1, 1), (1.5, 1)], [(1, 1), (1.5, 1)]),
                         policy=QualityPolicy(include_domain_bounds=True))
        q = args["quality_projection"]
        unsupported = replace(q.gap_constraints[0], method="endpoint-buffer")
        self.input_rejected({**args, "quality_projection": replace(q, gap_constraints=(unsupported,))},
                            "GAP_CONSTRAINT_UNSUPPORTED")

    def test_wrong_parent_and_missing_edge_cannot_enter_geometry(self):
        args = arguments(route([(1, 1), (1.5, 1)]))
        for q in (replace(args["quality_projection"], canonical_track=ParentReference("wrong", "r1")),
                  replace(args["quality_projection"], usable_intervals=())):
            with self.subTest(q=q):
                self.input_rejected({**args, "quality_projection": q}, "QUALITY_AUTHORITY_INVALID")

    def test_erased_gap_and_restored_exclusion_are_rejected(self):
        args = arguments(metric("gps-jump"), policy=POLICY)
        q = args["quality_projection"]
        for invalid in (replace(q, gaps=()), replace(q, usable_intervals=(interval(0, 0, 3),))):
            self.input_rejected({**args, "quality_projection": invalid}, "QUALITY_AUTHORITY_INVALID")

    def test_same_coordinates_different_evidence_fail(self):
        args = arguments(route([(1, 1), (1.5, 1)]))
        e = args["evidence"]
        changed = replace(e, diagnostics=e.diagnostics + (__import__("target_area_route_reconstruction").Diagnostic("DIFFERENT_EVIDENCE"),))
        # Source-independent fabricated diagnostics are rejected at the M2A
        # identity boundary, before a derived digest mismatch is evaluated.
        self.input_rejected({**args, "evidence": changed}, "SOURCE_DIAGNOSTIC_POSITION_INVALID")

    def test_wrong_target_revision(self):
        args = arguments(route([(1, 1), (1.5, 1)]))
        self.input_rejected({**args, "target_reference": ParentReference("target", "stale")}, "TARGET_REFERENCE_MISMATCH")

    def test_invalid_target_schema_crs_numbers_and_topology(self):
        args = arguments(route([(1, 1), (1.5, 1)]))
        for key, value in (("spatial_reference", "EPSG:4326"), ("revision_id", ""), ("geometry", {"type": "Point", "coordinates": [1, 1]})):
            area = {**args["target_area"], key: value}
            self.input_rejected({**args, "target_area": area}, "TARGET_AREA_SCHEMA_INVALID")
        for number in (float("nan"), float("inf")):
            area = copy.deepcopy(args["target_area"])
            area["extensions"] = {"test:value": number}
            self.input_rejected({**args, "target_area": area}, "SPATIAL_INPUT_NONFINITE_OR_MALFORMED")
        area = rectangle()
        area["geometry"]["coordinates"][0] = [[0,0],[2,2],[0,2],[2,0],[0,0]]
        self.input_rejected({**args, "target_area": area}, "TARGET_TOPOLOGY_INVALID")
        area = rectangle()
        area["geometry"]["coordinates"][0][-1] = [0, 1]
        self.input_rejected({**args, "target_area": area}, "TARGET_RING_NOT_CLOSED")

    def test_no_schema_repair_or_input_mutation(self):
        args = arguments(route([(-1, 1), (3, 1)]))
        before = copy.deepcopy(args)
        self.checked(args)
        self.assertEqual(args, before)

    def test_determinism_and_no_entity_identity(self):
        args = arguments(route([(-1, 1), (3, 1)]))
        proof = self.checked(args)
        self.assertEqual(proof.to_json(), self.checked(args).to_json())
        self.assertFalse({"id", "revision_id", "target_segment_refs", "ordinal", "geometry"} & proof.to_dict().keys())
        with self.assertRaises(FrozenInstanceError):
            proof.relation = "outside"
        snapshot = proof.to_dict()
        snapshot["target_coverage_intervals"].clear()
        self.assertTrue(proof.target_coverage_intervals)

    def test_manual_proof_and_independent_verifier(self):
        args = arguments(route([(1, 1), (1.5, 1)]))
        produced = self.checked(args)
        manual = SpatialRelationProof(produced.authority, produced.algorithm, True, "inside", "complete", None,
                                      (interval(0, 0, 1),), (), (), ())
        with patch.object(spatial, "prove_spatial_relation", side_effect=AssertionError("producer called")):
            self.assertEqual(verify_spatial_relation(manual, **args).outcome, "valid")

    def test_verifier_parent_target_quality_and_parameters(self):
        args = arguments(route([(1, 1), (1.5, 1)]))
        proof = self.checked(args)
        for authority in (replace(proof.authority, canonical_track=ParentReference("wrong", "r1")),
                          replace(proof.authority, target_area=ParentReference("target", "stale")),
                          replace(proof.authority, quality_projection_digest="wrong")):
            self.rejected(replace(proof, authority=authority), args, "SPATIAL_AUTHORITY_MISMATCH")
        self.rejected(replace(proof, algorithm=replace(proof.algorithm, version="future")), args, "SPATIAL_ALGORITHM_MISMATCH")
        area = copy.deepcopy(args["target_area"]); area["definition_provenance"]["description"] = "new snapshot"
        self.rejected(proof, {**args, "target_area": area}, "SPATIAL_AUTHORITY_MISMATCH")

    def test_verifier_omitted_shortened_duplicate_and_reordered_fragments(self):
        args = arguments(route([(-1, 1), (3, 1), (-1, 1)]))
        proof = self.checked(args)
        self.rejected(replace(proof, target_coverage_intervals=()), args, "TARGET_COVERAGE_PROOF_MISMATCH")
        shortened = replace(proof.target_coverage_intervals[0], end=TrackPosition(0, 0, .5))
        self.rejected(replace(proof, target_coverage_intervals=(shortened,) + proof.target_coverage_intervals[1:]), args, "SPATIAL_EDGE_COVERAGE_MISMATCH")
        self.rejected(replace(proof, target_coverage_intervals=proof.target_coverage_intervals[::-1]), args, "SPATIAL_RANGE_ORDER_OR_OVERLAP")
        self.rejected(replace(proof, target_coverage_intervals=proof.target_coverage_intervals * 2), args, "SPATIAL_EDGE_COVERAGE_MISMATCH")

    def test_verifier_invalid_fraction_cross_part_and_excluded_edge(self):
        args = arguments(metric("gps-jump"), rectangle(-2, -2, 2, 2), POLICY)
        proof = self.checked(args)
        for piece, code in ((interval(0, 1, 2), "SPATIAL_EDGE_NOT_ADMITTED_POSITIVE"),
                            (ParentInterval(TrackPosition(0, 0, float("nan")), TrackPosition(0, 1)), "SPATIAL_POSITION_INVALID"),
                            (interval(0, 0, 3), "SPATIAL_FRAGMENT_CROSSES_EDGE")):
            self.rejected(replace(proof, target_coverage_intervals=(piece,)), args, code)
        args = arguments(route([(1, 1), (1.5, 1)], [(1, 1), (1.5, 1)]))
        proof = self.checked(args)
        self.rejected(replace(proof, target_coverage_intervals=(ParentInterval(TrackPosition(0, 0), TrackPosition(1, 1)),)), args, "SPATIAL_RANGE_INVALID")

    def test_verifier_impossible_relations_and_nonassessability(self):
        args = arguments(route([(-1, 1), (3, 1)]))
        proof = self.checked(args)
        for relation in ("inside", "outside", "unknown"):
            self.rejected(replace(proof, relation=relation), args, "RELATION_PROOF_MISMATCH")
        self.rejected(replace(proof, assessable=False), args, "ASSESSABILITY_PROOF_MISMATCH")
        args = arguments(route([(1, 1)])); proof = self.checked(args)
        self.rejected(replace(proof, relation="unknown", coverage_completeness="incomplete"), args, "NONASSESSABLE_ASSERTION_INVALID")
        for points in ([(1, 1), (1.5, 1)], [(-2, 1), (-1, 1)]):
            args = arguments(route(points))
            proof = self.checked(args)
            self.rejected(replace(proof, relation="partial"), args, "RELATION_PROOF_MISMATCH")

    def test_verifier_complete_with_gap_or_missing_gap_fails(self):
        args = arguments(route([(-2, 1), (-1, 1)], [(3, 1), (4, 1)]))
        proof = self.checked(args)
        self.rejected(replace(proof, coverage_completeness="complete"), args, "COMPLETENESS_PROOF_MISMATCH")
        self.rejected(replace(proof, relation="outside"), args, "RELATION_PROOF_MISMATCH")
        self.rejected(replace(proof, gap_relevance=()), args, "GAP_RELEVANCE_MISSING_OR_EXTRA")
        fake = replace(proof.gap_relevance[0], bound_relation="disjoint", target_coverage_unresolved=False)
        self.rejected(replace(proof, gap_relevance=(fake,)), args, "GAP_RELEVANCE_PROOF_MISMATCH")

    def test_verifier_rejects_boolean_indices_and_stationary_flags(self):
        args = arguments(route([(1, 1), (1, 1)]))
        proof = self.checked(args)
        stationary = proof.stationary_evidence[0]
        for changed in (
            replace(stationary, target_covered=1),
            replace(stationary, interval=ParentInterval(TrackPosition(False, 0), TrackPosition(0, 1))),
        ):
            self.rejected(replace(proof, stationary_evidence=(changed,)), args, "STATIONARY_EVIDENCE_MISMATCH")
        args = arguments(route([(1, 1), (1.5, 1)], [(1, 1), (1.5, 1)]),
                         policy=QualityPolicy(include_domain_bounds=True))
        proof = self.checked(args)
        changed = replace(proof.gap_relevance[0], constraint_index=False)
        self.rejected(replace(proof, gap_relevance=(changed,)), args, "GAP_RELEVANCE_PROOF_MISMATCH")

    def test_schema_package_copies_match_frozen_sources(self):
        for name in ("common", "canonical-track", "target-area"):
            self.assertEqual(files("target_area_route_reconstruction").joinpath("spec", name + ".schema.json").read_bytes(),
                             (ROOT / "schemas" / (name + ".schema.json")).read_bytes())

    def test_unrepresentable_fraction_fails_without_snapping(self):
        with self.assertRaises(SpatialFailure) as raised:
            _spatial_geometry._fraction((1.0, 0.1), (0.0, 0.0), (1.0, 0.0), 1)
        self.assertEqual(raised.exception.issues[0].code, "SPATIAL_FRACTION_UNREPRESENTABLE")

    def test_declared_planar_longitude_semantics(self):
        # Explicit longitude-linear model: no hidden geodesic/dateline wrapping.
        proof = self.checked(arguments(route([(179, 1), (-179, 1)]), rectangle(-1, 0, 1, 2)))
        self.assertEqual(proof.relation, "partial")
        self.assertEqual(proof.algorithm.parameters.interpolation, "planar-crs84-linear")

    def test_real_mutations_are_killed_by_unchanged_witnesses(self):
        source = Path(spatial.__file__).read_text()
        geometry_source = Path(_spatial_geometry.__file__).read_text()
        dedup = '''        seen_geometry = set()
        retained = []
        for piece in target_intervals:
            p, i = piece.start.part_index, piece.start.observation_index
            obs = track["parts"][p]["observations"]
            key = LineString((obs[i]["position"], obs[i+1]["position"])).intersection(area).normalize().wkb
            if key not in seen_geometry:
                retained.append(piece)
                seen_geometry.add(key)
        target_intervals = retained
'''
        mutations = [
            ("spatial.py", source.replace("enumerate(quality_projection.gaps)", "enumerate(())"), "test_partial_with_gap_witness"),
            ("spatial.py", source.replace("for admitted in quality_projection.usable_intervals:", "for admitted in quality_projection.usable_intervals + tuple(e.interval for e in quality_projection.excluded_intervals):"), "test_quality_gap_witness"),
            ("spatial.py", source.replace('                relation = "unknown"', '                relation = "outside"'), "test_source_gap_chord_never_becomes_geometry"),
            ("spatial.py", source.replace("            if target_intervals and outside_intervals:", '            if gaps:\n                relation = "unknown"\n            elif target_intervals and outside_intervals:'), "test_partial_with_gap_witness"),
            ("_spatial_geometry.py", geometry_source.replace("    envelope = box(*bound.bbox)", '    return "disjoint"  # mutant mistakes full domain for local proof\n    envelope = box(*bound.bbox)'), "test_domain_bound_local_witness"),
            ("spatial.py", source.replace("from shapely.errors", "from shapely.geometry import LineString\nfrom shapely.errors").replace("                target_intervals.extend(covered)", "                if not covered and LineString((left, right)).intersects(area):\n                    covered = (ParentInterval(TrackPosition(p, i), TrackPosition(p, i+1)),)\n                target_intervals.extend(covered)"), "test_point_touch_witness"),
            ("spatial.py", source.replace("from shapely.errors", "from shapely.geometry import LineString\nfrom shapely.errors").replace("        assessable = bool(target_intervals or outside_intervals)", dedup + "        assessable = bool(target_intervals or outside_intervals)"), "test_repeated_entry_and_direction_preserved"),
            ("spatial.py", source.replace('            reason = "NO_POSITIVE_LENGTH_USABLE_GEOMETRY"', '            reason = "NO_POSITIVE_LENGTH_USABLE_GEOMETRY"\n            relation = "unknown"'), "test_singleton_nonassessable_witness"),
        ]
        for filename, mutant, witness in mutations:
            with self.subTest(witness=witness, filename=filename), tempfile.TemporaryDirectory() as directory:
                self.assertNotEqual(mutant, geometry_source if filename.startswith("_") else source)
                package = Path(directory) / "target_area_route_reconstruction"
                shutil.copytree(Path(spatial.__file__).parent, package, ignore=shutil.ignore_patterns("__pycache__"))
                (package / filename).write_text(mutant)
                env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": os.pathsep.join((directory, str(ROOT / "tests")))}
                run = subprocess.run([sys.executable, "-m", "unittest", "test_spatial_relation.SpatialRelationTests." + witness],
                                     env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                self.assertIn("AssertionError", run.stderr)
                self.assertIn("Ran 1 test", run.stderr)


if __name__ == "__main__":
    unittest.main()
