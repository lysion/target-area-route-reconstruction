"""M2B independent edge/lineage oracles and actual producer mutation witnesses."""

from __future__ import annotations

import copy
import hashlib
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

from target_area_route_reconstruction import (
    QualityPolicy, TrackPosition, ingest_bytes, ingest_file, project_quality, verify_quality,
)
from target_area_route_reconstruction import quality
from target_area_route_reconstruction._quality_numerics import distance_metres, utc_seconds
from target_area_route_reconstruction.quality_models import (
    DomainBound, DomainProofParameters, EdgeDiagnostic, ExcludedInterval, Gap,
    GapConstraint, ParentInterval, ParentReference, QualityAlgorithm, QualityParameters,
    QualityProjection,
)
from test_canonical_ingestion import SOURCE, RAW, ROOT, gpx

sys.path.insert(0, str(ROOT / "scripts"))
from strict_json import load_json
from generate_synthetic_source_fixtures import build_fit


POLICY = QualityPolicy(max_implied_speed_mps=100.0)  # test policy, not human physiology
DISABLED = QualityPolicy()


def interval(p, start, end):
    return ParentInterval(TrackPosition(p, start), TrackPosition(p, end))


def ingest_parts(parts):
    rows = []
    for part in parts:
        points = []
        for observation in part:
            lon, lat = observation["position"]
            time = "<time>" + observation["timestamp"] + "</time>" if "timestamp" in observation else ""
            points.append(f'<trkpt lon="{lon:.210f}" lat="{lat:.210f}">{time}</trkpt>')
        rows.append(points)
    return ingest_bytes(gpx(rows), source_kind="gpx", track_source=SOURCE)


def metric(name):
    track = load_json(ROOT / "tests/fixtures/metrics" / (name + ".json"))
    return ingest_parts([part["observations"] for part in track["parts"]])


def reference(evidence):
    return ParentReference(evidence.canonical_track["id"], evidence.canonical_track["revision_id"])


def fingerprint(evidence):
    # Public deterministic M2A serialization, not a producer helper.
    return hashlib.sha256(evidence.to_json().encode()).hexdigest()


def manual_jump(evidence):
    """Hand-built expected claim; intentionally independent of project_quality."""
    parent = reference(evidence)
    return QualityProjection(parent, QualityAlgorithm(QualityParameters(POLICY)), fingerprint(evidence),
                             (interval(0, 0, 1), interval(0, 2, 3)),
                             (ExcludedInterval(interval(0, 1, 2), "IMPLIED_SPEED_EXCEEDS_POLICY", (1, 2)),),
                             (Gap(parent, TrackPosition(0, 1), TrackPosition(0, 2), "quality_exclusion",
                                  ("IMPLIED_SPEED_EXCEEDS_POLICY",), excluded_interval_index=0),))


class QualityProjectionTests(unittest.TestCase):
    def checked(self, evidence, policy=DISABLED):
        result = project_quality(evidence, policy=policy)
        self.assertEqual(result.outcome, "produced", result.issues)
        checked = verify_quality(result.projection, evidence, policy=policy)
        self.assertEqual(checked.outcome, "valid", checked.issues)
        return result.projection

    def assert_rejected(self, claim, evidence, code, policy=POLICY):
        result = verify_quality(claim, evidence, policy=policy)
        self.assertEqual(result.outcome, "invalid", result)
        self.assertIn(code, [issue.code for issue in result.issues], result)
        return result

    def test_clean_track_exact_accounting_and_parent(self):
        evidence = metric("constant-speed")
        q = self.checked(evidence, POLICY)
        self.assertEqual(q.canonical_track, reference(evidence))
        count = len(evidence.canonical_track["parts"][0]["observations"])
        self.assertEqual(q.usable_intervals, (interval(0, 0, count - 1),))
        self.assertEqual((q.excluded_intervals, q.gaps, q.diagnostics), ((), (), ()))

    def test_gpx_discontinuity_witness(self):
        evidence = ingest_file(RAW / "gpx/discontinuity.gpx", source_kind="gpx", track_source=SOURCE)
        q = self.checked(evidence)
        self.assertEqual(q.usable_intervals, (interval(0, 0, 1), interval(1, 0, 1)))
        self.assertEqual(len(q.gaps), 1)
        self.assertEqual((q.gaps[0].start, q.gaps[0].end), (TrackPosition(0, 1), TrackPosition(1, 0)))
        self.assertEqual(q.gaps[0].causes, ("SOURCE_CONTINUITY_BREAK",))

    def test_fit_missing_position_witness(self):
        evidence = ingest_file(RAW / "fit/mixed-position.fit", source_kind="fit", track_source=SOURCE)
        q = self.checked(evidence)
        self.assertEqual(q.usable_intervals, ())
        self.assertEqual(q.excluded_intervals, ())
        self.assertEqual(len(q.gaps), 1)
        gap = q.gaps[0]
        self.assertEqual((gap.start, gap.end), (TrackPosition(0, 0), TrackPosition(1, 0)))
        self.assertEqual(gap.diagnostic_indices, (0,))
        self.assertEqual(evidence.diagnostics[0].source.record_index, 1)
        self.assertEqual([m.source.record_index for m in evidence.observation_sources], [0, 2])
        self.assertEqual(verify_quality(q, evidence, policy=DISABLED).gap_constraint_statuses, ("unavailable",))

    def test_fit_multiple_missing_records_and_open_ended_runs(self):
        from datetime import datetime, timedelta, timezone
        start = datetime(2026, 10, 7, tzinfo=timezone.utc)
        positions = [None, (0, 0), None, None, (0.01, 0), None]
        records = [(start + timedelta(seconds=i), xy[1] if xy else None, xy[0] if xy else None)
                   for i, xy in enumerate(positions)]
        evidence = ingest_bytes(build_fit(records), source_kind="fit", track_source=SOURCE)
        q = self.checked(evidence)
        self.assertEqual([g.diagnostic_indices for g in q.gaps], [(0,), (1, 2), (3,)])
        self.assertIsNone(q.gaps[0].start)
        self.assertIsNone(q.gaps[-1].end)
        self.assertEqual([m.source.record_index for m in evidence.observation_sources], [1, 4])
        self.assertEqual(q.usable_intervals, ())

    def test_empty_gpx_parts_remain_gap_provenance(self):
        evidence = ingest_parts([[], [{"position": [0, 0]}], [], [], [{"position": [1, 0]}], []])
        q = self.checked(evidence)
        self.assertEqual(len(q.gaps), 3)
        referenced = [i for g in q.gaps for i in g.diagnostic_indices]
        self.assertEqual(referenced, list(range(len(evidence.diagnostics))))
        self.assertTrue(all(g.kind == "source_gap" for g in q.gaps))
        self.assertIn("EMPTY_SOURCE_PART", q.gaps[1].causes)

    def test_repeated_coordinates_and_zero_edges_are_accounted(self):
        evidence = ingest_parts([[{"position": xy} for xy in ([0, 0], [0, 0], [1, 0], [0, 0], [0, 0])]])
        before = evidence.to_json()
        q = self.checked(evidence)
        self.assertEqual(q.usable_intervals, (interval(0, 0, 4),))
        self.assertEqual(len(q.diagnostics), 4)
        self.assertEqual(evidence.to_json(), before)

    def test_gps_jump_witness(self):
        evidence = metric("gps-jump")
        original = evidence.to_json()
        q = self.checked(evidence, POLICY)
        self.assertEqual(q, manual_jump(evidence))
        self.assertEqual(q.usable_intervals, (interval(0, 0, 1), interval(0, 2, 3)))
        self.assertEqual(q.excluded_intervals[0].interval, interval(0, 1, 2))
        self.assertEqual(evidence.to_json(), original)
        self.assertEqual(len(evidence.canonical_track["parts"][0]["observations"]), 4)

    def test_same_jump_without_policy_is_unassessed_not_rejected(self):
        q = self.checked(metric("gps-jump"))
        self.assertEqual(q.usable_intervals, (interval(0, 0, 3),))
        self.assertEqual(q.excluded_intervals, ())
        self.assertEqual([d.code for d in q.diagnostics], ["SPEED_RULE_DISABLED"] * 3)

    def test_missing_timestamps_do_not_reject_space(self):
        q = self.checked(metric("missing-timestamps"), POLICY)
        self.assertEqual(q.excluded_intervals, ())
        self.assertEqual(q.diagnostics[0].code, "SPEED_TIME_MISSING")

    def test_jump_with_missing_time_is_not_forced_to_fail(self):
        evidence = ingest_parts([[{"position": [0, 0]}, {"position": [170, 60]}]])
        q = self.checked(evidence, POLICY)
        self.assertEqual(q.usable_intervals, (interval(0, 0, 1),))
        self.assertEqual(q.diagnostics[0].code, "SPEED_TIME_MISSING")

    def test_nonincreasing_times_remain_original_order(self):
        for second in ("2026-10-07T00:00:00Z", "2026-10-06T23:59:59Z"):
            with self.subTest(second=second):
                evidence = ingest_parts([[{"position": [0, 0], "timestamp": "2026-10-07T00:00:00Z"},
                                          {"position": [1, 0], "timestamp": second}]])
                before = evidence.to_json()
                q = self.checked(evidence, POLICY)
                self.assertEqual(q.usable_intervals, (interval(0, 0, 1),))
                self.assertEqual(q.diagnostics[0].code, "SPEED_TIME_NONINCREASING")
                self.assertEqual(evidence.to_json(), before)

    def test_tiny_positive_geometry_survives_distance_rounding(self):
        for size in (5e-13, 1e-200):
            with self.subTest(size=size):
                evidence = ingest_parts([[{"position": [0, 0], "timestamp": "2026-10-07T00:00:00Z"},
                                          {"position": [size, 0], "timestamp": "2026-10-07T00:00:01Z"}]])
                self.assertNotEqual(evidence.canonical_track["parts"][0]["observations"][1]["position"], [0, 0])
                self.assertEqual(self.checked(evidence, POLICY).usable_intervals, (interval(0, 0, 1),))

    def test_quality_unavailable_is_distinct_from_empty_projection(self):
        for filename in ("fit/no-position.fit", "gpx/malformed.gpx"):
            evidence = ingest_file(RAW / filename, source_kind=Path(filename).suffix[1:], track_source=SOURCE)
            result = project_quality(evidence, policy=POLICY)
            self.assertEqual(result.outcome, "quality_evidence_unavailable")
            self.assertIsNone(result.projection)
            self.assertEqual(result.issues[0].code, "QUALITY_EVIDENCE_UNAVAILABLE")

    def test_six_committed_metric_shapes_are_supported(self):
        for case in load_json(ROOT / "tests/fixtures/metric-scenarios.json")["cases"]:
            with self.subTest(case=case["name"]):
                self.checked(metric(case["name"]), POLICY)

    def test_determinism_immutability_and_detached_serialization(self):
        evidence = metric("gps-jump")
        q = self.checked(evidence, POLICY)
        self.assertEqual(q.to_json(), self.checked(evidence, POLICY).to_json())
        snapshot = q.to_dict()
        snapshot["usable_intervals"][1]["start"]["observation_index"] = 1
        self.assertEqual(q.usable_intervals[1].start.observation_index, 2)
        with self.assertRaises(FrozenInstanceError):
            q.canonical_track.revision_id = "stale"

    def test_exact_time_fraction_beyond_microseconds(self):
        self.assertEqual(utc_seconds("2026-10-07T00:00:00.000000000000002Z")
                         - utc_seconds("2026-10-07T00:00:00.000000000000001Z"),
                         __import__("fractions").Fraction(1, 10**15))
        evidence = ingest_parts([[{"position": [0, 0], "timestamp": "2026-10-07T00:00:00.000000001Z"},
                                  {"position": [0.001, 0], "timestamp": "2026-10-07T00:00:00.000000002Z"}]])
        self.assertEqual(len(self.checked(evidence, POLICY).excluded_intervals), 1)

    def test_geodesic_equator_antimeridian_poles_and_antipodes(self):
        # Equatorial expected arc derived analytically from WGS84 semi-major axis.
        self.assertAlmostEqual(distance_metres([0, 0], [1, 0]), 6378137 * math.pi / 180, places=7)
        self.assertAlmostEqual(distance_metres([179.5, 0], [-179.5, 0]), 6378137 * math.pi / 180, places=7)
        self.assertEqual(distance_metres([0, 90], [180, 90]), 0)
        self.assertAlmostEqual(distance_metres([0, 0], [180, 0]), 20003931.458625447, places=6)
        evidence = ingest_parts([[{"position": [179.999, 0], "timestamp": "2026-10-07T00:00:00Z"},
                                  {"position": [-179.999, 0], "timestamp": "2026-10-07T00:00:10Z"}]])
        self.assertEqual(self.checked(evidence, POLICY).excluded_intervals, ())

    def test_numerical_guard_is_unassessed_not_geometry_erasure(self):
        evidence = ingest_parts([[{"position": [0, 0], "timestamp": "2026-10-07T00:00:00Z"},
                                  {"position": [1, 0], "timestamp": "2026-10-07T00:00:01Z"}]])
        policy = QualityPolicy(max_implied_speed_mps=distance_metres([0, 0], [1, 0]))
        q = self.checked(evidence, policy)
        self.assertEqual(q.usable_intervals, (interval(0, 0, 1),))
        self.assertEqual(q.diagnostics[0].code, "SPEED_NUMERICALLY_INDETERMINATE")

    def test_policy_rejects_nonfinite_nonpositive_or_implicit_values(self):
        for value in (float("nan"), float("inf"), -1, 0, True, "100", 10**1000):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "^QUALITY_POLICY_INVALID$"):
                QualityPolicy(max_implied_speed_mps=value)

    def test_manually_constructed_valid_claim(self):
        evidence = metric("gps-jump")
        with patch.object(quality, "project_quality", side_effect=AssertionError("producer called")), \
                patch.object(quality, "_decision", side_effect=AssertionError("producer called")):
            self.assertEqual(verify_quality(manual_jump(evidence), evidence, policy=POLICY).outcome, "valid")

    def test_wrong_parent_and_stale_revision(self):
        evidence = metric("gps-jump")
        q = manual_jump(evidence)
        for parent in (replace(q.canonical_track, id="wrong"), replace(q.canonical_track, revision_id="stale")):
            self.assert_rejected(replace(q, canonical_track=parent), evidence, "PARENT_REFERENCE_MISMATCH")

    def test_in_place_parent_mutation_is_detected(self):
        evidence = copy.deepcopy(metric("gps-jump"))
        q = manual_jump(evidence)
        evidence.canonical_track["parts"][0]["observations"].pop(1)
        result = verify_quality(q, evidence, policy=POLICY)
        self.assertEqual(result.outcome, "quality_evidence_unavailable")
        self.assertEqual(result.issues[0].code, "PARENT_CONTENT_REVISION_MISMATCH")

    def test_omitted_middle_edge_is_not_hidden_by_geometry(self):
        evidence = metric("gps-jump")
        q = manual_jump(evidence)
        self.assert_rejected(replace(q, excluded_intervals=()), evidence, "EDGE_UNACCOUNTED")

    def test_reordered_and_overlapping_intervals(self):
        evidence = metric("gps-jump")
        q = manual_jump(evidence)
        self.assert_rejected(replace(q, usable_intervals=q.usable_intervals[::-1]), evidence, "INTERVAL_ORDER_INVALID")
        self.assert_rejected(replace(q, usable_intervals=q.usable_intervals + (q.usable_intervals[-1],)), evidence, "INTERVAL_OVERLAP")
        self.assert_rejected(replace(q, excluded_intervals=q.excluded_intervals * 2), evidence, "EDGE_DOUBLE_ACCOUNTED")

    def test_reconnecting_rejected_edge_is_double_accounting(self):
        evidence = metric("gps-jump")
        q = manual_jump(evidence)
        self.assert_rejected(replace(q, usable_intervals=(interval(0, 0, 3),)), evidence, "EDGE_DOUBLE_ACCOUNTED")

    def test_reconnection_even_after_removing_exclusion_fails_rule(self):
        evidence = metric("gps-jump")
        q = manual_jump(evidence)
        self.assert_rejected(replace(q, usable_intervals=(interval(0, 0, 3),), excluded_intervals=(), gaps=()),
                             evidence, "EDGE_DECISION_MISMATCH")

    def test_cross_part_and_position_defects(self):
        evidence = metric("discontinuity")
        q = self.checked(evidence)
        cases = [(ParentInterval(TrackPosition(0, 0), TrackPosition(1, 1)), "INTERVAL_CROSS_PART"),
                 (interval(5, 0, 1), "TRACK_POSITION_OUT_OF_BOUNDS"),
                 (interval(0, 0, 99), "TRACK_POSITION_OUT_OF_BOUNDS"),
                 (interval(0, 1, 0), "INTERVAL_REVERSED_OR_EMPTY"),
                 (ParentInterval(TrackPosition(0, 0, 1.0), TrackPosition(0, 1)), "TRACK_POSITION_INVALID"),
                 (ParentInterval(TrackPosition(0, 0, float("nan")), TrackPosition(0, 1)), "TRACK_POSITION_INVALID"),
                 (ParentInterval(TrackPosition(0, 0, 0.5), TrackPosition(0, 1)), "WHOLE_EDGE_RANGE_REQUIRED")]
        for invalid, code in cases:
            with self.subTest(code=code):
                self.assert_rejected(replace(q, usable_intervals=(invalid,)), evidence, code, DISABLED)

    def test_compacted_index_claim_fails(self):
        evidence = metric("gps-jump")
        q = manual_jump(evidence)
        self.assert_rejected(replace(q, usable_intervals=(interval(0, 0, 1), interval(0, 1, 2))),
                             evidence, "EDGE_UNACCOUNTED")

    def test_exclusion_reason_and_source_reference_are_checked(self):
        evidence = metric("gps-jump")
        q = manual_jump(evidence)
        self.assert_rejected(replace(q, excluded_intervals=(replace(q.excluded_intervals[0], reason="BAD_GPS"),)),
                             evidence, "EXCLUSION_REASON_INVALID")
        self.assert_rejected(replace(q, excluded_intervals=(replace(q.excluded_intervals[0], observation_source_indices=(0, 1)),)),
                             evidence, "EXCLUSION_EVIDENCE_MISMATCH")

    def test_missing_or_fake_gap_cannot_pass(self):
        evidence = metric("gps-jump")
        q = manual_jump(evidence)
        self.assert_rejected(replace(q, gaps=()), evidence, "REQUIRED_GAP_MISSING")
        fake = replace(q.gaps[0], start=TrackPosition(0, 0), end=TrackPosition(0, 1))
        self.assert_rejected(replace(q, gaps=(fake,)), evidence, "GAP_PROVENANCE_MISMATCH")
        stale = replace(q.gaps[0], canonical_track=replace(q.canonical_track, revision_id="stale"))
        self.assert_rejected(replace(q, gaps=(stale,)), evidence, "GAP_PARENT_MISMATCH")

    def test_missing_record_cannot_disappear_from_provenance(self):
        evidence = ingest_file(RAW / "fit/mixed-position.fit", source_kind="fit", track_source=SOURCE)
        q = self.checked(evidence)
        self.assert_rejected(replace(q, gaps=(replace(q.gaps[0], diagnostic_indices=()),)),
                             evidence, "GAP_PROVENANCE_MISMATCH", DISABLED)
        self.assert_rejected(replace(q, gaps=()), evidence, "REQUIRED_GAP_MISSING", DISABLED)
        changed_evidence = replace(evidence, diagnostics=())
        result = verify_quality(q, changed_evidence, policy=DISABLED)
        self.assertEqual(result.issues[0].code, "SOURCE_GAP_EVIDENCE_MISSING")

    def test_altered_algorithm_parameters_fail_expected_contract(self):
        evidence = metric("gps-jump")
        q = manual_jump(evidence)
        for algorithm in (QualityAlgorithm(QualityParameters(DISABLED)),
                          replace(q.algorithm, version="future"),
                          replace(q.algorithm, parameters=replace(q.algorithm.parameters, distance_roundoff_guard_m=0.0))):
            self.assert_rejected(replace(q, algorithm=algorithm), evidence, "ALGORITHM_CONTRACT_MISMATCH")

    def test_full_domain_proof_is_tautological_and_does_not_resolve_gap(self):
        evidence = metric("discontinuity")
        policy = QualityPolicy(include_domain_bounds=True)
        q = self.checked(evidence, policy)
        self.assertEqual(len(q.gap_constraints), 1)
        self.assertEqual(q.gap_constraints[0].bound.bbox, (-180, -90, 180, 90))
        self.assertEqual(q.gaps[0].state, "unresolved")
        self.assertEqual(verify_quality(q, evidence, policy=policy).gap_constraint_statuses, ("verified",))
        self.assertEqual(q.usable_intervals, (interval(0, 0, 1), interval(1, 0, 1)))

    def proof_case(self):
        evidence = metric("gps-jump")
        policy = replace(POLICY, include_domain_bounds=True)
        q = manual_jump(evidence)
        q = replace(q, algorithm=QualityAlgorithm(QualityParameters(policy)),
                    gap_constraints=(GapConstraint(0, reference(evidence), fingerprint(evidence)),))
        self.assertEqual(verify_quality(q, evidence, policy=policy).outcome, "valid")
        return evidence, policy, q

    def test_unsupported_gap_proof_is_explicitly_rejected(self):
        evidence, policy, q = self.proof_case()
        for method in ("endpoint-buffer", "observed-average-speed", "nearest-road", "historical-route"):
            claim = replace(q, gap_constraints=(replace(q.gap_constraints[0], method=method),))
            result = self.assert_rejected(claim, evidence, "GAP_CONSTRAINT_UNSUPPORTED", policy)
            self.assertEqual(result.gap_constraint_statuses, ("unsupported",))

    def test_stale_or_wrong_proof_evidence(self):
        evidence, policy, q = self.proof_case()
        for constraint in (replace(q.gap_constraints[0], evidence_digest="0" * 64),
                           replace(q.gap_constraints[0], canonical_track=replace(q.canonical_track, revision_id="stale"))):
            self.assert_rejected(replace(q, gap_constraints=(constraint,)), evidence, "CONSTRAINT_EVIDENCE_MISMATCH", policy)

    def test_nonfinite_or_smaller_domain_bound_fails(self):
        evidence, policy, q = self.proof_case()
        for number in (float("nan"), float("inf"), float("-inf")):
            claim = replace(q, gap_constraints=(replace(q.gap_constraints[0], bound=DomainBound((number, -90, 180, 90))),))
            self.assert_rejected(claim, evidence, "CONSTRAINT_BOUND_INVALID", policy)
        claim = replace(q, gap_constraints=(replace(q.gap_constraints[0], bound=DomainBound((-1, -1, 1, 1))),))
        self.assert_rejected(claim, evidence, "CONSTRAINT_BOUND_PROOF_MISMATCH", policy)

    def test_proof_parameters_and_gap_reference_are_verified(self):
        evidence, policy, q = self.proof_case()
        claim = replace(q, gap_constraints=(replace(q.gap_constraints[0], parameters=DomainProofParameters("local-buffer")),))
        self.assert_rejected(claim, evidence, "CONSTRAINT_PARAMETERS_MISMATCH", policy)
        claim = replace(q, gap_constraints=(replace(q.gap_constraints[0], gap_index=99),))
        self.assert_rejected(claim, evidence, "CONSTRAINT_GAP_REFERENCE_INVALID", policy)

    def test_identical_part_geometry_retains_both_occurrences(self):
        points = [{"position": [0, 0]}, {"position": [1, 0]}, {"position": [0, 0]}]
        evidence = ingest_parts([points, points])
        q = self.checked(evidence)
        self.assertEqual(q.usable_intervals, (interval(0, 0, 2), interval(1, 0, 2)))
        self.assert_rejected(replace(q, usable_intervals=q.usable_intervals[:1]), evidence, "EDGE_UNACCOUNTED", DISABLED)

    def test_multiple_exclusions_keep_every_edge_and_gap(self):
        evidence = ingest_parts([[{"position": [lon, 0], "timestamp": f"2026-10-07T00:00:{i:02d}Z"}
                                  for i, lon in enumerate((0, 1, 2, 2.00001, 3))]])
        q = self.checked(evidence, POLICY)
        self.assertEqual(q.usable_intervals, (interval(0, 2, 3),))
        self.assertEqual([e.interval for e in q.excluded_intervals], [interval(0, 0, 1), interval(0, 1, 2), interval(0, 3, 4)])
        self.assertEqual([g.excluded_interval_index for g in q.gaps], [0, 1, 2])
        self.assert_rejected(replace(q, gaps=q.gaps[::-1]), evidence, "GAP_ORDER_INVALID")

    def test_all_rejected_edges_still_leave_observations(self):
        evidence = metric("gps-jump")
        before = evidence.to_json()
        q = self.checked(evidence, QualityPolicy(max_implied_speed_mps=1))
        self.assertEqual(q.usable_intervals, ())
        self.assertEqual(len(q.excluded_intervals), 3)
        self.assertEqual(len(q.gaps), 3)
        self.assertEqual(evidence.to_json(), before)

    def test_malformed_mutable_values_fail_closed(self):
        evidence = metric("gps-jump")
        q = manual_jump(evidence)
        self.assert_rejected(replace(q, usable_intervals=list(q.usable_intervals)), evidence, "PROJECTION_MALFORMED")
        self.assert_rejected(replace(q, gaps=(None,)), evidence, "PROJECTION_MALFORMED")

    def test_bool_is_not_a_provenance_index(self):
        evidence = metric("gps-jump")
        q = manual_jump(evidence)
        self.assert_rejected(replace(q, excluded_intervals=(replace(q.excluded_intervals[0], observation_source_indices=(True, 2)),)),
                             evidence, "EXCLUSION_EVIDENCE_MISMATCH")
        evidence = metric("discontinuity")
        q = self.checked(evidence)
        self.assert_rejected(replace(q, gaps=(replace(q.gaps[0], diagnostic_indices=(False,)),)),
                             evidence, "GAP_PROVENANCE_MISMATCH", DISABLED)

    def test_source_mapping_and_evidence_snapshot_are_bound(self):
        evidence = metric("gps-jump")
        q = manual_jump(evidence)
        self.assert_rejected(replace(q, evidence_digest="0" * 64), evidence, "EVIDENCE_REFERENCE_MISMATCH")
        changed = replace(evidence, observation_sources=evidence.observation_sources[::-1])
        result = verify_quality(q, changed, policy=POLICY)
        self.assertEqual(result.issues[0].code, "SOURCE_MAPPING_INVALID")

    def test_proof_presence_matches_explicit_parameters(self):
        evidence, policy, q = self.proof_case()
        self.assert_rejected(replace(q, gap_constraints=()), evidence, "CONSTRAINT_POLICY_MISMATCH", policy)
        self.assert_rejected(replace(q, gap_constraints=q.gap_constraints * 2), evidence, "CONSTRAINT_GAP_REFERENCE_INVALID", policy)

    def test_original_raw_baseline_all_supported_results(self):
        manifest = load_json(RAW / "manifest.json")
        for entry in manifest["fixtures"]:
            with self.subTest(entry=entry["id"]):
                evidence = ingest_file(RAW / entry["path"], source_kind=entry["format"], track_source=SOURCE)
                if evidence.outcome == "success":
                    self.checked(evidence, POLICY)
                else:
                    self.assertEqual(project_quality(evidence, policy=POLICY).outcome, "quality_evidence_unavailable")

    def test_unavailable_distance_is_explicit_and_not_a_rejection(self):
        evidence = metric("gps-jump")
        with patch("target_area_route_reconstruction.quality.distance_metres", side_effect=ValueError("DISTANCE_UNAVAILABLE")), \
                patch("target_area_route_reconstruction.quality_verifier.distance_metres", side_effect=ValueError("DISTANCE_UNAVAILABLE")):
            q = self.checked(evidence, POLICY)
            self.assertEqual(q.usable_intervals, (interval(0, 0, 3),))
            self.assertEqual([d.code for d in q.diagnostics], ["SPEED_DISTANCE_UNAVAILABLE"] * 3)

    def test_unsupported_time_is_not_a_fabricated_duration(self):
        for value in ("2026-10-07T00:00:60Z", "2026-10-07T00:00:00", "not-time"):
            self.assertIsNone(utc_seconds(value))

    def test_unavailable_rule_diagnostics_cannot_be_deleted(self):
        evidence = metric("missing-timestamps")
        q = self.checked(evidence, POLICY)
        self.assert_rejected(replace(q, diagnostics=()), evidence, "QUALITY_DIAGNOSTICS_MISMATCH")

    def test_producer_mutations_fail_existing_positive_witnesses(self):
        source = Path(quality.__file__).read_text()
        mutations = [
            (source.replace("run_start = None  # rejection breaks usable continuity", "run_start = i  # mutant bridges rejection"),
             "test_gps_jump_witness"),
            (source.replace("if diagnostic.code in GAP_CODES:", "if False:  # mutant drops source gaps"),
             "test_fit_missing_position_witness"),
            (source.replace("    gaps.sort(key=order)", "    usable = [ParentInterval(usable[0].start, usable[-1].end)] if usable else []\n    gaps.sort(key=order)"),
             "test_gpx_discontinuity_witness"),
        ]
        for mutated, witness in mutations:
            with self.subTest(witness=witness), tempfile.TemporaryDirectory() as directory:
                self.assertNotEqual(mutated, source)
                package = Path(directory) / "target_area_route_reconstruction"
                shutil.copytree(Path(quality.__file__).parent, package, ignore=shutil.ignore_patterns("__pycache__"))
                (package / "quality.py").write_text(mutated)
                env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": os.pathsep.join((directory, str(ROOT / "tests")))}
                run = subprocess.run([sys.executable, "-m", "unittest", "test_quality_projection.QualityProjectionTests." + witness],
                                     env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                self.assertIn("AssertionError", run.stderr)
                self.assertIn("Ran 1 test", run.stderr)


if __name__ == "__main__":
    unittest.main()
