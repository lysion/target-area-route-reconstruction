"""Independent raw-source and deterministic regeneration regressions."""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path
import fitdecode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from generate_synthetic_source_fixtures import write_fixtures
from validate_source_fixture_baseline import FixtureError, fit_crc, read_fit, read_gpx
from strict_json import load_json


class RawSourceContractTests(unittest.TestCase):
    def test_all_raw_files_regenerate_byte_identically(self) -> None:
        manifest = load_json(ROOT / "tests/source-fixtures/manifest.json")
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

    def test_complete_activity_summary_contract_independently_decoded(self) -> None:
        with fitdecode.FitReader(str(ROOT / "tests/source-fixtures/fit/complete-activity.fit"),
                                 check_crc=fitdecode.CrcCheck.RAISE) as reader:
            frames = [frame for frame in reader if isinstance(frame, fitdecode.FitDataMessage)]
        self.assertEqual(frames[0].name, "file_id")
        self.assertEqual(frames[0].get_value("type"), "activity")
        self.assertIsNotNone(frames[0].get_value("manufacturer"))
        messages = {frame.name: frame for frame in frames}
        for name in ("lap", "session"):
            message = messages[name]
            self.assertEqual((message.get_value("timestamp") - message.get_value("start_time")).total_seconds(), 20)
            self.assertEqual(message.get_value("total_elapsed_time"), 20)
            self.assertEqual(message.get_value("total_timer_time"), 20)
            self.assertEqual(message.get_value("sport"), "running")
        self.assertEqual(messages["activity"].get_value("num_sessions"), 1)
        self.assertEqual(messages["activity"].get_value("local_timestamp"), messages["activity"].get_value("timestamp"))
        self.assertEqual(messages["session"].get_value("num_laps"), 1)
        self.assertEqual(messages["session"].get_value("first_lap_index"), 0)

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
