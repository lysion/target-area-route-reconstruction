"""R3 P1/P2 defects discovered by the exact-head remote full-repository audit.

Runs real GPX ingestion and public producer/verifier APIs. The six geometry
cases use a separate exact Fraction witness for the positive-width strip.
"""
from __future__ import annotations

import math
import unittest
from dataclasses import asdict, make_dataclass, replace, fields
from decimal import Decimal
from fractions import Fraction

from target_area_route_reconstruction import (
    QualityPolicy, TrackPosition, ingest_bytes, project_quality,
    prove_spatial_relation, verify_quality, verify_spatial_relation,
    assemble_spatial_entities,
)
from target_area_route_reconstruction.quality_models import ParentReference, QualityProjection


def source(*parts):
    def xml(x):
        return format(Decimal(str(x)), 'f')
    segs = ''.join('<trkseg>' + ''.join(
        f'<trkpt lon="{xml(x)}" lat="{xml(y)}"/>' for x, y in points
    ) + '</trkseg>' for points in parts)
    raw = ('<gpx version="1.1" creator="r3" xmlns="http://www.topografix.com/GPX/1/1">'
           '<trk>' + segs + '</trk></gpx>').encode()
    data = ingest_bytes(raw, source_kind='gpx',
                        track_source={'id': 'r3-regression', 'revision_id': 'r1'})
    assert data.outcome == 'success', data
    return data


def ring(a, b, c, d):
    return [[a,b],[c,b],[c,d],[a,d],[a,b]]


def target(polygons, multi=False):
    return dict(schema_version='0.1.0', id='r3-target', revision_id='r1',
                spatial_reference='OGC:CRS84',
                definition_provenance={'description':'R3 exact numerical regression'},
                geometry={'type':'MultiPolygon' if multi else 'Polygon',
                          'coordinates':polygons})


def arguments(evidence, area, policy=None):
    policy = policy or QualityPolicy()
    quality = project_quality(evidence, policy=policy)
    assert quality.outcome == 'produced', quality
    return dict(evidence=evidence, quality_projection=quality.projection,
                quality_policy=policy, target_area=area,
                target_reference=ParentReference(area['id'], area['revision_id']))


def subclassed(original):
    kind = type(original)
    extra = make_dataclass('Extended' + kind.__name__,
                           [('untrusted_extension', str, 'outside contract')],
                           bases=(kind,), frozen=True)
    return extra(**{f.name:getattr(original,f.name) for f in fields(original)})


class R3Correctness(unittest.TestCase):
    def test_six_silent_geos_failures_cannot_be_accepted(self):
        ev = source([(-1,0), (1,0)])
        for scale in (1e-154, 1e-160):
            near = math.nextafter(scale, math.inf)
            left = (Fraction(scale) + 1) / 2
            right = (Fraction(near) + 1) / 2
            self.assertLess(left, right)  # exact positive intersection
            examples = {
                'strip': target([ring(scale,-scale,near,scale)]),
                'hole': target([ring(-2,-2,2,2), ring(scale,-scale,near,scale)]),
                'multi': target([[ring(scale,-scale,near,scale)],
                                 [ring(-1.9,.5,-1.8,.6)]], multi=True),
            }
            for name, area in examples.items():
                with self.subTest(scale=scale, shape=name):
                    result = prove_spatial_relation(**arguments(ev,area))
                    self.assertEqual(result.outcome, 'numerical_failure', result)
                    self.assertIsNone(result.proof)
                    self.assertTrue(any(issue.code.startswith('SPATIAL_') for issue in result.issues))

    def test_normal_crossing_and_positive_subnormal_edge_survive(self):
        area = target([ring(-1,-1,1,1)])
        for points, relation in (([(-2,0),(2,0)], 'partial'),
                                  ([(0,0),(5e-324,0)], 'inside')):
            with self.subTest(points=points):
                args = arguments(source(points),area)
                result = prove_spatial_relation(**args)
                self.assertEqual(result.outcome, 'produced', result)
                self.assertEqual(result.proof.relation,relation)
                self.assertEqual(verify_spatial_relation(result.proof, **args).outcome,'valid')

    def test_closed_quality_snapshot_types_and_numeric_spellings(self):
        ev = source([(0,0),(.1,0),(.2,0)],[(.3,0),(.4,0)])
        policy = QualityPolicy(include_domain_bounds=True)
        area = target([ring(-1,-1,1,1)])
        args = arguments(ev,area,policy)
        baseline = args['quality_projection']
        self.assertEqual(verify_quality(baseline,ev,policy=policy).outcome,'valid')
        span = baseline.usable_intervals[0]
        constraint = baseline.gap_constraints[0]
        scenarios = (
            replace(baseline,usable_intervals=(subclassed(span),*baseline.usable_intervals[1:])),
            subclassed(baseline),
            replace(baseline,gaps=(subclassed(baseline.gaps[0]),*baseline.gaps[1:])),
            replace(baseline,gap_constraints=(replace(constraint,bound=subclassed(constraint.bound)),
                                                      *baseline.gap_constraints[1:])),
            replace(baseline,gap_constraints=(replace(constraint,bound=replace(constraint.bound,
                                                      bbox=(-180,-90,180,90))),
                                                      *baseline.gap_constraints[1:])),
        )
        for changed in scenarios:
            with self.subTest(claim=type(changed).__name__, json=changed.to_json()[:80]):
                self.assertNotEqual(changed.to_json(),baseline.to_json())
                self.assertEqual(verify_quality(changed,ev,policy=policy).outcome,'invalid')
                denial=prove_spatial_relation(**{**args,'quality_projection':changed})
                self.assertNotEqual(denial.outcome,'produced')
                self.assertIsNone(denial.proof)

    def test_spatial_proof_subclasses_rejected_at_m2c_and_m2d(self):
        ev = source([(0,0),(.1,0)],[(.2,0),(.3,0)])
        args = arguments(ev,target([ring(-1,-1,1,1)]))
        produced = prove_spatial_relation(**args)
        self.assertEqual(produced.outcome,'produced')
        self.assertEqual(verify_spatial_relation(produced.proof,**args).outcome,'valid')
        relevance = produced.proof.gap_relevance[0]
        for proof in (subclassed(produced.proof),
                      replace(produced.proof,gap_relevance=(subclassed(relevance),))):
            self.assertEqual(verify_spatial_relation(proof,**args).outcome,'invalid')
            self.assertNotEqual(assemble_spatial_entities(proof=proof,**args).outcome,'produced')

    def test_nested_gap_integer_spelling_cannot_alias_serialized_proof(self):
        # Exact-head Codex P2: False == 0 == 0.0 in Python dataclass
        # equality, but each has a different JSON value/digest. Validate
        # at both the M2B parent and the independently copied M2C gap.
        from pathlib import Path
        from target_area_route_reconstruction import ingest_file
        from dataclasses import replace

        evidence = ingest_file(
            Path(__file__).parent / 'source-fixtures/gpx/discontinuity.gpx',
            source_kind='gpx',
            track_source={'id': 'r3-p2-source-gap', 'revision_id': 'r1'})
        self.assertEqual(evidence.outcome, 'success')
        policy = QualityPolicy()
        args = arguments(evidence, target([ring(-180, -90, 180, 90)]), policy)
        quality = args['quality_projection']
        self.assertEqual(verify_quality(quality, evidence, policy=policy).outcome, 'valid')
        spatial = prove_spatial_relation(**args)
        self.assertEqual(spatial.outcome, 'produced', spatial)
        self.assertEqual(verify_spatial_relation(spatial.proof, **args).outcome, 'valid')

        gap_idx = next(i for i, gap in enumerate(quality.gaps)
                       if gap.diagnostic_indices and gap.diagnostic_indices[0] == 0)
        base_gap = quality.gaps[gap_idx]
        base_rel = spatial.proof.gap_relevance[gap_idx]
        for spelling in (False, 0.0):
            with self.subTest(field='diagnostic_indices', spelling=repr(spelling)):
                changed = replace(base_gap, diagnostic_indices=(
                    spelling, *base_gap.diagnostic_indices[1:]))
                self.assertEqual(changed, base_gap)
                wrong_quality = replace(quality, gaps=(
                    *quality.gaps[:gap_idx], changed, *quality.gaps[gap_idx + 1:]))
                self.assertNotEqual(wrong_quality.to_json(), quality.to_json())
                self.assertEqual(
                    verify_quality(wrong_quality, evidence, policy=policy).outcome, 'invalid')
                self.assertNotEqual(prove_spatial_relation(**{
                    **args, 'quality_projection': wrong_quality}).outcome, 'produced')

                bad_rel = replace(base_rel, gap=changed)
                bad_proof = replace(spatial.proof, gap_relevance=(
                    *spatial.proof.gap_relevance[:gap_idx], bad_rel,
                    *spatial.proof.gap_relevance[gap_idx + 1:]))
                self.assertEqual(bad_rel, base_rel)
                self.assertNotEqual(bad_proof.to_json(), spatial.proof.to_json())
                checked = verify_spatial_relation(bad_proof, **args)
                self.assertEqual(checked.outcome, 'invalid', checked)
                self.assertIn('SPATIAL_PROOF_MALFORMED',
                              {issue.code for issue in checked.issues})
                denied = assemble_spatial_entities(proof=bad_proof, **args)
                self.assertNotEqual(denied.outcome, 'produced', denied)

    def test_quality_exclusion_index_has_one_integer_identity(self):
        # Even an internally equal quality gap cannot carry a bool/float
        # alternative to the integer excluded_interval_index.
        raw = (
            '<gpx version="1.1" creator="r3" xmlns="http://www.topografix.com/GPX/1/1">'
            '<trk><trkseg>'
            '<trkpt lon="0" lat="0"><time>2026-10-07T00:00:00Z</time></trkpt>'
            '<trkpt lon="0.00001" lat="0"><time>2026-10-07T00:01:00Z</time></trkpt>'
            '<trkpt lon="0.1" lat="0"><time>2026-10-07T00:01:01Z</time></trkpt>'
            '</trkseg></trk></gpx>').encode()
        evidence = ingest_bytes(raw, source_kind='gpx',
                                track_source={'id': 'r3-p2-quality-gap', 'revision_id': 'r1'})
        self.assertEqual(evidence.outcome, 'success')
        policy = QualityPolicy(max_implied_speed_mps=10.0)
        args = arguments(evidence, target([ring(-1, -1, 1, 1)]), policy)
        quality = args['quality_projection']
        self.assertEqual(verify_quality(quality, evidence, policy=policy).outcome, 'valid')
        gap_idx = next(i for i, gap in enumerate(quality.gaps)
                       if gap.kind == 'quality_exclusion' and gap.excluded_interval_index == 0)
        original = quality.gaps[gap_idx]
        spatial = prove_spatial_relation(**args)
        self.assertEqual(spatial.outcome, 'produced', spatial)
        self.assertEqual(verify_spatial_relation(spatial.proof, **args).outcome, 'valid')
        for spelling in (False, 0.0):
            with self.subTest(spelling=repr(spelling)):
                changed = replace(original, excluded_interval_index=spelling)
                self.assertEqual(changed, original)
                wrong = replace(quality, gaps=tuple(
                    changed if index == gap_idx else gap
                    for index, gap in enumerate(quality.gaps)))
                self.assertNotEqual(wrong.to_json(), quality.to_json())
                self.assertEqual(verify_quality(wrong, evidence, policy=policy).outcome,
                                 'invalid')
                bad_rel = replace(spatial.proof.gap_relevance[gap_idx], gap=changed)
                proof = replace(spatial.proof, gap_relevance=tuple(
                    bad_rel if index == gap_idx else item
                    for index, item in enumerate(spatial.proof.gap_relevance)))
                self.assertNotEqual(proof.to_json(), spatial.proof.to_json())
                verified = verify_spatial_relation(proof, **args)
                self.assertEqual(verified.outcome, 'invalid', verified)
                self.assertIn('SPATIAL_PROOF_MALFORMED',
                              {issue.code for issue in verified.issues})
                self.assertNotEqual(assemble_spatial_entities(proof=proof, **args).outcome,
                                    'produced')

    def test_bypassed_policy_constructor_cannot_create_second_identity(self):
        ev=source([(0,0),(.001,0)])
        policy=QualityPolicy(max_implied_speed_mps=1.0)
        args=arguments(ev,target([ring(-1,-1,1,1)]),policy)
        q=args['quality_projection']
        forged=object.__new__(QualityPolicy)
        object.__setattr__(forged,'max_implied_speed_mps',1)
        object.__setattr__(forged,'include_domain_bounds',False)
        altered=replace(q,algorithm=replace(q.algorithm,parameters=replace(q.algorithm.parameters,policy=forged)))
        self.assertEqual(verify_quality(altered,ev,policy=policy).outcome,'invalid')
        self.assertNotEqual(prove_spatial_relation(**{**args,'quality_projection':altered}).outcome,'produced')


if __name__ == '__main__':
    unittest.main()
