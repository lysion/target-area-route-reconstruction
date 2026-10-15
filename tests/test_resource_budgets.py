"""M3 per-source admission guards reject before hashing or downstream geometry."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from target_area_route_reconstruction import ingest_bytes, project_quality, verify_quality
from target_area_route_reconstruction.fit import parse_fit
from target_area_route_reconstruction.gpx import parse_gpx
from target_area_route_reconstruction.local_graph import LocalGraphStore, _output_vertices, _request, _target_vertices
from target_area_route_reconstruction.local_evidence import LocalEvidenceError
from target_area_route_reconstruction.spatial_entities_models import SpatialEntityBundle
from target_area_route_reconstruction.models import SourceFailure
from target_area_route_reconstruction.quality_models import QualityPolicy
from target_area_route_reconstruction import TaskResourceProfile
from target_area_route_reconstruction.resource_limits import normalize_task_resource_profile

FIXTURES = Path(os.environ.get("M3_SOURCE_FIXTURES", Path(__file__).resolve().parent / "source-fixtures"))
SOURCE = {"id": "bounded", "revision_id": "r1"}


class ResourceBudgetTests(unittest.TestCase):
    def test_task_resource_profile_is_strict_bounded_and_identity_relevant(self):
        from dataclasses import replace
        from target_area_route_reconstruction.local_graph import _request

        profile = replace(TaskResourceProfile(), max_observations=1234,
                          max_quality_fragments=2345, max_target_vertices=456,
                          max_output_vertices=7890)
        self.assertEqual(normalize_task_resource_profile(profile)["max_quality_fragments"], 2345)
        with self.assertRaisesRegex(ValueError, "INVALID_OBSERVATION_LIMIT"):
            normalize_task_resource_profile(replace(profile, max_observations=True))
        with self.assertRaisesRegex(ValueError, "INVALID_TARGET_VERTEX_LIMIT"):
            normalize_task_resource_profile(replace(profile, max_target_vertices=100_001))
        with self.assertRaisesRegex(ValueError, "INVALID_TASK_RESOURCE_PROFILE"):
            normalize_task_resource_profile(type("Foreign", (), {})())

        area = {"schema_version": "0.1.0", "id": "t", "revision_id": "r",
                "spatial_reference": "OGC:CRS84",
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1]]]},
                "definition_provenance": {"description": "profile identity"}}
        base = _request(area, QualityPolicy(), True, "speed_mps")
        varied = _request(area, QualityPolicy(), True, "speed_mps", profile)
        self.assertNotEqual(base["resource_profile"], varied["resource_profile"])
        self.assertNotEqual(json.dumps(base, sort_keys=True), json.dumps(varied, sort_keys=True))

    @staticmethod
    def _fragmented_gpx():
        # Every other parent edge is a fast one-degree jump; the intervening
        # stationary edges remain usable. This creates distinct quality runs.
        longitudes = (0, 1, 1, 2, 2, 3, 3)
        origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
        points = "".join(
            f'<trkpt lat="0" lon="{longitude}"><time>{(origin + timedelta(seconds=i)).isoformat().replace("+00:00", "Z")}</time></trkpt>'
            for i, longitude in enumerate(longitudes)
        )
        return (f'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="fragment">'
                f'<trk><trkseg>{points}</trkseg></trk></gpx>').encode()

    def test_source_byte_limit_fails_before_hash_and_parse(self):
        with patch("target_area_route_reconstruction.ingestion.hashlib.sha256", side_effect=AssertionError("must not hash")):
            result = ingest_bytes(b"1234", source_kind="gpx", track_source=SOURCE, max_source_bytes=3)
        self.assertEqual(result.outcome, "failure")
        self.assertIsNone(result.content_hash)
        self.assertEqual(result.diagnostics[0].code, "SOURCE_BYTES_LIMIT_EXCEEDED")

    def test_observation_budget_bounds_fit_and_gpx_parsers(self):
        fit = (FIXTURES / "fit" / "complete-activity.fit").read_bytes()
        gpx = (FIXTURES / "gpx" / "discontinuity.gpx").read_bytes()
        with self.assertRaisesRegex(SourceFailure, "OBSERVATION_LIMIT_EXCEEDED"):
            parse_fit(fit, max_observations=2)
        rejected = ingest_bytes(gpx, source_kind="gpx", track_source=SOURCE, max_observations=3)
        self.assertEqual(rejected.outcome, "failure")
        self.assertEqual(rejected.diagnostics[0].code, "OBSERVATION_LIMIT_EXCEEDED")

    def test_part_budget_refuses_before_building_another_part(self):
        gpx = (FIXTURES / "gpx" / "discontinuity.gpx").read_bytes()
        with self.assertRaisesRegex(SourceFailure, "PART_OR_INTERVAL_LIMIT_EXCEEDED"):
            parse_gpx(gpx, max_parts=1)

    def test_gpx_source_is_streamed_instead_of_materialized_as_a_tree(self):
        # The XSD is parsed from its packaged bytes; source XML must only flow
        # through the streaming parser. This protects the memory admission
        # guarantee independently of the returned bounded canonical model.
        raw_source = (b'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="stream">'
                      b'<trk><trkseg>' +
                      b''.join(b'<trkpt lat="0" lon="0"/>' for _ in range(256)) +
                      b'</trkseg></trk></gpx>')
        import target_area_route_reconstruction.gpx as gpx_module
        original = gpx_module.etree.fromstring

        def reject_source_tree(payload, *args, **kwargs):
            if payload == raw_source:
                raise AssertionError("GPX source was materialized with fromstring")
            return original(payload, *args, **kwargs)

        with patch.object(gpx_module.etree, "fromstring", side_effect=reject_source_tree):
            result = parse_gpx(raw_source, max_observations=256)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0].samples), 256)
        self.assertEqual(result[0].samples[-1].source.point_index, 255)

    def test_quality_fragmentation_budget_refuses_without_partial_projection(self):
        evidence = ingest_bytes(self._fragmented_gpx(), source_kind="gpx", track_source=SOURCE)
        policy = QualityPolicy(max_implied_speed_mps=1.0)
        rejected = project_quality(evidence, policy=policy, max_fragments=5)
        self.assertEqual(rejected.outcome, "resource_limit_exceeded")
        self.assertIsNone(rejected.projection)
        self.assertEqual(rejected.issues[0].code, "PART_OR_INTERVAL_LIMIT_EXCEEDED")

        with self.assertRaisesRegex(ValueError, "INVALID_QUALITY_FRAGMENT_LIMIT"):
            project_quality(evidence, policy=policy, max_fragments=True)
        over_boundary = project_quality(evidence, policy=policy, max_fragments=17)
        self.assertEqual(over_boundary.outcome, "resource_limit_exceeded")
        accepted = project_quality(evidence, policy=policy, max_fragments=18)
        self.assertEqual(accepted.outcome, "produced")
        self.assertEqual(verify_quality(accepted.projection, evidence, policy=policy).outcome, "valid")

    def test_quality_verifier_caps_outer_and_nested_fragment_claims_first(self):
        from dataclasses import replace
        from dataclasses import dataclass
        import target_area_route_reconstruction.quality_verifier as verifier
        from target_area_route_reconstruction.quality_models import Gap

        evidence = ingest_bytes(self._fragmented_gpx(), source_kind="gpx", track_source=SOURCE)
        policy = QualityPolicy(max_implied_speed_mps=1.0)
        projection = project_quality(evidence, policy=policy, max_fragments=18).projection
        with patch.object(verifier, "MAX_QUALITY_FRAGMENTATION", 18):
            result = verify_quality(projection, evidence, policy=policy)
        self.assertEqual(result.outcome, "valid")
        with patch.object(verifier, "MAX_QUALITY_FRAGMENTATION", 17):
            result = verify_quality(projection, evidence, policy=policy)
        self.assertEqual(result.outcome, "invalid")
        self.assertEqual(result.issues[0].code, "PART_OR_INTERVAL_LIMIT_EXCEEDED")

        gap = projection.gaps[0]
        @dataclass(frozen=True)
        class ExtendedGap(Gap):
            marker: str = "foreign"

        oversized_gap = ExtendedGap(gap.canonical_track, gap.start, gap.end, gap.kind,
                                    gap.causes, tuple(range(12)),
                                    gap.excluded_interval_index, gap.state)
        oversized = replace(projection, gaps=(oversized_gap, *projection.gaps[1:]))
        with patch.object(verifier, "MAX_QUALITY_FRAGMENTATION", 25):
            result = verify_quality(oversized, evidence, policy=policy)
        self.assertEqual(result.outcome, "invalid")
        self.assertEqual(result.issues[0].code, "PART_OR_INTERVAL_LIMIT_EXCEEDED")

    def test_local_graph_records_quality_budget_failure_without_downstream_proofs(self):
        source = {"schema_version": "0.1.0", "id": "fragment", "revision_id": "r1",
                  "activity": {"id": "a"}, "origin": {"namespace": "local"},
                  "representation": {"media_type": "application/gpx+xml"}}
        area = {"schema_version": "0.1.0", "id": "t", "revision_id": "r1",
                "spatial_reference": "OGC:CRS84",
                "geometry": {"type": "Polygon", "coordinates": [[[0, -1], [4, -1], [4, 1], [0, 1], [0, -1]]]},
                "definition_provenance": {"description": "quality fragmentation test"}}
        from dataclasses import replace
        from target_area_route_reconstruction.resource_limits import DEFAULT_TASK_RESOURCE_PROFILE
        with tempfile.TemporaryDirectory() as directory:
            store = LocalGraphStore(Path(directory) / "fragment.sqlite")
            admission = store.admit_bytes(self._fragmented_gpx(), source_kind="gpx", track_source=source)
            profile = replace(DEFAULT_TASK_RESOURCE_PROFILE, max_quality_fragments=5)
            commit = store.derive_graph("fragment", "r1", expected_record_digest=admission.record_digest,
                                        target_area=area, policy=QualityPolicy(max_implied_speed_mps=1.0),
                                        resource_profile=profile)
            reloaded = store.reload_graph(commit.graph_digest, expected_source_digest=admission.record_digest,
                                          target_area=area, policy=QualityPolicy(max_implied_speed_mps=1.0),
                                          resource_profile=profile)
            self.assertEqual(commit.outcome, "stage_unavailable")
            self.assertEqual(reloaded.status, "verified_local")
            manifest = json.loads(reloaded.manifest_json)
            stages = {node["kind"]: json.loads(node["payload_json"])
                      for node in manifest["nodes"]}
            self.assertEqual(stages["M2B"]["outcome"], "resource_limit_exceeded")
            self.assertEqual(stages["M2B"]["result_json"] and
                             json.loads(stages["M2B"]["result_json"])["issues"][0]["code"],
                             "PART_OR_INTERVAL_LIMIT_EXCEEDED")
            for stage in ("M2C", "M2D", "M2E", "M2F"):
                self.assertEqual(stages[stage]["outcome"], "unavailable")
                self.assertIsNone(stages[stage]["result_json"])

    def test_target_complexity_is_rejected_before_canonical_serialization(self):
        area = {
            "schema_version": "0.1.0", "id": "t", "revision_id": "r",
            "spatial_reference": "OGC:CRS84",
            "geometry": {"type": "Polygon", "coordinates": [[ [float(i), 0.0] for i in range(20_001) ]]},
            "definition_provenance": {"description": "oversized test target"},
        }
        with patch("target_area_route_reconstruction.local_graph.canonical_record", side_effect=AssertionError("must not serialize")):
            with self.assertRaisesRegex(LocalEvidenceError, "TARGET_COMPLEXITY_LIMIT_EXCEEDED"):
                _request(area, QualityPolicy(), True, "speed_mps")

    def test_vertex_limits_accept_exact_ceiling_and_reject_next_vertex(self):
        import target_area_route_reconstruction.local_graph as graph
        area = {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1]]]}}
        self.assertEqual(_target_vertices(area, limit=3), 3)
        area["geometry"]["coordinates"][0].append([0, 1])
        with self.assertRaisesRegex(LocalEvidenceError, "TARGET_COMPLEXITY_LIMIT_EXCEEDED"):
            _target_vertices(area, limit=3)

        bundle = SpatialEntityBundle("{}", ('{"geometry":{"coordinates":[[0,0],[1,1]]}}',))
        self.assertEqual(_output_vertices(bundle, limit=2), 2)
        with self.assertRaisesRegex(LocalEvidenceError, "OUTPUT_LIMIT_EXCEEDED"):
            _output_vertices(bundle, limit=2, initial=1)
        with self.assertRaisesRegex(LocalEvidenceError, "OUTPUT_LIMIT_EXCEEDED"):
            _output_vertices(SpatialEntityBundle("{}", ()), limit=2, initial=3)

    def test_public_graph_entry_refuses_target_before_storage_publication(self):
        import target_area_route_reconstruction.local_graph as graph
        area = {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}}
        with tempfile.TemporaryDirectory() as directory:
            store = LocalGraphStore(Path(directory) / "empty.sqlite")
            from dataclasses import replace
            from target_area_route_reconstruction.resource_limits import DEFAULT_TASK_RESOURCE_PROFILE
            with self.assertRaisesRegex(LocalEvidenceError, "TARGET_COMPLEXITY_LIMIT_EXCEEDED"):
                store.derive_graph("missing", "r1", expected_record_digest="0" * 64,
                                   target_area=area, resource_profile=replace(
                                       DEFAULT_TASK_RESOURCE_PROFILE, max_target_vertices=3))
            with sqlite3.connect(store.path) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM graphs").fetchone()[0], 0)

    def test_output_budget_failure_does_not_publish_graph(self):
        from dataclasses import replace
        from target_area_route_reconstruction.resource_limits import DEFAULT_TASK_RESOURCE_PROFILE
        source = {"schema_version": "0.1.0", "id": "budget", "revision_id": "r1",
                  "activity": {"id": "a"}, "origin": {"namespace": "local"},
                  "representation": {"media_type": "application/gpx+xml"}}
        area = {"schema_version": "0.1.0", "id": "t", "revision_id": "r1",
                "spatial_reference": "OGC:CRS84",
                "geometry": {"type": "Polygon", "coordinates": [[[112.902, 28.19], [112.908, 28.19],
                                                                            [112.908, 28.22], [112.902, 28.22],
                                                                            [112.902, 28.19]]]},
                "definition_provenance": {"description": "output budget"}}
        with tempfile.TemporaryDirectory() as directory:
            store = LocalGraphStore(Path(directory) / "output.sqlite")
            admission = store.admit_file(FIXTURES / "equivalent" / "basic.gpx",
                                         source_kind="gpx", track_source=source)
            with self.assertRaisesRegex(LocalEvidenceError, "OUTPUT_LIMIT_EXCEEDED"):
                store.derive_graph("budget", "r1", expected_record_digest=admission.record_digest,
                                   target_area=area, resource_profile=replace(
                                       DEFAULT_TASK_RESOURCE_PROFILE, max_output_vertices=1))
            with sqlite3.connect(store.path) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM graphs").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
