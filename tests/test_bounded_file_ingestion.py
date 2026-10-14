"""Public file admission tests; standalone in the noneditable wheel too."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from target_area_route_reconstruction import ingest_bytes, ingest_file
from target_area_route_reconstruction import ingestion

SOURCE = {"id": "bounded-source", "revision_id": "r1"}
GPX = b'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="test"><trk><trkseg><trkpt lat="0" lon="0"/><trkpt lat="0" lon="1"/></trkseg></trk></gpx>'


class BoundedFileIngestionTests(unittest.TestCase):
    def assert_failure(self, result, code):
        self.assertEqual(result.outcome, "failure")
        self.assertIsNone(result.content_hash)
        self.assertIsNone(result.canonical_track)
        self.assertEqual(result.diagnostics[0].code, code)

    def test_regular_boundary_hash_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.gpx"
            path.write_bytes(GPX)
            digest = hashlib.sha256(GPX).hexdigest()
            for budget in (len(GPX), len(GPX) + 1):
                actual = ingest_file(path, source_kind="gpx", track_source=SOURCE,
                                     max_source_bytes=budget, expected_sha256=digest)
                expected = ingest_bytes(GPX, source_kind="gpx", track_source=SOURCE, expected_sha256=digest)
                self.assertEqual(actual.to_json(), expected.to_json())
            mismatch = ingest_file(path, source_kind="gpx", track_source=SOURCE, expected_sha256="0" * 64)
            self.assertEqual(mismatch.diagnostics[0].code, "SOURCE_HASH_MISMATCH")
            self.assertEqual(mismatch.content_hash["digest"], digest)
            self.assertEqual(path.read_bytes(), GPX)
            with patch.object(ingestion.os, "read", side_effect=AssertionError("must not read")):
                self.assert_failure(ingest_file(path, source_kind="gpx", track_source=SOURCE,
                                               max_source_bytes=len(GPX)-1), "SOURCE_BYTES_LIMIT_EXCEEDED")

    def test_sparse_oversize_default_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.fit"
            with path.open("wb") as stream:
                stream.truncate(ingestion.DEFAULT_SOURCE_BYTES + 1)
            with patch.object(ingestion.os, "read", side_effect=AssertionError("must not read")):
                self.assert_failure(ingest_file(path, source_kind="fit", track_source=SOURCE),
                                    "SOURCE_BYTES_LIMIT_EXCEEDED")

    def test_growth_after_descriptor_stat_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "growing.gpx"
            path.write_bytes(b"x")
            real_stat, real_read = os.fstat, os.read
            requests = []
            def grow(descriptor):
                metadata = real_stat(descriptor)
                path.write_bytes(b"x" * 100)
                return metadata
            def read(descriptor, size):
                requests.append(size)
                return real_read(descriptor, size)
            with patch.object(ingestion.os, "fstat", side_effect=grow), patch.object(ingestion.os, "read", side_effect=read), patch.object(ingestion, "ingest_bytes", side_effect=AssertionError("no partial parse/hash")):
                self.assert_failure(ingest_file(path, source_kind="gpx", track_source=SOURCE,
                                               max_source_bytes=7), "SOURCE_BYTES_LIMIT_EXCEEDED")
            self.assertEqual(requests, [8])

    def test_nonregular_and_missing_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            # POSIX directory opens succeed and must be refused before read.
            result = ingest_file(path, source_kind="gpx", track_source=SOURCE)
            self.assert_failure(result, "SOURCE_NOT_REGULAR_FILE" if os.name == "posix" else "SOURCE_READ_FAILED")
            self.assert_failure(ingest_file(path / "absent", source_kind="fit", track_source=SOURCE), "SOURCE_READ_FAILED")
            if hasattr(os, "mkfifo"):
                fifo = path / "pipe"
                os.mkfifo(fifo)
                with patch.object(ingestion.os, "read", side_effect=AssertionError("must not read")):
                    self.assert_failure(ingest_file(fifo, source_kind="fit", track_source=SOURCE), "SOURCE_NOT_REGULAR_FILE")
            if os.name == "posix" and Path("/dev/null").exists():
                self.assert_failure(ingest_file("/dev/null", source_kind="fit", track_source=SOURCE), "SOURCE_NOT_REGULAR_FILE")

    def test_symlink_resolves_opened_regular_file(self):
        if os.name != "posix":
            self.skipTest("symlink permissions platform dependent")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.gpx"
            path.write_bytes(GPX)
            link = path.with_name("link.gpx")
            link.symlink_to(path)
            self.assertEqual(ingest_file(link, source_kind="gpx", track_source=SOURCE).to_json(),
                             ingest_bytes(GPX, source_kind="gpx", track_source=SOURCE).to_json())

    def test_invalid_budget_and_read_error(self):
        for budget in (False, True, 0, -1, 1.0, "1", None, ingestion.MAX_SOURCE_BYTES+1):
            with self.subTest(budget=budget), self.assertRaisesRegex(ValueError, "^INVALID_SOURCE_BYTES_LIMIT$"):
                ingest_file("absent", source_kind="gpx", track_source=SOURCE, max_source_bytes=budget)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.gpx"
            path.write_bytes(GPX)
            with patch.object(ingestion.os, "read", side_effect=OSError("read error")):
                self.assert_failure(ingest_file(path, source_kind="gpx", track_source=SOURCE), "SOURCE_READ_FAILED")


if __name__ == "__main__":
    unittest.main()
