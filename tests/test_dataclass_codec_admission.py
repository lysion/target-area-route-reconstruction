"""Native codec metadata cannot select which facts are validated or hashed.

Public chain tests use class declarations as the independent field oracle.
Self-contained for the installed-wheel gate; no production matcher as oracle.
"""
import copy
import hashlib
import unittest
from dataclasses import fields, is_dataclass
from unittest.mock import patch

from target_area_route_reconstruction import (
    QualityPolicy, ingest_bytes, project_quality, verify_quality,
    prove_spatial_relation, verify_spatial_relation, assemble_spatial_entities,
    verify_spatial_entities, export_geojson, export_temporal_geojson,
)
from target_area_route_reconstruction.quality_models import ParentReference


def fixture():
    segments = []
    for points in (((0., 0.), (.01, 0.), (.01, 0.), (.02, 0.)), ((.03, 0.), (.04, 0.))):
        segments.append('<trkseg>' + ''.join(
            f'<trkpt lon="{x}" lat="{y}"><time>2026-10-12T00:00:00</time></trkpt>'
            for x, y in points) + '</trkseg>')
    raw = ('<gpx version="1.1" creator="codec-regression" '
           'xmlns="http://www.topografix.com/GPX/1/1"><trk>' +
           ''.join(segments) + '</trk></gpx>').encode()
    evidence = ingest_bytes(raw, source_kind="gpx",
                            track_source={"id": "codec-source", "revision_id": "raw1"})
    policy = QualityPolicy(include_domain_bounds=True)
    quality = project_quality(evidence, policy=policy).projection
    target = dict(schema_version="0.1.0", id="codec-target", revision_id="t1",
                  spatial_reference="OGC:CRS84",
                  definition_provenance={"description": "class-owned codec"},
                  geometry={"type": "Polygon", "coordinates": [
                      [[-1., -1.], [1., -1.], [1., 1.], [-1., 1.], [-1., -1.]]]})
    args = dict(evidence=evidence, quality_projection=quality, quality_policy=policy,
                target_area=target, target_reference=ParentReference(target["id"], "t1"))
    proof = prove_spatial_relation(**args).proof
    assert proof is not None
    bundle = assemble_spatial_entities(proof=proof, **args).bundle
    assert bundle is not None
    return args, proof, bundle


def find(value, name):
    if type(value).__name__ == name:
        return value
    if is_dataclass(value):
        children = [getattr(value, f.name) for f in fields(type(value))]
    elif type(value) in (list, tuple):
        children = value
    else:
        return None
    for child in children:
        found = find(child, name)
        if found is not None:
            return found
    return None


def shadow(value, name, omitted, spelling):
    changed = copy.deepcopy(value)
    model = find(changed, name)
    assert model is not None
    declared = {f.name: getattr(model, f.name) for f in fields(type(model))}
    table = type(model).__dataclass_fields__
    payload = ({} if spelling == "empty" else dict(table) if spelling == "equal-copy"
               else {k: v for k, v in table.items() if k != omitted})
    object.__setattr__(model, "__dataclass_fields__", payload)
    assert declared == {f.name: getattr(model, f.name) for f in fields(type(model))}
    return changed


class DataclassCodecAdmission(unittest.TestCase):
    def test_evidence_metadata_rejected_before_any_hash(self):
        from target_area_route_reconstruction._quality_evidence import evidence_digest
        args, _, _ = fixture()
        variants = (("IngestionResult", "diagnostics"), ("Diagnostic", "field"),
                    ("ObservationSource", "source"), ("SourceLocation", "point_index"),
                    ("TrackPosition", "fraction_to_next"))
        for model, omitted in variants:
            for spelling in ("empty", "omitted", "equal-copy"):
                with self.subTest(model=model, spelling=spelling):
                    evidence = shadow(args["evidence"], model, omitted, spelling)
                    with patch("hashlib.sha256", wraps=hashlib.sha256) as sha:
                        result = project_quality(evidence, policy=args["quality_policy"])
                        with self.assertRaisesRegex(ValueError, "QUALITY_EVIDENCE_INVALID"):
                            evidence_digest(evidence)
                        self.assertEqual(sha.call_count, 0)
                    self.assertEqual(result.outcome, "quality_evidence_unavailable")
                    self.assertIsNone(result.projection)
        for method in ("to_dict", "to_json"):
            with self.subTest(method=method):
                evidence = copy.deepcopy(args["evidence"])
                callback = unittest.mock.Mock(return_value={})
                object.__setattr__(evidence, method, callback)
                with patch("hashlib.sha256", wraps=hashlib.sha256) as sha:
                    self.assertEqual(project_quality(evidence, policy=args["quality_policy"]).outcome,
                                     "quality_evidence_unavailable")
                    with self.assertRaisesRegex(ValueError, "QUALITY_EVIDENCE_INVALID"):
                        evidence_digest(evidence)
                    self.assertEqual(sha.call_count, 0)
                callback.assert_not_called()

    def test_quality_metadata_never_becomes_spatial_authority(self):
        args, _, _ = fixture()
        for model, omitted in (("QualityProjection", "diagnostics"), ("ParentInterval", "end"),
                               ("EdgeDiagnostic", "code"), ("Gap", "diagnostic_indices"),
                               ("GapConstraint", "gap_index")):
            for spelling in ("empty", "omitted", "equal-copy"):
                with self.subTest(model=model, spelling=spelling):
                    changed = shadow(args["quality_projection"], model, omitted, spelling)
                    self.assertEqual(verify_quality(changed, args["evidence"],
                                     policy=args["quality_policy"]).outcome, "invalid")
                    with patch("target_area_route_reconstruction._spatial_inputs.fingerprint") as fingerprint:
                        result = prove_spatial_relation(**{**args, "quality_projection": changed})
                        fingerprint.assert_not_called()
                    self.assertEqual(result.outcome, "invalid_input")
                    self.assertIsNone(result.proof)
        for method in ("to_dict", "to_json"):
            changed = copy.deepcopy(args["quality_projection"])
            callback = unittest.mock.Mock(return_value={})
            object.__setattr__(changed, method, callback)
            self.assertEqual(verify_quality(changed, args["evidence"],
                             policy=args["quality_policy"]).outcome, "invalid")
            self.assertEqual(prove_spatial_relation(**{**args, "quality_projection": changed}).outcome,
                             "invalid_input")
            callback.assert_not_called()

    def test_proof_metadata_rejected_before_entity_and_exports(self):
        args, proof, bundle = fixture()
        for model, omitted in (("SpatialRelationProof", "stationary_evidence"),
                               ("SpatialAuthority", "quality_projection_digest"),
                               ("StationaryEvidence", "target_covered"),
                               ("GapRelevance", "bound_relation")):
            for spelling in ("empty", "omitted", "equal-copy"):
                with self.subTest(model=model, spelling=spelling):
                    changed = shadow(proof, model, omitted, spelling)
                    self.assertEqual(verify_spatial_relation(changed, **args).outcome, "invalid")
                    with patch("target_area_route_reconstruction.spatial_entities._assemble") as assemble:
                        denied = assemble_spatial_entities(proof=changed, **args)
                        assemble.assert_not_called()
                    self.assertEqual(denied.outcome, "invalid_input")
                    self.assertIsNone(denied.bundle)
                    for export in (export_geojson, export_temporal_geojson):
                        self.assertEqual(export(bundle=bundle, proof=changed, **args).outcome, "invalid_input")
        for method in ("to_dict", "to_json"):
            changed = copy.deepcopy(proof)
            callback = unittest.mock.Mock(return_value={})
            object.__setattr__(changed, method, callback)
            self.assertEqual(verify_spatial_relation(changed, **args).outcome, "invalid")
            self.assertEqual(assemble_spatial_entities(proof=changed, **args).outcome, "invalid_input")
            callback.assert_not_called()

    def test_legitimate_revisions_stay_bound_and_private_wrong_roots_fail_closed(self):
        from target_area_route_reconstruction._quality_evidence import evidence_digest
        from target_area_route_reconstruction.models import Diagnostic
        args, _, _ = fixture()
        payloads = []
        for revision in ("t1", "t2"):
            target = {**args["target_area"], "revision_id": revision}
            changed = {**args, "target_area": target,
                       "target_reference": ParentReference(target["id"], revision)}
            proof = prove_spatial_relation(**changed).proof
            bundle = assemble_spatial_entities(proof=proof, **changed).bundle
            self.assertEqual(verify_spatial_entities(bundle, proof=proof, **changed).outcome, "valid")
            payloads.append(bundle)
            corrupt = shadow(proof, "SpatialAuthority", "quality_projection_digest", "empty")
            self.assertEqual(verify_spatial_relation(corrupt, **changed).outcome, "invalid")
        self.assertEqual(payloads[0].assessment["id"], payloads[1].assessment["id"])
        self.assertNotEqual(payloads[0].assessment["revision_id"], payloads[1].assessment["revision_id"])
        self.assertNotEqual(payloads[0].to_json(), payloads[1].to_json())
        repeated = prove_spatial_relation(**args).proof
        self.assertEqual(assemble_spatial_entities(proof=repeated, **args).bundle.to_json(), payloads[0].to_json())
        evidence = copy.deepcopy(args["evidence"])
        object.__setattr__(evidence, "__dataclass_params__", type(evidence).__dataclass_params__)
        self.assertEqual(project_quality(evidence, policy=args["quality_policy"]).outcome,
                         "quality_evidence_unavailable")
        with patch("hashlib.sha256", wraps=hashlib.sha256) as sha:
            with self.assertRaisesRegex(ValueError, "QUALITY_EVIDENCE_INVALID"):
                evidence_digest(Diagnostic("ADMITTED"))
            self.assertEqual(sha.call_count, 0)
        policy = copy.deepcopy(args["quality_policy"])
        object.__setattr__(policy, "__dataclass_fields__", {})
        with patch("hashlib.sha256", wraps=hashlib.sha256) as sha:
            with self.assertRaisesRegex(ValueError, "QUALITY_POLICY_INVALID"):
                project_quality(args["evidence"], policy=policy)
            self.assertEqual(sha.call_count, 0)
        reference = copy.deepcopy(args["target_reference"])
        object.__setattr__(reference, "__dataclass_fields__", {})
        denied = prove_spatial_relation(**{**args, "target_reference": reference})
        self.assertEqual(denied.outcome, "invalid_input")
        self.assertIn("TARGET_REFERENCE_MISMATCH", [i.code for i in denied.issues])
        incomplete = object.__new__(ParentReference)
        denied = prove_spatial_relation(**{**args, "target_reference": incomplete})
        self.assertEqual(denied.outcome, "invalid_input")
        self.assertIn("TARGET_REFERENCE_MISMATCH", [i.code for i in denied.issues])
        class ForeignTarget(dict):
            def __deepcopy__(self, memo):
                raise AssertionError("foreign copy must never run")
        class ForeignFloat(float):
            def __float__(self):
                raise AssertionError("foreign conversion must never run")
        for target in (ForeignTarget(args["target_area"]), copy.deepcopy(args["target_area"])):
            if type(target) is dict:
                target["geometry"]["coordinates"][0][0][0] = ForeignFloat(-1.)
            denied = prove_spatial_relation(**{**args, "target_area": target})
            self.assertEqual(denied.outcome, "invalid_input")
            self.assertIn("SPATIAL_INPUT_NONFINITE_OR_MALFORMED", [i.code for i in denied.issues])


if __name__ == "__main__":
    unittest.main()
