"""Independent raw-source and deterministic regeneration regressions."""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from generate_synthetic_source_fixtures import write_fixtures
from validate_source_fixture_baseline import FixtureError, fit_crc, read_fit, read_gpx


class RawSourceContractTests(unittest.TestCase):
    def test_all_raw_files_regenerate_byte_identically(self) -> None:
        manifest = json.loads((ROOT / "tests/source-fixtures/manifest.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixtures(root)
            for entry in manifest["fixtures"]:
                with self.subTest(path=entry["path"]):
                    self.assertEqual(
                        (root / entry["path"]).read_bytes(),
                        (ROOT / "tests/source-fixtures" / entry["path"]).read_bytes(),
                    )

    def test_complete_activity_has_required_message_types(self) -> None:
        result = read_fit(ROOT / "tests/source-fixtures/fit/complete-activity.fit")
        self.assertEqual(result["activity_structure"], "complete_activity")
        self.assertEqual(result["message_counts"], {
            "file_id": 1, "record": 3, "lap": 1, "session": 1, "activity": 1,
        })

    def test_invalid_position_sentinel_is_not_a_position(self) -> None:
        root = ROOT / "tests/source-fixtures/fit"
        self.assertEqual(read_fit(root / "invalid-position-sentinel.fit")["positioned_record_count"], 0)
        self.assertEqual(read_fit(root / "mixed-position.fit")["positioned_record_count"], 2)

    def test_header_crc_is_checked_independently_of_file_crc(self) -> None:
        data = (ROOT / "tests/source-fixtures/equivalent/basic.fit").read_bytes()
        header = bytearray(data[:12])
        header[0] = 14
        header.extend(struct.pack("<H", fit_crc(header) ^ 1))
        bad = bytes(header) + data[12:-2]
        bad += struct.pack("<H", fit_crc(bad))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.fit"
            path.write_bytes(bad)
            with self.assertRaisesRegex(FixtureError, "header CRC"):
                read_fit(path)

    def test_well_formed_wrong_root_is_not_valid_gpx(self) -> None:
        path = ROOT / "tests/source-fixtures/gpx/invalid-root.gpx"
        self.assertEqual(read_gpx(path, False)["failure_class"], "invalid_gpx")
        with self.assertRaises(FixtureError):
            read_gpx(path, True)


if __name__ == "__main__":
    unittest.main()
