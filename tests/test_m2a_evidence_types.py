"""Independent M2A declaration/JSON admission witnesses for R3 D-01.

Expectations come from the public model/JSON contract, not the producer's
canonical matcher. Real GPX bytes supply the baseline warning and lineage.
"""
import copy
import json
import math
import unittest
from dataclasses import fields, make_dataclass, replace
from unittest.mock import patch

from target_area_route_reconstruction import (
    Diagnostic, IngestionResult, ObservationSource, SourceLocation, TrackPosition,
    QualityPolicy, ingest_bytes, project_quality, verify_quality,
    prove_spatial_relation, verify_spatial_relation, assemble_spatial_entities,
    verify_spatial_entities, export_temporal_geojson,
)
from target_area_route_reconstruction.quality_models import ParentReference
from target_area_route_reconstruction._quality_evidence import evidence_digest


class ForeignString(str):
    pass


class ForeignDict(dict):
    pass


def extended(value):
    model = make_dataclass('Extended' + type(value).__name__,
                           [('unbound', str, 'extra')], bases=(type(value),), frozen=True)
    return model(**{field.name: getattr(value, field.name) for field in fields(value)})


class SourceEvidenceTypeRegression(unittest.TestCase):
    def setUp(self):
        self.raw = (
            '<gpx version="1.1" creator="d01-independent" '
            'xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>'
            '<trkpt lon="0" lat="0"><time>2026-01-01T00:00:00</time></trkpt>'
            '<trkpt lon="0.1" lat="0"><time>2026-01-01T00:01:00Z</time></trkpt>'
            '</trkseg></trk></gpx>').encode()
        self.evidence = ingest_bytes(self.raw, source_kind='gpx',
                                     track_source={'id': 'd01-independent', 'revision_id': 'r1'})
        self.assertEqual(self.evidence.outcome, 'success')
        self.assertEqual(len(self.evidence.diagnostics), 1)
        self.warning = self.evidence.diagnostics[0]
        self.assertEqual(self.warning.code, 'TIMESTAMP_TIMEZONE_MISSING')
        self.policy = QualityPolicy()
        self.quality = project_quality(self.evidence, policy=self.policy).projection
        self.target = dict(schema_version='0.1.0', id='d01-target', revision_id='r1',
                           spatial_reference='OGC:CRS84',
                           definition_provenance={'description': 'D-01 contract control'},
                           geometry={'type': 'Polygon', 'coordinates': [[
                               [-1., -1.], [1., -1.], [1., 1.], [-1., 1.], [-1., -1.]]]})
        self.args = dict(evidence=self.evidence, quality_projection=self.quality,
                         quality_policy=self.policy, target_area=self.target,
                         target_reference=ParentReference('d01-target', 'r1'))
        self.proof = prove_spatial_relation(**self.args).proof
        self.bundle = assemble_spatial_entities(proof=self.proof, **self.args).bundle
        self.assertIsNotNone(self.bundle)

    def rejected(self, evidence, code=None):
        # Malformed source snapshots must never reach ANY hash computation.
        with patch('target_area_route_reconstruction._quality_evidence.digest',
                   side_effect=AssertionError('malformed input reached a hash')):
            projected = project_quality(evidence, policy=self.policy)
            self.assertEqual(projected.outcome, 'quality_evidence_unavailable', projected)
            self.assertIsNone(projected.projection)
            verified = verify_quality(self.quality, evidence, policy=self.policy)
            self.assertNotEqual(verified.outcome, 'valid', verified)
            if code:
                self.assertIn(code, {issue.code for issue in projected.issues})
            with self.assertRaisesRegex(ValueError, 'QUALITY_EVIDENCE_INVALID'):
                evidence_digest(evidence)
            args = {**self.args, 'evidence': evidence}
            spatial = prove_spatial_relation(**args)
            self.assertNotEqual(spatial.outcome, 'produced', spatial)
            self.assertIsNone(spatial.proof)
            self.assertEqual(verify_spatial_relation(self.proof, **args).outcome, 'invalid')
            self.assertIsNone(assemble_spatial_entities(proof=self.proof, **args).bundle)
            self.assertEqual(verify_spatial_entities(self.bundle, proof=self.proof,
                                                    **args).outcome, 'invalid')
            export = export_temporal_geojson(bundle=self.bundle, proof=self.proof, **args)
            self.assertNotEqual(export.outcome, 'produced')
            self.assertIsNone(export.geojson_json)

    def test_numeric_aliases_of_diagnostic_fields_cannot_create_identity(self):
        for field in ('code', 'field'):
            for value in (False, 0, 0.0, -0.0, True, 1, 1.0):
                with self.subTest(field=field, value=repr(value)):
                    self.rejected(replace(self.evidence, diagnostics=(
                        replace(self.warning, **{field: value}),)), 'SOURCE_DIAGNOSTIC_TYPE_INVALID')

    def test_other_wrong_primitive_types_are_rejected_before_hashing(self):
        for field in ('code', 'field'):
            for value in ([], {}, math.nan, math.inf, self.warning,
                          ForeignString(getattr(self.warning, field))):
                with self.subTest(field=field, value=repr(value)):
                    self.rejected(replace(self.evidence, diagnostics=(
                        replace(self.warning, **{field: value}),)), 'SOURCE_DIAGNOSTIC_TYPE_INVALID')
        self.rejected(replace(self.evidence, diagnostics=(
            replace(self.warning, code=None),)), 'SOURCE_DIAGNOSTIC_TYPE_INVALID')

    def test_dataclass_extensions_and_unrelated_instances_are_rejected(self):
        first = self.evidence.observation_sources[0]
        self.rejected(extended(self.evidence), 'QUALITY_EVIDENCE_INVALID')
        for diagnostic in (extended(self.warning), first, {'code': self.warning.code}):
            self.rejected(replace(self.evidence, diagnostics=(diagnostic,)),
                          'SOURCE_DIAGNOSTIC_SOURCE_INVALID')
        self.rejected(replace(self.evidence, observation_sources=(
            extended(first), *self.evidence.observation_sources[1:])), 'SOURCE_MAPPING_INVALID')
        self.rejected(replace(self.evidence, diagnostics=(replace(
            self.warning, source=extended(self.warning.source)),)), 'SOURCE_DIAGNOSTIC_SOURCE_INVALID')
        self.rejected(replace(self.evidence, diagnostics=(replace(
            self.warning, next_position=extended(self.warning.next_position)),)),
                      'SOURCE_DIAGNOSTIC_POSITION_INVALID')

    def test_equal_json_does_not_override_declared_tuple_fields(self):
        for field in ('diagnostics', 'observation_sources'):
            changed = replace(self.evidence, **{field: list(getattr(self.evidence, field))})
            self.assertEqual(changed.to_json(), self.evidence.to_json())
            self.rejected(changed)

    def test_source_indices_are_exact_integers_in_mappings_and_diagnostics(self):
        first = self.evidence.observation_sources[0]
        for name in ('record_index', 'track_index', 'segment_index', 'point_index'):
            for value in (False, 0.0):
                source = replace(first.source, **{name: value})
                self.rejected(replace(self.evidence, observation_sources=(
                    replace(first, source=source), *self.evidence.observation_sources[1:])),
                              'SOURCE_MAPPING_INVALID')
                self.rejected(replace(self.evidence, diagnostics=(replace(
                    self.warning, source=source),)), 'SOURCE_DIAGNOSTIC_SOURCE_INVALID')

    def test_remaining_evidence_fields_require_native_declared_values(self):
        self.rejected(replace(self.evidence, outcome=ForeignString('success')))
        self.rejected(replace(self.evidence, outcome=True))
        self.rejected(replace(self.evidence, content_hash=ForeignDict(self.evidence.content_hash)))
        self.rejected(replace(self.evidence, content_hash={
            **self.evidence.content_hash, 'digest': ForeignString(self.evidence.content_hash['digest'])}))
        self.rejected(replace(self.evidence, canonical_track=ForeignDict(self.evidence.canonical_track)))
        track = copy.deepcopy(self.evidence.canonical_track)
        track['parts'] = tuple(track['parts'])
        self.assertEqual(json.loads(replace(self.evidence, canonical_track=track).to_json()),
                         json.loads(self.evidence.to_json()))
        self.rejected(replace(self.evidence, canonical_track=track))
        for payload in (self.warning, ForeignDict(description='extra'), math.nan):
            track = copy.deepcopy(self.evidence.canonical_track)
            track['extra'] = payload
            self.rejected(replace(self.evidence, canonical_track=track))

    def test_incomplete_and_recursive_instances_fail_closed(self):
        self.rejected(object.__new__(IngestionResult), 'QUALITY_EVIDENCE_INVALID')
        self.rejected(replace(self.evidence, diagnostics=(object.__new__(Diagnostic),)))
        track = copy.deepcopy(self.evidence.canonical_track)
        track['extra'] = track
        self.rejected(replace(self.evidence, canonical_track=track), 'QUALITY_EVIDENCE_INVALID')

    def test_authentic_warning_and_optional_string_field_remain_valid(self):
        for field in ('timestamp', None):
            evidence = replace(self.evidence, diagnostics=(replace(self.warning, field=field),))
            result = project_quality(evidence, policy=self.policy)
            self.assertEqual(result.outcome, 'produced')
            self.assertEqual(verify_quality(result.projection, evidence,
                                            policy=self.policy).outcome, 'valid')
            self.assertEqual(evidence_digest(evidence), result.projection.evidence_digest)
        again = ingest_bytes(self.raw, source_kind='gpx',
                             track_source={'id': 'd01-independent', 'revision_id': 'r1'})
        self.assertEqual(again.to_json(), self.evidence.to_json())
        self.assertEqual(project_quality(again, policy=self.policy).projection.to_json(),
                         self.quality.to_json())
        self.assertEqual(verify_spatial_entities(self.bundle, proof=self.proof,
                                                **self.args).outcome, 'valid')
        exported = export_temporal_geojson(bundle=self.bundle, proof=self.proof, **self.args)
        self.assertEqual(exported.outcome, 'produced')
        metric = next(feature['properties']['metric'] for feature in json.loads(
            exported.geojson_json)['features'] if feature['properties']['layer'] == 'target_metric_edge')
        self.assertEqual(metric['status'], 'missing_timestamp')
        self.assertIsNone(metric['speed_mps'])
        self.assertEqual(self.warning.field, 'timestamp')


if __name__ == '__main__':
    unittest.main()
