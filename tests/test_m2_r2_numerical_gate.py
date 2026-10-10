"""Independent Codex full-repository audit R2-01/R2-02 regressions.

Unlike the production M2C verifier and the legacy M1 oracle, the expected
intersection in the attack is constructed from exact rational arithmetic on
the ACTUAL binary64 coordinates. No GEOS/Shapely predicate supplies the
expected outcome. Extreme but schema-valid coordinates may be rejected with
a stable numeric failure; they must NEVER be labelled outside/complete or
accepted as an incorrectly extended target fragment.
"""

from __future__ import annotations

import math
import unittest
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

from target_area_route_reconstruction import (
    QualityPolicy, TrackPosition, ingest_bytes, project_quality,
    prove_spatial_relation, verify_quality, verify_spatial_relation,
)
from target_area_route_reconstruction.quality_models import ParentInterval
from target_area_route_reconstruction._spatial_inputs import algorithm, prepare
from target_area_route_reconstruction.spatial_models import SpatialRelationProof
from target_area_route_reconstruction import assemble_spatial_entities
from test_canonical_ingestion import gpx
from test_spatial_relation import arguments, rectangle


def decimal_xml(value):
    """GPX latitude/longitude is xsd:decimal, not scientific notation.

    Preserve very small *nonzero* binary64 values (including 5e-324) through
    real GPX/XSD/normalization rather than constructing a forged CanonicalTrack.
    """
    return format(Decimal(str(value)), "f")


def real_gpx(left, right):
    pts = []
    for lon, lat in (left, right):
        pts.append(f'<trkpt lon="{decimal_xml(lon)}" lat="{decimal_xml(lat)}"/>')
    result = ingest_bytes(gpx([pts]), source_kind="gpx",
                          track_source={"id": "codex-r2-source", "revision_id": "r1"})
    assert result.outcome == "success", result
    assert [x["position"] for x in result.canonical_track["parts"][0]["observations"]] == [
        list(left), list(right)], result.canonical_track
    return result


def exact_positive_horizontal_coverage(a, b, xmin, xmax):
    """Liang-Barsky for a horizontal edge; Fraction(float) is exact binary64.

    This intentionally *does not* use GEOS, any producer/verifier helper,
    floating-point interpolation or an epsilon cutoff.
    """
    a, b, xmin, xmax = (Fraction(x) for x in (a, b, xmin, xmax))
    assert b > a and xmax > xmin
    lo = max(Fraction(0), (xmin - a) / (b - a))
    hi = min(Fraction(1), (xmax - a) / (b - a))
    return lo < hi, lo, hi


class IndependentR2Numerics(unittest.TestCase):
    def check_attack(self, left_lon, right_lon, xmin, xmax):
        self.assertTrue(math.isfinite(left_lon) and math.isfinite(right_lon))
        self.assertTrue(xmax > xmin)
        exact, lo, hi = exact_positive_horizontal_coverage(
            left_lon, right_lon, xmin, xmax)
        self.assertTrue(exact, ("independent exact coverage witness", lo, hi))
        evidence = real_gpx((left_lon, 0), (right_lon, 0))
        args = arguments(evidence, rectangle(xmin, -1, xmax, 1))
        proof = prove_spatial_relation(**args)
        # A numeric failure is an accepted *safe* result: no trustworthy
        # relation/proof/target fragment may escape through the public API.
        self.assertEqual(proof.outcome, "numerical_failure", proof)
        self.assertIsNone(proof.proof)
        self.assertTrue(
            any(issue.code in (
                "SPATIAL_NUMERICAL_BOUNDARY_UNRESOLVED",
                "SPATIAL_NUMERICAL_ENGINE_WARNING",
                "SPATIAL_PARTITION_NUMERICAL_FAILURE",
                "SPATIAL_FRACTION_UNREPRESENTABLE",
                "SPATIAL_LINEAGE_NUMERICAL_FAILURE",
            ) for issue in proof.issues), proof.issues)
        # Adversarial verifier attack: manufacture the exact kind of
        # outside/complete proof incorrectly accepted by the old shared-GEOS
        # verifier. No producer helper is used for expected fragments.
        _, _, authority, _ = prepare(**args)
        forged = SpatialRelationProof(
            authority=authority, algorithm=algorithm(), assessable=True,
            relation="outside", coverage_completeness="complete", reason=None,
            target_coverage_intervals=(),
            outside_evidence_intervals=(
                ParentInterval(TrackPosition(0, 0), TrackPosition(0, 1)),),
            stationary_evidence=(), gap_relevance=(),
        )
        checked = verify_spatial_relation(forged, **args)
        self.assertEqual(checked.outcome, "invalid", checked)
        self.assertTrue(
            any(x.code.startswith("SPATIAL_NUMERICAL_") for x in checked.issues),
            checked)
        assembled = assemble_spatial_entities(proof=forged, **args)
        self.assertNotEqual(assembled.outcome, "produced", assembled)

    def test_r2_01_a_false_outside_with_nextafter_thin_rectangle(self):
        x = 8e-200
        self.check_attack(-9e-200, 1.8e-199, x, math.nextafter(x, math.inf))

    def test_r2_01_b_polygon_bound_overshoot_with_subnormal_edge(self):
        self.check_attack(-1.3e-199, 3e-200, 0.0, 5e-324)

    def test_multiple_scales_near_boundary_with_independent_fraction_oracle(self):
        for magnitude in (1e-160, 1e-175, 1e-190, 1e-200, 1e-240):
            with self.subTest(magnitude=magnitude):
                xmin = magnitude
                self.check_attack(-2 * magnitude, 3 * magnitude,
                                  xmin, math.nextafter(xmin, math.inf))

    def test_tiny_positive_evidence_fully_inside_does_not_get_erased(self):
        for size in (1e-200, 5e-324):
            with self.subTest(size=size):
                evidence = real_gpx((0, 0), (size, 0))
                args = arguments(evidence, rectangle(-1, -1, 1, 1))
                result = prove_spatial_relation(**args)
                self.assertEqual(result.outcome, "produced", result)
                self.assertEqual(result.proof.relation, "inside")
                self.assertEqual(len(result.proof.target_coverage_intervals), 1)
                self.assertEqual(verify_spatial_relation(
                    result.proof, **args).outcome, "valid")


class IndependentR2Identity(unittest.TestCase):
    def test_zero_and_negative_zero_become_canonical_parent_identity(self):
        examples = (TrackPosition(0, 0, 0.0), TrackPosition(0, 0, 0),
                    TrackPosition(0, 0, -0.0))
        self.assertTrue(all(type(x.fraction_to_next) is float for x in examples))
        self.assertTrue(all(math.copysign(1.0, x.fraction_to_next) == 1 for x in examples))
        self.assertEqual(len({str(x) for x in examples}), 1)

        evidence = real_gpx((0, 0), (0.1, 0))
        policy = QualityPolicy()
        original = project_quality(evidence, policy=policy)
        self.assertEqual(original.outcome, "produced")
        baseline = original.projection
        for fraction in (0.0, 0, -0.0):
            with self.subTest(fraction=repr(fraction), typ=type(fraction).__name__):
                first = replace(baseline.usable_intervals[0].start,
                                fraction_to_next=fraction)
                changed = replace(baseline, usable_intervals=(
                    replace(baseline.usable_intervals[0], start=first),))
                self.assertEqual(changed.to_json(), baseline.to_json())
                self.assertEqual(verify_quality(
                    changed, evidence, policy=policy).outcome, "valid")
                original_args = arguments(evidence, rectangle(-1, -1, 1, 1))
                changed_args = {**original_args, "quality_projection": changed}
                # A canonical equivalent representation has one spatial
                # authority digest and hence identical downstream revision.
                a = prove_spatial_relation(**original_args)
                b = prove_spatial_relation(**changed_args)
                self.assertEqual((a.outcome, b.outcome), ("produced", "produced"))
                self.assertEqual(a.proof.authority.quality_projection_digest,
                                 b.proof.authority.quality_projection_digest)
                self.assertEqual(a.proof.to_json(), b.proof.to_json())

    def test_manually_bypassed_trackposition_constructor_is_rejected(self):
        evidence = real_gpx((0, 0), (.1, 0))
        policy = QualityPolicy()
        q = project_quality(evidence, policy=policy).projection
        for invalid in (0, -0.0):
            with self.subTest(kind=type(invalid).__name__, value=repr(invalid)):
                bad = object.__new__(TrackPosition)
                object.__setattr__(bad, "part_index", 0)
                object.__setattr__(bad, "observation_index", 0)
                object.__setattr__(bad, "fraction_to_next", invalid)
                hacked = replace(q, usable_intervals=(
                    ParentInterval(bad, q.usable_intervals[0].end),))
                rejected = verify_quality(hacked, evidence, policy=policy)
                self.assertEqual(rejected.outcome, "invalid", rejected)
                self.assertIn("TRACK_POSITION_INVALID", [x.code for x in rejected.issues])

    def test_noncanonical_diagnostic_endpoints_fail_closed_before_spatial_digest(self):
        # Independent PR #21 Codex P2 witness: dataclass equality treats
        # integer/negative zero as equal, while JSON and evidence hashes do
        # not. Test the diagnostic field, not just usable intervals.
        evidence = real_gpx((0, 0), (0.1, 0))
        policy = QualityPolicy()
        baseline = project_quality(evidence, policy=policy).projection
        self.assertEqual(len(baseline.diagnostics), 1)
        self.assertEqual(verify_quality(baseline, evidence, policy=policy).outcome, "valid")
        args = arguments(evidence, rectangle(-1, -1, 1, 1))
        for endpoint in ("start", "end"):
            for invalid in (0, -0.0):
                with self.subTest(endpoint=endpoint, typ=type(invalid).__name__,
                                  value=repr(invalid)):
                    original = getattr(baseline.diagnostics[0].interval, endpoint)
                    forged_position = object.__new__(TrackPosition)
                    object.__setattr__(forged_position, "part_index", original.part_index)
                    object.__setattr__(forged_position, "observation_index", original.observation_index)
                    object.__setattr__(forged_position, "fraction_to_next", invalid)
                    interval = replace(baseline.diagnostics[0].interval,
                                       **{endpoint: forged_position})
                    forged = replace(baseline, diagnostics=(
                        replace(baseline.diagnostics[0], interval=interval),))
                    # The old verifier compared these tuples with dataclass
                    # equality, then approved distinct serialized evidence.
                    self.assertEqual(forged.diagnostics, baseline.diagnostics)
                    self.assertNotEqual(forged.to_json(), baseline.to_json())
                    validation = verify_quality(forged, evidence, policy=policy)
                    self.assertEqual(validation.outcome, "invalid", validation)
                    self.assertIn("TRACK_POSITION_INVALID",
                                  [issue.code for issue in validation.issues])
                    spatial = prove_spatial_relation(
                        **{**args, "quality_projection": forged})
                    self.assertNotEqual(spatial.outcome, "produced", spatial)
                    self.assertIsNone(spatial.proof)


    def test_m2a_source_positions_cannot_forge_equivalent_evidence_digests(self):
        # Third independent Codex P2: an upstream M2A ObservationSource or
        # diagnostic endpoint can have dataclass-equal but JSON-distinct zero.
        # This boundary must reject before project_quality computes a digest.
        simple = real_gpx((0, 0), (0.1, 0))
        gap = ingest_bytes(gpx([
            ['<trkpt lon="0" lat="0"/>', '<trkpt lon="0.1" lat="0"/>'],
            ['<trkpt lon="0.2" lat="0"/>', '<trkpt lon="0.3" lat="0"/>'],
        ]), source_kind="gpx", track_source={"id": "r2-source-gap", "revision_id": "r1"})
        self.assertEqual(gap.outcome, "success")
        self.assertTrue(any(d.previous_position is not None and d.next_position is not None
                            for d in gap.diagnostics), gap.diagnostics)
        for evidence, category, field, issue in (
            (simple, "mapping", "position", "SOURCE_MAPPING_INVALID"),
            (gap, "diagnostic", "previous_position", "SOURCE_DIAGNOSTIC_POSITION_INVALID"),
            (gap, "diagnostic", "next_position", "SOURCE_DIAGNOSTIC_POSITION_INVALID"),
        ):
            policy = QualityPolicy()
            original = project_quality(evidence, policy=policy)
            self.assertEqual(original.outcome, "produced", original)
            self.assertEqual(verify_quality(
                original.projection, evidence, policy=policy).outcome, "valid")
            for invalid in (0, -0.0):
                with self.subTest(category=category, field=field,
                                  representation=(type(invalid).__name__, repr(invalid))):
                    if category == "mapping":
                        row = evidence.observation_sources[0]
                        before = row.position
                    else:
                        row = next(d for d in evidence.diagnostics
                                   if getattr(d, field) is not None)
                        before = getattr(row, field)
                    bad = object.__new__(TrackPosition)
                    object.__setattr__(bad, "part_index", before.part_index)
                    object.__setattr__(bad, "observation_index", before.observation_index)
                    object.__setattr__(bad, "fraction_to_next", invalid)
                    self.assertEqual(bad, before)  # old equality-based admission
                    if category == "mapping":
                        changed = replace(evidence, observation_sources=(
                            replace(row, position=bad), *evidence.observation_sources[1:]))
                    else:
                        idx = evidence.diagnostics.index(row)
                        diagnostics = list(evidence.diagnostics)
                        diagnostics[idx] = replace(row, **{field: bad})
                        changed = replace(evidence, diagnostics=tuple(diagnostics))
                    self.assertNotEqual(changed.to_json(), evidence.to_json())
                    produced = project_quality(changed, policy=policy)
                    self.assertEqual(produced.outcome, "quality_evidence_unavailable", produced)
                    self.assertIn(issue, [i.code for i in produced.issues])
                    verified = verify_quality(original.projection, changed, policy=policy)
                    self.assertEqual(verified.outcome, "quality_evidence_unavailable", verified)
                    self.assertIn(issue, [i.code for i in verified.issues])
                    # Build expected target/policy from valid source first;
                    # the helper intentionally refuses the forged M2A input.
                    args = arguments(evidence, rectangle(-1, -1, 1, 1))
                    denied = prove_spatial_relation(
                        **{**args, "evidence": changed,
                           "quality_projection": original.projection})
                    self.assertNotEqual(denied.outcome, "produced", denied)
                    self.assertIsNone(denied.proof)


    def test_m2c_nested_gap_relevance_endpoint_identity_fails_closed(self):
        # Codex PR #21 P2 witness: the embedded Gap in GapRelevance is a
        # distinct serialized snapshot from the validated M2B Gap. A forged
        # integer/negative zero is dataclass-equal but has a different digest.
        evidence = ingest_bytes(gpx([
            ['<trkpt lon="0" lat="0"/>', '<trkpt lon="0.1" lat="0"/>'],
            ['<trkpt lon="0.2" lat="0"/>', '<trkpt lon="0.3" lat="0"/>'],
        ]), source_kind="gpx", track_source={"id": "r2-nested-gap", "revision_id": "r1"})
        self.assertEqual(evidence.outcome, "success")
        args = arguments(evidence, rectangle(-1, -1, 1, 1))
        result = prove_spatial_relation(**args)
        self.assertEqual(result.outcome, "produced", result)
        baseline = result.proof
        self.assertEqual(verify_spatial_relation(baseline, **args).outcome, "valid")
        self.assertTrue(baseline.gap_relevance)
        for field in ("start", "end"):
            for invalid in (0, -0.0):
                with self.subTest(field=field, type=type(invalid).__name__, value=repr(invalid)):
                    original = getattr(baseline.gap_relevance[0].gap, field)
                    self.assertIsNotNone(original)
                    bad = object.__new__(TrackPosition)
                    object.__setattr__(bad, "part_index", original.part_index)
                    object.__setattr__(bad, "observation_index", original.observation_index)
                    object.__setattr__(bad, "fraction_to_next", invalid)
                    self.assertEqual(bad, original)
                    changed_gap = replace(baseline.gap_relevance[0].gap, **{field: bad})
                    self.assertEqual(changed_gap, baseline.gap_relevance[0].gap)
                    changed_relevance = replace(baseline.gap_relevance[0], gap=changed_gap)
                    forged = replace(baseline, gap_relevance=(
                        changed_relevance, *baseline.gap_relevance[1:]))
                    self.assertNotEqual(forged.to_json(), baseline.to_json())
                    checked = verify_spatial_relation(forged, **args)
                    self.assertEqual(checked.outcome, "invalid", checked)
                    self.assertIn("SPATIAL_POSITION_INVALID",
                                  [issue.code for issue in checked.issues])
                    assembled = assemble_spatial_entities(proof=forged, **args)
                    self.assertNotEqual(assembled.outcome, "produced", assembled)


    def test_nongap_m2a_diagnostic_has_canonical_real_neighbor_positions(self):
        # Codex P2: timestamp diagnostics are not gap diagnostics but still
        # enter the immutable M2A digest. A well-typed, canonical position
        # must ALSO be the exact neighbor of the source record.
        from target_area_route_reconstruction.models import Diagnostic
        evidence = real_gpx((0, 0), (0.1, 0))
        first, second = evidence.observation_sources
        d = Diagnostic("TIMESTAMP_UNREPRESENTABLE", second.source, "timestamp",
                       first.position, second.position)
        admitted = replace(evidence, diagnostics=(d,))
        policy = QualityPolicy()
        projected = project_quality(admitted, policy=policy)
        self.assertEqual(projected.outcome, "produced", projected)
        self.assertEqual(verify_quality(projected.projection, admitted,
                                        policy=policy).outcome, "valid")
        candidates = (
            ("previous_position", TrackPosition(99, 99, 0.0)),
            ("next_position", TrackPosition(99, 99, 0.0)),
            ("next_position", first.position),  # in bounds, incorrect record
        )
        for field, value in candidates:
            with self.subTest(field=field, value=value):
                forged = replace(admitted, diagnostics=(replace(d, **{field: value}),))
                self.assertNotEqual(forged.to_json(), admitted.to_json())
                result = project_quality(forged, policy=policy)
                self.assertEqual(result.outcome, "quality_evidence_unavailable", result)
                self.assertIn("SOURCE_DIAGNOSTIC_POSITION_INVALID",
                              [issue.code for issue in result.issues])
                verified = verify_quality(projected.projection, forged, policy=policy)
                self.assertEqual(verified.outcome, "quality_evidence_unavailable", verified)
                self.assertIn("SOURCE_DIAGNOSTIC_POSITION_INVALID",
                              [issue.code for issue in verified.issues])


    def test_gpx_source_indices_reject_bool_and_float_equivalences(self):
        # Codex P2: source coordinates of *the record index itself* are part
        # of the M2A hash. Python SourceLocation equality accepts False==0
        # and 0.0==0, while canonical JSON differs.
        evidence = real_gpx((0, 0), (0.1, 0))
        from target_area_route_reconstruction.models import Diagnostic
        mapped = evidence.observation_sources[0]
        diagnostic = Diagnostic("TIMESTAMP_UNREPRESENTABLE", mapped.source, "timestamp",
                                None, mapped.position)
        with_diag = replace(evidence, diagnostics=(diagnostic,))
        policy = QualityPolicy()
        projection = project_quality(with_diag, policy=policy)
        self.assertEqual(projection.outcome, "produced", projection)
        for field in ("record_index", "track_index", "segment_index", "point_index"):
            for replacement in (False, 0.0):
                with self.subTest(field=field, value=repr(replacement)):
                    self.assertEqual(getattr(mapped.source, field), 0)
                    bad_source = replace(mapped.source, **{field: replacement})
                    self.assertEqual(bad_source, mapped.source)
                    bad_mapping = replace(with_diag, observation_sources=(
                        replace(mapped, source=bad_source),
                        *with_diag.observation_sources[1:]))
                    self.assertNotEqual(bad_mapping.to_json(), with_diag.to_json())
                    rejected_map = project_quality(bad_mapping, policy=policy)
                    self.assertEqual(rejected_map.outcome, "quality_evidence_unavailable", rejected_map)
                    self.assertIn("SOURCE_MAPPING_INVALID",
                                  [issue.code for issue in rejected_map.issues])
                    bad_diag = replace(with_diag, diagnostics=(
                        replace(diagnostic, source=bad_source),))
                    self.assertNotEqual(bad_diag.to_json(), with_diag.to_json())
                    rejected_diag = project_quality(bad_diag, policy=policy)
                    self.assertEqual(rejected_diag.outcome, "quality_evidence_unavailable", rejected_diag)
                    self.assertIn("SOURCE_DIAGNOSTIC_SOURCE_INVALID",
                                  [issue.code for issue in rejected_diag.issues])
                    self.assertEqual(
                        verify_quality(projection.projection, bad_diag, policy=policy).outcome,
                        "quality_evidence_unavailable")


    def test_source_snapshot_subclasses_cannot_extend_hashed_identity(self):
        # Codex P2: dataclass inheritance preserves canonical source indices,
        # but adds serialized fields to asdict() and therefore distinct SHA.
        from dataclasses import asdict, dataclass
        from target_area_route_reconstruction.models import (
            Diagnostic, IngestionResult, ObservationSource, SourceLocation,
        )

        @dataclass(frozen=True)
        class ForeignSource(SourceLocation):
            extra: str = "untrusted"

        @dataclass(frozen=True)
        class ForeignMapping(ObservationSource):
            extra: str = "untrusted"

        @dataclass(frozen=True)
        class ForeignDiagnostic(Diagnostic):
            extra: str = "untrusted"

        @dataclass(frozen=True)
        class ForeignEvidence(IngestionResult):
            extra: str = "untrusted"

        evidence = real_gpx((0, 0), (0.1, 0))
        mapping = evidence.observation_sources[0]
        fake_source = ForeignSource(**asdict(mapping.source))
        self.assertEqual([getattr(fake_source, key) for key in
                          ("record_index", "track_index", "segment_index", "point_index")],
                         [getattr(mapping.source, key) for key in
                          ("record_index", "track_index", "segment_index", "point_index")])
        diagnostic = Diagnostic("TIMESTAMP_UNREPRESENTABLE", mapping.source,
                                "timestamp", None, mapping.position)
        augmented = replace(evidence, diagnostics=(diagnostic,))
        self.assertEqual(project_quality(augmented, policy=QualityPolicy()).outcome, "produced")
        cases = (
            (replace(augmented, observation_sources=(
                replace(mapping, source=fake_source), *augmented.observation_sources[1:])),
             "SOURCE_MAPPING_INVALID"),
            (replace(augmented, observation_sources=(
                ForeignMapping(**asdict(mapping)), *augmented.observation_sources[1:])),
             "SOURCE_MAPPING_INVALID"),
            (replace(augmented, diagnostics=(ForeignDiagnostic(**asdict(diagnostic)),)),
             "SOURCE_DIAGNOSTIC_SOURCE_INVALID"),
            (ForeignEvidence(**asdict(augmented)), "QUALITY_EVIDENCE_INVALID"),
        )
        for changed, code in cases:
            with self.subTest(case=code, type=type(changed).__name__):
                self.assertNotEqual(changed.to_json(), augmented.to_json())
                result = project_quality(changed, policy=QualityPolicy())
                self.assertEqual(result.outcome, "quality_evidence_unavailable", result)
                self.assertIn(code, [issue.code for issue in result.issues])


if __name__ == "__main__":
    unittest.main()
