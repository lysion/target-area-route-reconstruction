"""M3 per-source admission guards reject before hashing or downstream geometry."""
from pathlib import Path
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from target_area_route_reconstruction import ingest_bytes
from target_area_route_reconstruction.fit import parse_fit
from target_area_route_reconstruction.gpx import parse_gpx
from target_area_route_reconstruction.local_graph import LocalGraphStore, _output_vertices, _request, _target_vertices
from target_area_route_reconstruction.local_evidence import LocalEvidenceError
from target_area_route_reconstruction.spatial_entities_models import SpatialEntityBundle
from target_area_route_reconstruction.models import SourceFailure
from target_area_route_reconstruction.quality_models import QualityPolicy

FIXTURES = Path(os.environ.get("M3_SOURCE_FIXTURES", Path(__file__).resolve().parent / "source-fixtures"))
SOURCE = {"id": "bounded", "revision_id": "r1"}


class ResourceBudgetTests(unittest.TestCase):
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
        with patch.object(graph, "DEFAULT_TARGET_VERTICES", 3):
            self.assertEqual(_target_vertices(area), 3)
            area["geometry"]["coordinates"][0].append([0, 1])
            with self.assertRaisesRegex(LocalEvidenceError, "TARGET_COMPLEXITY_LIMIT_EXCEEDED"):
                _target_vertices(area)

        bundle = SpatialEntityBundle("{}", ('{"geometry":{"coordinates":[[0,0],[1,1]]}}',))
        with patch.object(graph, "DEFAULT_OUTPUT_VERTICES", 2):
            self.assertEqual(_output_vertices(bundle), 2)
            with self.assertRaisesRegex(LocalEvidenceError, "OUTPUT_LIMIT_EXCEEDED"):
                _output_vertices(bundle, initial=1)
            with self.assertRaisesRegex(LocalEvidenceError, "OUTPUT_LIMIT_EXCEEDED"):
                _output_vertices(SpatialEntityBundle("{}", ()), initial=3)

    def test_public_graph_entry_refuses_target_before_storage_publication(self):
        import target_area_route_reconstruction.local_graph as graph
        area = {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}}
        with tempfile.TemporaryDirectory() as directory:
            store = LocalGraphStore(Path(directory) / "empty.sqlite")
            with patch.object(graph, "DEFAULT_TARGET_VERTICES", 3):
                with self.assertRaisesRegex(LocalEvidenceError, "TARGET_COMPLEXITY_LIMIT_EXCEEDED"):
                    store.derive_graph("missing", "r1", expected_record_digest="0" * 64,
                                       target_area=area)
            with sqlite3.connect(store.path) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM graphs").fetchone()[0], 0)

    def test_output_budget_failure_does_not_publish_graph(self):
        import target_area_route_reconstruction.local_graph as graph
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
            with patch.object(graph, "DEFAULT_OUTPUT_VERTICES", 1):
                with self.assertRaisesRegex(LocalEvidenceError, "OUTPUT_LIMIT_EXCEEDED"):
                    store.derive_graph("budget", "r1", expected_record_digest=admission.record_digest,
                                       target_area=area)
            with sqlite3.connect(store.path) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM graphs").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
