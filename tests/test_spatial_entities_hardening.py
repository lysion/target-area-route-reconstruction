"""PR #8 admission audit, including PR #9's original duplicate/one-ULP inputs.

The one-ULP input remains M1-lineage-valid. ADR-0012 explicitly chooses the
canonical-snapshot policy: it cannot reuse the original immutable revision.
"""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from shapely.geometry import shape

from target_area_route_reconstruction import (
    assemble_spatial_entities, verify_spatial_entities, prove_spatial_relation,
    QualityPolicy, ingest_bytes,
)
from target_area_route_reconstruction._m2d_common import canonical_json, schema_issues
from target_area_route_reconstruction.spatial_entities_models import SpatialEntityBundle
from test_spatial_relation import arguments, route, rectangle
from test_quality_projection import metric, POLICY, ROOT
from test_spatial_entities import M2DEntityTests as _ExistingWitnesses
from validate_semantic_fixtures import validate_segment_against_parent

# Do not import a TestCase as a module-level discoverable class (which would
# rerun its tests); retain only its helper functions.
_build = _ExistingWitnesses.build
_tamper = _ExistingWitnesses.tamper
del _ExistingWitnesses


class M2DAdmissionTests(unittest.TestCase):
    build = _build
    tamper = _tamper

    def setUp(self):
        self.args = arguments(route([(-1, 1), (3, 1)]))
        self.proof, self.result = self.build(self.args)
        self.bundle = self.result.bundle

    def reject(self, bundle, code, *, args=None, proof=None, path=None):
        result = verify_spatial_entities(bundle, proof=proof or self.proof,
                                         **(args or self.args))
        self.assertEqual(result.outcome, 'invalid', result)
        self.assertIn(code, [i.code for i in result.issues], result)
        if path is not None:
            self.assertIn((code, path), [(i.code, i.path) for i in result.issues])
        return result

    def test_pr9_duplicate_relation(self):
        bad = replace(self.bundle, assessment_json='{"relation":"outside",' + self.bundle.assessment_json[1:])
        self.reject(bad, 'M2D_DUPLICATE_JSON_MEMBER', path='assessment')

    def test_duplicate_members_recursive_and_identical(self):
        replacements = [
            ('assessment', '"parameters":{"identity_policy":', '"parameters":{"identity_policy":"forged","identity_policy":'),
            ('assessment', '"canonical_track":{', '"canonical_track":{"id":"forged",'),
            ('segment', '"geometry":{', '"geometry":{"type":"LineString",'),
            ('segment', '"start_position":{', '"start_position":{"observation_index":0,'),
            ('segment', '"ordinal":0', '"ordinal":0,"ordinal":0'),
            # Escaped and literal keys must be treated as the same key.
            ('assessment', '"relation":"partial"', '"relati\\u006fn":"outside","relation":"partial"'),
        ]
        for side, old, new in replacements:
            with self.subTest(side=side, old=old):
                raw = self.bundle.assessment_json if side == 'assessment' else self.bundle.segment_json[0]
                self.assertEqual(raw.count(old), 1)
                raw = raw.replace(old, new)
                bad = replace(self.bundle, **({'assessment_json': raw} if side == 'assessment' else {'segment_json': (raw,)}))
                self.reject(bad, 'M2D_DUPLICATE_JSON_MEMBER', path='assessment' if side == 'assessment' else 'segments/0')

    def test_pr9_one_ulp_is_semantic_not_snapshot_equivalence(self):
        segments = list(self.bundle.segments)
        point = segments[0]['geometry']['coordinates'][0]
        self.assertEqual(point, [0.0, 1.0])
        point[0] = math.nextafter(point[0], math.inf)
        self.assertEqual(validate_segment_against_parent(segments[0], self.args['evidence'].canonical_track,
                                                        shape(self.args['target_area']['geometry'])), [])
        check = self.reject(self.tamper(self.bundle, segments=segments), 'M2D_CANONICAL_SNAPSHOT_MISMATCH', path='segments/0')
        self.assertNotIn('M2D_GEOMETRY_REGEN_MISMATCH', [i.code for i in check.issues])

    def test_duplicate_member_in_later_segment_is_not_skipped(self):
        args = arguments(route([(-1,1),(3,1),(-1,1),(3,1)]))
        proof, result = self.build(args)
        raw = list(result.bundle.segment_json)
        self.assertEqual(len(raw), 3)
        raw[2] = '{"ordinal":999,' + raw[2][1:]
        self.reject(replace(result.bundle, segment_json=tuple(raw)),
                    'M2D_DUPLICATE_JSON_MEMBER', args=args, proof=proof, path='segments/2')

    def test_schema_legal_assessment_content_is_revision_bound(self):
        a = self.bundle.assessment
        a['extensions'] = {'org.example.audit': 'unbound content'}
        self.assertEqual(schema_issues('spatial-assessment', a), ())
        self.reject(self.tamper(self.bundle, assessment=a), 'M2D_CANONICAL_SNAPSHOT_MISMATCH', path='assessment')

    def test_schema_legal_segment_content_is_revision_bound(self):
        segments = list(self.bundle.segments)
        segments[0]['extensions'] = {'org.example.audit': {'new': True}}
        self.assertEqual(schema_issues('target-segment', segments[0]), ())
        self.reject(self.tamper(self.bundle, segments=segments), 'M2D_CANONICAL_SNAPSHOT_MISMATCH', path='segments/0')

    def test_syntax_whitespace_and_property_order_are_not_semantics(self):
        a = dict(reversed(list(self.bundle.assessment.items())))
        b = SpatialEntityBundle(json.dumps(a, indent=2), tuple(json.dumps(s, indent=2) for s in self.bundle.segments))
        self.assertEqual(verify_spatial_entities(b, proof=self.proof, **self.args).outcome, 'valid')
        self.assertEqual(b.to_json(), self.bundle.to_json())

    def test_numeric_payload_substitutions_cannot_reuse_revision(self):
        for value in (0, -0.0):
            with self.subTest(value=repr(value)):
                segments = list(self.bundle.segments)
                segments[0]['geometry']['coordinates'][0][0] = value
                self.reject(self.tamper(self.bundle, segments=segments), 'M2D_CANONICAL_SNAPSHOT_MISMATCH')
        segments = list(self.bundle.segments)
        segments[0]['ordinal'] = 0.0  # JSON Schema integer, but different canonical payload
        self.assertEqual(schema_issues('target-segment', segments[0]), ())
        self.reject(self.tamper(self.bundle, segments=segments), 'M2D_CANONICAL_SNAPSHOT_MISMATCH')

    def test_boolean_provenance_index_is_not_integer_zero(self):
        args = arguments(route([(-1, 1), (3, 1)], [(4, 1), (5, 1)]))
        proof, result = self.build(args)
        a = result.bundle.assessment
        a['coverage_uncertainties'][0]['provenance']['parameters']['gap_index'] = False
        self.reject(self.tamper(result.bundle, assessment=a), 'M2D_UNCERTAINTY_MISMATCH', args=args, proof=proof)

    def test_boolean_parent_index_fails_schema(self):
        segments = list(self.bundle.segments)
        segments[0]['start_position']['observation_index'] = False
        self.reject(self.tamper(self.bundle, segments=segments), 'M2D_ENTITY_SCHEMA_INVALID', path='segments/0')

    def test_nonfinite_json_is_rejected_before_semantics(self):
        for token in ('NaN', 'Infinity', '-Infinity', '1e9999', '-1e9999'):
            for side in ('assessment', 'segment'):
                with self.subTest(token=token, side=side):
                    if side == 'assessment':
                        bad = replace(self.bundle, assessment_json='{"extensions":{"probe":' + token + '},' + self.bundle.assessment_json[1:])
                    else:
                        bad = replace(self.bundle, segment_json=(self.bundle.segment_json[0].replace('"ordinal":0', '"ordinal":' + token),))
                    self.reject(bad, 'M2D_NONFINITE_JSON')

    def test_malformed_json_and_containers_fail_closed(self):
        for raw in ('{', '[' * 2000 + '0' + ']' * 2000, '"\\ud800"', 'null'):
            with self.subTest(raw=raw[:20]):
                self.reject(replace(self.bundle, assessment_json=raw), 'M2D_BUNDLE_MALFORMED')
        for changes in ({'segment_json': list(self.bundle.segment_json)}, {'assessment_json': self.bundle.assessment_json.encode()},
                        {'segment_json': (None,)}, {'segment_json': 'not a tuple'}):
            with self.subTest(changes=str(changes)[:50]):
                self.reject(replace(self.bundle, **changes), 'M2D_BUNDLE_MALFORMED')

    def test_unexpected_authority_and_verifier_failures_are_not_success(self):
        with patch('target_area_route_reconstruction.spatial_entities.verify_spatial_relation', side_effect=RuntimeError('engine failure')):
            result = assemble_spatial_entities(proof=self.proof, **self.args)
        self.assertEqual(result.outcome, 'invalid_input')
        self.assertIsNone(result.bundle)
        self.assertEqual([i.code for i in result.issues], ['M2D_AUTHORITY_CHECK_FAILED'])
        with patch('target_area_route_reconstruction.spatial_entities_verifier.regenerate', side_effect=RuntimeError('resource failure')):
            self.reject(self.bundle, 'M2D_VERIFICATION_FAILURE')
        with patch('target_area_route_reconstruction.spatial_entities.regenerate', side_effect=ValueError('unrepresentable')):
            result = assemble_spatial_entities(proof=self.proof, **self.args)
        self.assertEqual(result.outcome, 'assembly_failure')
        self.assertIsNone(result.bundle)
        self.assertEqual([i.code for i in result.issues], ['M2D_ASSEMBLY_NUMERICAL_OR_STRUCTURAL_FAILURE'])

    def test_type_sensitive_proof_metadata_gate(self):
        proof = replace(self.proof, algorithm=replace(self.proof.algorithm,
            parameters=replace(self.proof.algorithm.parameters, comparison_ulps=8.0)))
        result = assemble_spatial_entities(proof=proof, **self.args)
        self.assertEqual(result.outcome, 'invalid_input')
        self.assertEqual([i.code for i in result.issues], ['M2D_PROOF_METADATA_MISMATCH'])
        self.reject(self.bundle, 'M2D_PROOF_METADATA_MISMATCH', proof=proof)
        args = arguments(route([(-1, 1), (3, 1)], [(4, 1), (5, 1)]))
        proof, result = self.build(args)
        g = proof.gap_relevance[0]
        forged = replace(proof, gap_relevance=(replace(g, gap=replace(g.gap, start=replace(g.gap.start, part_index=False))),))
        # M2C now independently rejects invalid nested gap positions before
        # M2D can examine representation metadata or derive an assessment.
        self.reject(result.bundle, 'M2D_SPATIAL_PROOF_INVALID', args=args, proof=forged)

    def test_all_authority_changes_fail_before_assembly(self):
        alternatives = []
        bad = dict(self.args); bad['target_reference'] = replace(bad['target_reference'], revision_id='stale'); alternatives.append(bad)
        bad = dict(self.args); bad['target_area'] = copy.deepcopy(bad['target_area']); bad['target_area']['geometry']['coordinates'][0][1][0] += 0.1; alternatives.append(bad)
        bad = dict(self.args); bad['quality_projection'] = replace(bad['quality_projection'], usable_intervals=()); alternatives.append(bad)
        bad = dict(self.args); bad['quality_policy'] = QualityPolicy(max_implied_speed_mps=5); alternatives.append(bad)
        bad = dict(self.args); bad['evidence'] = route([(-1, 1), (4, 1)]); alternatives.append(bad)
        for args in alternatives:
            with self.subTest(args=str(args)[:80]):
                with patch('target_area_route_reconstruction.spatial_entities._assemble', side_effect=AssertionError('must not assemble')):
                    result = assemble_spatial_entities(proof=self.proof, **args)
                self.assertEqual(result.outcome, 'invalid_input')
                self.assertEqual(result.issues[0].code, 'M2D_SPATIAL_PROOF_INVALID')
                self.reject(self.bundle, 'M2D_SPATIAL_PROOF_INVALID', args=args)

    def test_geometry_order_internal_vertices_and_tiny_geometry(self):
        for points in ([(.2, .2), (.3, .4), (.5, .3)], [(0, 0), (1e-200, 0)], [(0, 0), (5e-13, 0)]):
            with self.subTest(points=points):
                args = arguments(route(points), rectangle(-1, -1, 1, 1))
                proof, result = self.build(args)
                self.assertEqual(result.bundle.segments[0]['geometry']['coordinates'], [list(p) for p in points])
                for coordinates in (list(reversed([list(p) for p in points])), [list(points[0]), list(points[0])]):
                    segs = list(result.bundle.segments); segs[0]['geometry']['coordinates'] = coordinates
                    self.reject(self.tamper(result.bundle, segments=segs), 'M2D_GEOMETRY_REGEN_MISMATCH', args=args, proof=proof)
        args = arguments(route([(.2, .2), (.3, .4), (.5, .3)])); proof, result = self.build(args)
        segs = list(result.bundle.segments); del segs[0]['geometry']['coordinates'][1]
        self.reject(self.tamper(result.bundle, segments=segs), 'M2D_GEOMETRY_REGEN_MISMATCH', args=args, proof=proof)

    def test_nonmaximal_split_and_shortened_fraction(self):
        s = self.bundle.segments[0]
        first, second = copy.deepcopy(s), copy.deepcopy(s)
        first['end_position']['fraction_to_next'] = .5
        second['start_position']['fraction_to_next'] = .5
        second['ordinal'] = 1
        self.reject(self.tamper(self.bundle, segments=[first, second]), 'M2D_TARGET_COVERAGE_NOT_EXHAUSTIVE')
        first = copy.deepcopy(s); first['end_position']['fraction_to_next'] = .6
        self.reject(self.tamper(self.bundle, segments=[first]), 'M2D_MAXIMALITY_OR_LINEAGE_MISMATCH')

    def test_reordering_overlap_dedup_and_cross_source_gap_merge(self):
        for args in (arguments(route([(-1, 1), (3, 1), (-1, 1)])),
                     arguments(route([(.2, 1), (1.5, 1)], [(.2, 1), (1.5, 1)]))):
            proof, result = self.build(args)
            segs = list(result.bundle.segments)
            self.assertEqual(len(segs), 2)
            self.reject(self.tamper(result.bundle, segments=list(reversed(segs))), 'M2D_MAXIMALITY_OR_LINEAGE_MISMATCH', args=args, proof=proof)
            self.reject(self.tamper(result.bundle, segments=[segs[0]]), 'M2D_TARGET_COVERAGE_NOT_EXHAUSTIVE', args=args, proof=proof)
            overlap = copy.deepcopy(segs); overlap[1]['start_position'] = overlap[0]['start_position']
            self.reject(self.tamper(result.bundle, segments=overlap), 'M2D_MAXIMALITY_OR_LINEAGE_MISMATCH', args=args, proof=proof)
            merged = copy.deepcopy(segs[0]); merged['end_position'] = segs[1]['end_position']
            self.reject(self.tamper(result.bundle, segments=[merged]), 'M2D_TARGET_COVERAGE_NOT_EXHAUSTIVE', args=args, proof=proof)

    def test_quality_gap_merge_and_incomplete_shortening(self):
        args = arguments(metric('gps-jump'), rectangle(-180, -90, 180, 90), POLICY)
        proof, result = self.build(args)
        segs = list(result.bundle.segments)
        self.assertGreaterEqual(len(segs), 2)
        self.assertEqual(result.bundle.assessment['coverage_completeness'], 'incomplete')
        merged = copy.deepcopy(segs[0]); merged['end_position'] = segs[-1]['end_position']
        self.reject(self.tamper(result.bundle, segments=[merged]), 'M2D_TARGET_COVERAGE_NOT_EXHAUSTIVE', args=args, proof=proof)
        segs[0]['end_position'] = copy.deepcopy(segs[0]['start_position'])
        self.reject(self.tamper(result.bundle, segments=segs), 'M2D_MAXIMALITY_OR_LINEAGE_MISMATCH', args=args, proof=proof)

    def test_uncertainty_exactness_including_open_ends(self):
        for side in ('leading', 'trailing'):
            evidence = ingest_bytes((ROOT / f'tests/m2d-contract/{side}-gap.gpx').read_bytes(), source_kind='gpx', track_source={'id':'source','revision_id':'r1'})
            args = arguments(evidence); proof, result = self.build(args)
            a = result.bundle.assessment
            original = copy.deepcopy(a['coverage_uncertainties'])
            for uncertainties in ([], original * 2):
                a['coverage_uncertainties'] = uncertainties
                code = 'M2D_ENTITY_SCHEMA_INVALID'  # required / uniqueItems
                self.reject(self.tamper(result.bundle, assessment=a), code, args=args, proof=proof)
            a['coverage_uncertainties'] = original
            r = a['coverage_uncertainties'][0]['affected_track_range']; r['start'], r['end'] = r['end'], r['start']
            self.reject(self.tamper(result.bundle, assessment=a), 'M2D_UNCERTAINTY_MISMATCH', args=args, proof=proof)

    def test_relation_completeness_and_nonassessable_forgery(self):
        for field, value in (('relation', 'inside'), ('coverage_completeness', 'incomplete')):
            a = self.bundle.assessment; a[field] = value
            code = 'M2D_RELATION_OR_COMPLETENESS_CHANGED' if field == 'relation' else 'M2D_ENTITY_SCHEMA_INVALID'
            self.reject(self.tamper(self.bundle, assessment=a), code)
        args = arguments(route([(1, 1)])); proof, result = self.build(args)
        self.reject(self.bundle, 'M2D_NONASSESSABLE_ENTITIES', args=args, proof=proof)
        for forged in (replace(self.proof, relation='outside'), replace(self.proof, coverage_completeness='incomplete')):
            self.reject(self.bundle, 'M2D_SPATIAL_PROOF_INVALID', proof=forged)

    def test_complete_cannot_carry_extra_uncertainty(self):
        args = arguments(route([(-1,1),(3,1)],[(4,1),(5,1)])); _, r = self.build(args)
        a = self.bundle.assessment; a['coverage_uncertainties'] = r.bundle.assessment['coverage_uncertainties']
        self.reject(self.tamper(self.bundle, assessment=a), 'M2D_ENTITY_SCHEMA_INVALID')

    def test_identity_changes_with_evidence_and_target_content(self):
        outcomes = [self.bundle]
        for args in (arguments(route([(-1,1),(4,1)])), arguments(route([(-1,1),(3,1)]), rectangle(0,0,1,2)),
                     arguments(route([(-1,1),(3,1)]), policy=QualityPolicy(include_domain_bounds=True))):
            _, result = self.build(args); outcomes.append(result.bundle)
        self.assertEqual(len({b.assessment['revision_id'] for b in outcomes}), 4)
        for b in outcomes[1:]:
            self.reject(b, 'M2D_ALGORITHM_MISMATCH')

    def test_forged_bidirectional_identity_is_rejected(self):
        a = self.bundle.assessment; segs = list(self.bundle.segments)
        a['revision_id'] = 'forged'; segs[0]['spatial_assessment']['revision_id'] = 'forged'
        segs[0]['revision_id'] = 'forged-segment'; a['target_segment_refs'][0]['revision_id'] = 'forged-segment'
        self.reject(self.tamper(self.bundle, assessment=a, segments=segs), 'M2D_ASSESSMENT_IDENTITY_MISMATCH')

    def test_verifier_does_not_call_producer(self):
        with patch('target_area_route_reconstruction.spatial_entities._assemble', side_effect=AssertionError('producer forbidden')):
            self.assertEqual(verify_spatial_entities(self.bundle, proof=self.proof, **self.args).outcome, 'valid')
            self.reject(self.tamper(self.bundle, segments=[]), 'M2D_TARGET_COVERAGE_NOT_EXHAUSTIVE')

    def test_nonzero_json_underflow_is_not_silently_zero(self):
        raw = self.bundle.segment_json[0].replace('"coordinates":[[0.0,', '"coordinates":[[1e-9999,')
        self.assertNotEqual(raw, self.bundle.segment_json[0])
        self.reject(replace(self.bundle, segment_json=(raw,)), 'M2D_JSON_NUMBER_UNREPRESENTABLE')

    def test_original_evidence_and_proof_remain_unchanged(self):
        evidence, quality = self.args['evidence'], self.args['quality_projection']
        snapshots = (evidence.to_json(), quality.to_json(), self.proof.to_json(), canonical_json(self.args['target_area']))
        self.build(self.args)
        self.assertEqual(snapshots, (evidence.to_json(), quality.to_json(), self.proof.to_json(), canonical_json(self.args['target_area'])))
        detached = self.bundle.assessment
        detached['relation'] = 'outside'
        self.assertEqual(self.bundle.assessment['relation'], 'partial')

    def test_wrong_track_revision_even_when_geometry_unchanged(self):
        args = dict(self.args)
        evidence = copy.deepcopy(args['evidence']); evidence.canonical_track['revision_id'] = 'wrong-revision'
        args['evidence'] = evidence
        self.reject(self.bundle, 'M2D_SPATIAL_PROOF_INVALID', args=args)
        result = assemble_spatial_entities(proof=self.proof, **args)
        self.assertEqual(result.outcome, 'invalid_input')
        self.assertIsNone(result.bundle)

    def test_invalid_target_topology_and_unusable_source_fail_closed(self):
        for invalid in (None, True, {}, {'geometry': {'type': 'Point', 'coordinates': [0,0]}}):
            args = dict(self.args); args['target_area'] = invalid
            self.reject(self.bundle, 'M2D_SPATIAL_PROOF_INVALID', args=args)
        area = rectangle(); area['geometry']['coordinates'] = [[[0,0],[2,2],[0,2],[2,0],[0,0]]]
        args = dict(self.args); args['target_area'] = area
        self.reject(self.bundle, 'M2D_SPATIAL_PROOF_INVALID', args=args)
        for filename, kind in (('fit/no-position.fit', 'fit'), ('gpx/malformed.gpx', 'gpx')):
            args = dict(self.args)
            args['evidence'] = ingest_bytes((ROOT / 'tests/source-fixtures' / filename).read_bytes(), source_kind=kind,
                                           track_source={'id':'none','revision_id':'r1'})
            result = assemble_spatial_entities(proof=self.proof, **args)
            self.assertEqual(result.outcome, 'invalid_input')
            self.assertIsNone(result.bundle)

    def test_fit_missing_runs_keep_exact_diagnostic_provenance(self):
        from datetime import datetime, timedelta, timezone
        from generate_synthetic_source_fixtures import build_fit
        start = datetime(2026,10,7,tzinfo=timezone.utc)
        points = [None, (.1,.1), (.2,.1), None, None, (.3,.1), (.4,.1), None]
        records = [(start + timedelta(seconds=i), xy[1] if xy else None, xy[0] if xy else None) for i, xy in enumerate(points)]
        evidence = ingest_bytes(build_fit(records), source_kind='fit', track_source={'id':'fit-gaps','revision_id':'r1'})
        args = arguments(evidence)
        proof, result = self.build(args)
        self.assertEqual(len(result.bundle.segments), 2)
        uncertainties = result.bundle.assessment['coverage_uncertainties']
        self.assertEqual(len(uncertainties), 3)
        self.assertIsNone(uncertainties[0]['affected_track_range']['start'])
        self.assertIsNone(uncertainties[-1]['affected_track_range']['end'])
        self.assertEqual([u['provenance']['parameters']['gap_diagnostic_indices'] for u in uncertainties], [[0],[1,2],[3]])
        a = result.bundle.assessment
        a['coverage_uncertainties'][1]['provenance']['parameters']['gap_diagnostic_indices'] = [1]
        self.reject(self.tamper(result.bundle, assessment=a), 'M2D_UNCERTAINTY_MISMATCH', args=args, proof=proof)

    def test_target_irrelevant_gap_branch_is_not_a_new_proof_method(self):
        # No supported local-disjoint bound currently exists in M2B. Exercise
        # the conversion predicate separately, and reject this forged public
        # proof rather than pretending to have a valid integration witness.
        from target_area_route_reconstruction.spatial_entities import _uncertainties
        from target_area_route_reconstruction.spatial_entities_verifier import _expected_uncertainties
        args = arguments(route([(-1,1),(3,1)],[(4,1),(5,1)]))
        proof, result = self.build(args)
        forged = replace(proof, gap_relevance=(replace(proof.gap_relevance[0], target_coverage_unresolved=False,
                                                     bound_relation='disjoint', possible_outside=True),))
        self.assertEqual(_uncertainties(forged), [])
        self.assertEqual(_expected_uncertainties(forged), [])
        self.reject(result.bundle, 'M2D_SPATIAL_PROOF_INVALID', args=args, proof=forged)

    def test_inside_partial_without_refs_and_outside_with_refs(self):
        for relation, refs in (('inside', []), ('partial', []), ('outside', self.bundle.assessment['target_segment_refs'])):
            a = self.bundle.assessment; a['relation'] = relation; a['target_segment_refs'] = refs
            self.reject(self.tamper(self.bundle, assessment=a), 'M2D_ENTITY_SCHEMA_INVALID')

    def test_diagonal_clipping_preserves_interpolated_lineage(self):
        args = arguments(route([(-.7,-.3),(1.3,1.7)]), rectangle(0,0,1,1))
        proof, result = self.build(args)
        self.assertEqual(len(result.bundle.segments), 1)
        segment = result.bundle.segments[0]
        self.assertEqual(validate_segment_against_parent(segment, args['evidence'].canonical_track,
                                                        shape(args['target_area']['geometry'])), [])
        self.assertGreater(segment['start_position']['fraction_to_next'], 0)
        self.assertLess(segment['end_position']['fraction_to_next'], 1)

    def test_admission_mutations_are_assertion_killed(self):
        import target_area_route_reconstruction as package
        mutations = [
            ('_m2d_common.py', '            if key in result:', '            if False and key in result:', 'test_pr9_duplicate_relation'),
            ('_m2d_common.py', 'raise BundleJSONError("M2D_DUPLICATE_JSON_MEMBER")', 'raise BundleJSONError("M2D_NONFINITE_JSON")', 'test_pr9_duplicate_relation'),
            ('spatial_entities_verifier.py', 'if canonical_json(assessment) != canonical_json(expected_assessment):', 'if False:', 'test_schema_legal_assessment_content_is_revision_bound'),
            ('spatial_entities_verifier.py', 'if canonical_json(item) != canonical_json(expected_segment):', 'if False:', 'test_schema_legal_segment_content_is_revision_bound'),
            ('spatial_entities_verifier.py', 'if not geometry_matches_parent(item["geometry"], info["geometry"], evidence.canonical_track):', 'if item["geometry"] != info["geometry"]:', 'test_pr9_one_ulp_is_semantic_not_snapshot_equivalence'),
            ('_m2d_common.py', 'if value == 0 and Decimal(number) != 0:', 'if False:', 'test_nonzero_json_underflow_is_not_silently_zero'),
            ('spatial_entities.py', 'if not exact_proof_metadata(proof, quality_projection):', 'if False:', 'test_type_sensitive_proof_metadata_gate'),
        ]
        for filename, old, new, witness in mutations:
            with self.subTest(witness=witness, mutation=new):
                source = (Path(package.__file__).parent / filename).read_text()
                self.assertEqual(source.count(old), 1)
                with tempfile.TemporaryDirectory() as directory:
                    destination = Path(directory) / 'target_area_route_reconstruction'
                    shutil.copytree(Path(package.__file__).parent, destination, ignore=shutil.ignore_patterns('__pycache__'))
                    (destination / filename).write_text(source.replace(old, new))
                    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE':'1', 'PYTHONPATH':os.pathsep.join((directory, str(ROOT / 'tests')))}
                    run = subprocess.run([sys.executable, '-m', 'unittest', 'test_spatial_entities_hardening.M2DAdmissionTests.' + witness],
                                         env=env, capture_output=True, text=True, timeout=40)
                    self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                    self.assertIn('AssertionError', run.stderr)
                    self.assertIn('Ran 1 test', run.stderr)
                    self.assertNotIn('FAILED (errors=', run.stderr)


if __name__ == '__main__':
    unittest.main()
