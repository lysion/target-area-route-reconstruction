"""M2A integration oracles: explicit facts, frozen schemas and raw baseline."""

from __future__ import annotations

import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from lxml import etree

from target_area_route_reconstruction import TrackPosition, ingest_bytes, ingest_file
from target_area_route_reconstruction import normalization

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from strict_json import load_json
from generate_synthetic_source_fixtures import build_fit, definition_message, data_message, file_id_block
from validate_schema_fixtures import build_registry, schema_documents
from validate_source_fixture_baseline import fit_crc, read_fit

RAW = ROOT / "tests/source-fixtures"
SOURCE = {"id": "m2a-source", "revision_id": "m2a-source-r1"}


def gpx(segments: list[list[str]]) -> bytes:
    return ('<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="M2A-test"><trk>'
            + ''.join('<trkseg>' + ''.join(points) + '</trkseg>' for points in segments)
            + '</trk></gpx>').encode()


def observations(result):
    return [observation for part in result.canonical_track["parts"] for observation in part["observations"]]


def positions(result):
    return [observation["position"] for observation in observations(result)]


def fit_record(fields, payload):
    """Test-only encoder; expected decoded telemetry is stated independently."""
    data = file_id_block(datetime(2026, 10, 7, tzinfo=timezone.utc))
    data += definition_message(1, 20, fields) + data_message(1, payload)
    header = struct.pack("<BBHI4s", 12, 0x20, 2100, len(data), b".FIT")
    body = header + data
    return body + struct.pack("<H", fit_crc(body))


class CanonicalIngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(RAW / "manifest.json")
        documents = schema_documents(ROOT / "schemas")
        cls.validator = Draft202012Validator(
            documents[ROOT / "schemas/canonical-track.schema.json"], registry=build_registry(documents),
            format_checker=FormatChecker(),
        )

    def raw(self, relative: str):
        return ingest_file(RAW / relative, source_kind=Path(relative).suffix[1:], track_source=SOURCE)

    def assert_failure(self, result, code: str):
        self.assertEqual(result.outcome, "failure")
        self.assertIsNone(result.canonical_track)
        self.assertEqual([issue.code for issue in result.diagnostics], [code])

    def test_every_committed_raw_source_against_independent_expectations(self):
        for entry in self.manifest["fixtures"]:
            with self.subTest(fixture=entry["id"]):
                result = ingest_file(RAW / entry["path"], source_kind=entry["format"], track_source=SOURCE,
                                     expected_sha256=entry["sha256"])
                self.assertEqual(result.content_hash, {"algorithm": "sha256", "digest": entry["sha256"]})
                expectation = entry["normalization_expectation"]
                if not entry["source_expectation"]["source_valid"]:
                    code = "MALFORMED_SOURCE" if entry["source_expectation"]["failure_class"] == "malformed_xml" else "INVALID_GPX_STRUCTURE"
                    self.assert_failure(result, code)
                elif expectation.get("canonical_track_present") is False:
                    self.assertEqual(result.outcome, "no_positioned_observations")
                    self.assertIsNone(result.canonical_track)
                else:
                    self.assertEqual(result.outcome, "success")
                    self.assertEqual(list(self.validator.iter_errors(result.canonical_track)), [])
                    self.assertEqual(result.canonical_track["track_source"], SOURCE)
                    self.assertEqual(result.canonical_track["spatial_reference"], "OGC:CRS84")
                    if "observation_counts" in expectation:
                        self.assertEqual([len(part["observations"]) for part in result.canonical_track["parts"]], expectation["observation_counts"])
                    if "positions" in expectation:
                        tolerance = expectation.get("position_tolerance_deg", 0)
                        for actual, expected in zip(positions(result), expectation["positions"]):
                            for a, b in zip(actual, expected):
                                self.assertLessEqual(abs(a - b), tolerance)
                    if "timestamps" in expectation:
                        self.assertEqual([obs["timestamp"] for obs in observations(result)], expectation["timestamps"])

    def test_complete_activity_and_original_minimal_fit_are_both_accepted(self):
        for path in ("fit/complete-activity.fit", "equivalent/basic.fit"):
            with self.subTest(path=path):
                result = self.raw(path)
                independently_decoded = read_fit(RAW / path)
                self.assertEqual(positions(result), [list(point) for point in independently_decoded["positions"]])
                self.assertEqual(len(observations(result)), 3)

    def test_no_position_fit_retains_source_record_diagnostics(self):
        for path, reason in (("fit/no-position.fit", "POSITION_MISSING"),
                             ("fit/invalid-position-sentinel.fit", "POSITION_INVALID_SENTINEL")):
            with self.subTest(path=path):
                result = self.raw(path)
                self.assertIsNone(result.canonical_track)
                missing = result.diagnostics[:-1]
                self.assertEqual([issue.code for issue in missing], [reason] * 3)
                self.assertEqual([issue.source.record_index for issue in missing], [0, 1, 2])
                self.assertTrue(all(issue.source.source_kind == "fit" for issue in missing))
                self.assertTrue(all(issue.previous_position is None and issue.next_position is None for issue in missing))

    def test_mixed_fit_has_two_singleton_parts_and_missing_record_neighbors(self):
        result = self.raw("fit/mixed-position.fit")
        self.assertEqual([len(part["observations"]) for part in result.canonical_track["parts"]], [1, 1])
        issue, = result.diagnostics
        self.assertEqual((issue.code, issue.source.record_index), ("POSITION_INVALID_SENTINEL", 1))
        self.assertEqual(issue.previous_position, TrackPosition(0, 0))
        self.assertEqual(issue.next_position, TrackPosition(1, 0))
        self.assertEqual([item.source.record_index for item in result.observation_sources], [0, 2])
        self.assertEqual([item.position for item in result.observation_sources], [TrackPosition(0, 0), TrackPosition(1, 0)])

    def test_multiple_missing_fit_records_preserve_surrounding_evidence(self):
        time = datetime(2026, 10, 7, tzinfo=timezone.utc)
        data = build_fit([(time, None, None), (time, 0, 0), (time, None, None),
                          (time, None, None), (time, 1, 1), (time, None, None)])
        result = ingest_bytes(data, source_kind="fit", track_source=SOURCE)
        self.assertEqual(positions(result), [[0.0, 0.0], [180.0 / 2**31 * round(2**31 / 180), 180.0 / 2**31 * round(2**31 / 180)]])
        self.assertEqual([len(part["observations"]) for part in result.canonical_track["parts"]], [1, 1])
        self.assertEqual([issue.source.record_index for issue in result.diagnostics], [0, 2, 3, 5])
        self.assertEqual([(issue.previous_position, issue.next_position) for issue in result.diagnostics], [
            (None, TrackPosition(0, 0)), (TrackPosition(0, 0), TrackPosition(1, 0)),
            (TrackPosition(0, 0), TrackPosition(1, 0)), (TrackPosition(1, 0), None),
        ])

    def test_gpx_parts_and_original_point_locations(self):
        result = self.raw("gpx/discontinuity.gpx")
        self.assertEqual([len(part["observations"]) for part in result.canonical_track["parts"]], [2, 2])
        expected = [[112.9, 28.2], [112.902, 28.202], [112.908, 28.208], [112.91, 28.21]]
        self.assertEqual(positions(result), expected)
        self.assertEqual([(item.source.segment_index, item.source.point_index) for item in result.observation_sources], [(0, 0), (0, 1), (1, 0), (1, 1)])
        issue, = result.diagnostics
        self.assertEqual(issue.code, "SOURCE_CONTINUITY_BREAK")
        self.assertEqual((issue.previous_position, issue.next_position), (TrackPosition(0, 1), TrackPosition(1, 0)))

    def test_empty_gpx_parts_are_diagnostic_and_never_merge_neighbors(self):
        data = gpx([["<trkpt lon='0' lat='0'/>"] , [], ["<trkpt lon='1' lat='1'/>"]])
        result = ingest_bytes(data, source_kind="gpx", track_source=SOURCE)
        self.assertEqual([len(part["observations"]) for part in result.canonical_track["parts"]], [1, 1])
        self.assertIn("EMPTY_SOURCE_PART", [issue.code for issue in result.diagnostics])
        self.assertEqual([item.source.segment_index for item in result.observation_sources], [0, 2])

    def test_multiple_gpx_tracks_do_not_join(self):
        data = gpx([["<trkpt lon='0' lat='0'/>"]]).replace(b"</trk></gpx>", b"</trk><trk><trkseg><trkpt lon='2' lat='2'/></trkseg></trk></gpx>")
        result = ingest_bytes(data, source_kind="gpx", track_source=SOURCE)
        self.assertEqual([len(part["observations"]) for part in result.canonical_track["parts"]], [1, 1])
        self.assertEqual([item.source.track_index for item in result.observation_sources], [0, 1])

    def test_missing_gpx_timestamp_keeps_positions(self):
        result = self.raw("gpx/no-timestamps.gpx")
        self.assertEqual(positions(result), [[112.9, 28.2], [112.905, 28.205], [112.91, 28.21]])
        self.assertTrue(all("timestamp" not in obs for obs in observations(result)))

    def test_nonmonotonic_timestamps_are_not_sorted_or_repaired(self):
        data = gpx([["<trkpt lon='2' lat='0'><time>2026-10-07T00:00:10Z</time></trkpt>",
                     "<trkpt lon='1' lat='0'><time>2026-10-07T00:00:00Z</time></trkpt>"]])
        result = ingest_bytes(data, source_kind="gpx", track_source=SOURCE)
        self.assertEqual(positions(result), [[2.0, 0.0], [1.0, 0.0]])
        self.assertEqual([obs["timestamp"] for obs in observations(result)], ["2026-10-07T00:00:10Z", "2026-10-07T00:00:00Z"])
        self.assertEqual(result.diagnostics, ())

    def test_fit_source_record_order_is_not_timestamp_order(self):
        later = datetime(2026, 10, 7, 0, 0, 10, tzinfo=timezone.utc)
        earlier = datetime(2026, 10, 7, tzinfo=timezone.utc)
        result = ingest_bytes(build_fit([(later, 0, 0), (earlier, 0, 0)]), source_kind="fit", track_source=SOURCE)
        self.assertEqual([obs["timestamp"] for obs in observations(result)], ["2026-10-07T00:00:10Z", "2026-10-07T00:00:00Z"])
        self.assertEqual([item.source.record_index for item in result.observation_sources], [0, 1])
        self.assertEqual(len(result.canonical_track["parts"]), 1)

    def test_timezone_is_normalized_without_losing_fractional_precision(self):
        data = gpx([["<trkpt lon='0' lat='0'><time>2026-10-07T08:00:00.123456789+08:00</time></trkpt>"]])
        result = ingest_bytes(data, source_kind="gpx", track_source=SOURCE)
        self.assertEqual(observations(result)[0]["timestamp"], "2026-10-07T00:00:00.123456789Z")
        self.assertEqual(list(self.validator.iter_errors(result.canonical_track)), [])

    def test_timestamp_without_timezone_is_not_inferred(self):
        data = gpx([["<trkpt lon='0' lat='0'><time>2026-10-07T00:00:00</time></trkpt>"]])
        result = ingest_bytes(data, source_kind="gpx", track_source=SOURCE)
        self.assertEqual(positions(result), [[0.0, 0.0]])
        self.assertNotIn("timestamp", observations(result)[0])
        self.assertEqual([issue.code for issue in result.diagnostics], ["TIMESTAMP_TIMEZONE_MISSING"])

    def test_repeated_positions_and_repeated_visits_are_preserved(self):
        data = gpx([["<trkpt lon='0' lat='0'/>", "<trkpt lon='0' lat='0'/>",
                     "<trkpt lon='1' lat='0'/>", "<trkpt lon='0' lat='0'/>"]])
        result = ingest_bytes(data, source_kind="gpx", track_source=SOURCE)
        self.assertEqual(positions(result), [[0.0, 0.0], [0.0, 0.0], [1.0, 0.0], [0.0, 0.0]])
        self.assertEqual([item.position.observation_index for item in result.observation_sources], [0, 1, 2, 3])

    def test_fit_repeated_coordinates_are_not_deduplicated(self):
        time = datetime(2026, 10, 7, tzinfo=timezone.utc)
        result = ingest_bytes(build_fit([(time, 0, 0), (time, 0, 0), (time, 0, 1), (time, 0, 0)]), source_kind="fit", track_source=SOURCE)
        self.assertEqual(positions(result), [[0.0, 0.0], [0.0, 0.0], [round(2**31 / 180) * 180.0 / 2**31, 0.0], [0.0, 0.0]])
        self.assertEqual([item.source.record_index for item in result.observation_sources], [0, 1, 2, 3])

    def test_tiny_positive_gpx_coordinates_remain_distinct(self):
        for tiny in ("0.0000000000005", "0." + "0" * 199 + "1"):
            with self.subTest(tiny=tiny):
                result = ingest_bytes(gpx([["<trkpt lon='0' lat='0'/>", f"<trkpt lon='{tiny}' lat='0'/>"]]), source_kind="gpx", track_source=SOURCE)
                self.assertEqual(positions(result), [[0.0, 0.0], [float(tiny), 0.0]])
                self.assertGreater(positions(result)[1][0], 0)

    def test_one_fit_semicircle_step_survives_normalization(self):
        time = datetime(2026, 10, 7, tzinfo=timezone.utc)
        data = build_fit([(time, 0, 0), (time, 0, 180.0 / 2**31)])
        result = ingest_bytes(data, source_kind="fit", track_source=SOURCE)
        self.assertEqual(positions(result), [[0.0, 0.0], [180.0 / 2**31, 0.0]])

    def test_fit_supported_observed_telemetry_and_missing_timestamp(self):
        data = fit_record([(0, 4, 0x85), (1, 4, 0x85), (2, 2, 0x84), (5, 4, 0x86), (6, 2, 0x84)],
                          struct.pack("<iiHIH", 0, 0, 3000, 1000, 3500))
        result = ingest_bytes(data, source_kind="fit", track_source=SOURCE)
        self.assertEqual(observations(result), [{"position": [0.0, 0.0], "altitude_m": 100.0,
                                                 "distance_m": 10.0, "observed_speed_mps": 3.5}])
        self.assertEqual(list(self.validator.iter_errors(result.canonical_track)), [])

    def test_enhanced_fit_telemetry_uses_profile_units(self):
        data = fit_record([(0, 4, 0x85), (1, 4, 0x85), (2, 2, 0x84), (6, 2, 0x84),
                           (78, 4, 0x86), (73, 4, 0x86)], struct.pack("<iiHHII", 0, 0, 3000, 3500, 3500, 4000))
        result = ingest_bytes(data, source_kind="fit", track_source=SOURCE)
        self.assertEqual(observations(result), [{"position": [0.0, 0.0], "altitude_m": 200.0, "observed_speed_mps": 4.0}])

    def test_relative_fit_timestamp_is_not_inferred_as_calendar_time(self):
        data = fit_record([(253, 4, 0x86), (0, 4, 0x85), (1, 4, 0x85)], struct.pack("<Iii", 10, 0, 0))
        result = ingest_bytes(data, source_kind="fit", track_source=SOURCE)
        self.assertEqual(observations(result), [{"position": [0.0, 0.0]}])
        self.assertEqual([issue.code for issue in result.diagnostics], ["TIMESTAMP_RELATIVE"])

    def test_out_of_range_fit_coordinates_are_not_clamped(self):
        data = fit_record([(0, 4, 0x85), (1, 4, 0x85)], struct.pack("<ii", round(100 * 2**31 / 180), 0))
        result = ingest_bytes(data, source_kind="fit", track_source=SOURCE)
        self.assert_failure(result, "POSITION_OUT_OF_RANGE")

    def test_partial_position_sentinel_also_breaks_fit_continuity(self):
        time = datetime(2026, 10, 7, tzinfo=timezone.utc)
        data = build_fit([(time, 0, 0), (time, None, 1), (time, 0, 2)])
        result = ingest_bytes(data, source_kind="fit", track_source=SOURCE)
        self.assertEqual([len(part["observations"]) for part in result.canonical_track["parts"]], [1, 1])
        self.assertEqual([issue.source.record_index for issue in result.diagnostics], [1])

    def test_apparent_jump_is_preserved_without_quality_classification(self):
        result = ingest_bytes(gpx([["<trkpt lon='0' lat='0'/>", "<trkpt lon='170' lat='80'/>"]]), source_kind="gpx", track_source=SOURCE)
        self.assertEqual(positions(result), [[0.0, 0.0], [170.0, 80.0]])
        self.assertEqual(result.diagnostics, ())
        self.assertEqual(len(result.canonical_track["parts"]), 1)

    def test_gpx_altitude_is_observed_and_source_extensions_do_not_leak(self):
        result = ingest_bytes(gpx([["<trkpt lon='0' lat='0'><ele>-12.5</ele><extensions><x:hr xmlns:x='urn:test'>90</x:hr></extensions></trkpt>"]]), source_kind="gpx", track_source=SOURCE)
        self.assertEqual(observations(result), [{"position": [0.0, 0.0], "altitude_m": -12.5}])

    def test_equivalent_groups_use_exact_time_order_and_documented_fit_quantization(self):
        for group in self.manifest["equivalence_expectations"]:
            entries = [next(entry for entry in self.manifest["fixtures"] if entry["id"] == name) for name in group["members"]]
            results = [ingest_file(RAW / entry["path"], source_kind=entry["format"], track_source={"id": entry["id"], "revision_id": "r1"}) for entry in entries]
            with self.subTest(group=group["group"]):
                left, right = results
                self.assertEqual([len(p["observations"]) for p in left.canonical_track["parts"]], [len(p["observations"]) for p in right.canonical_track["parts"]])
                self.assertEqual([obs["timestamp"] for obs in observations(left)], [obs["timestamp"] for obs in observations(right)])
                # Existing fixtures encode nearest FIT semicircles. Half a
                # unit is the format error bound, not geometry-set similarity.
                tolerance = min(max(entry["normalization_expectation"].get("position_tolerance_deg", 0) for entry in entries), 90.0 / 2**31)
                for a, b in zip(positions(left), positions(right)):
                    for x, y in zip(a, b):
                        self.assertLessEqual(abs(x - y), tolerance)
                self.assertNotEqual(left.content_hash, right.content_hash)
                self.assertNotEqual(left.canonical_track["track_source"], right.canonical_track["track_source"])

    def test_repeated_ingestion_is_byte_deterministic_for_all_raw_cases(self):
        for entry in self.manifest["fixtures"]:
            with self.subTest(path=entry["path"]):
                first = self.raw(entry["path"])
                second = self.raw(entry["path"])
                self.assertEqual(first.to_json(), second.to_json())
                self.assertNotIn("NaN", first.to_json())

    def test_ingestion_never_changes_raw_file_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            for entry in self.manifest["fixtures"]:
                original = (RAW / entry["path"]).read_bytes()
                path = Path(directory) / Path(entry["path"]).name
                path.write_bytes(original)
                result = ingest_file(path, source_kind=entry["format"], track_source=SOURCE)
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(result.content_hash["digest"], hashlib.sha256(original).hexdigest())

    def test_hash_guard_and_source_revision_are_explicit(self):
        data = (RAW / "equivalent/basic.gpx").read_bytes()
        self.assert_failure(ingest_bytes(data, source_kind="gpx", track_source=SOURCE, expected_sha256="0" * 64), "SOURCE_HASH_MISMATCH")
        source = dict(SOURCE)
        result = ingest_bytes(data, source_kind="gpx", track_source=source)
        source["revision_id"] = "changed"
        self.assertEqual(result.canonical_track["track_source"], SOURCE)
        changed = ingest_bytes(data, source_kind="gpx", track_source=source)
        self.assertNotEqual(result.canonical_track["revision_id"], changed.canonical_track["revision_id"])

    def test_snapshot_mutation_does_not_change_result(self):
        result = self.raw("equivalent/basic.gpx")
        snapshot = result.to_dict()
        snapshot["canonical_track"]["parts"][0]["observations"].reverse()
        self.assertEqual(positions(result)[0], [112.9, 28.2])

    def test_fit_corruption_is_rejected_with_stable_reason(self):
        data = (RAW / "fit/complete-activity.fit").read_bytes()
        broken_crc = data[:-2] + bytes((data[-2] ^ 1, data[-1]))
        self.assert_failure(ingest_bytes(broken_crc, source_kind="fit", track_source=SOURCE), "FIT_CRC_MISMATCH")
        self.assert_failure(ingest_bytes(data[:-1], source_kind="fit", track_source=SOURCE), "MALFORMED_SOURCE")
        self.assert_failure(ingest_bytes(b"not a FIT file", source_kind="fit", track_source=SOURCE), "MALFORMED_SOURCE")

    def test_chained_fit_files_are_not_flattened_into_one_track(self):
        data = (RAW / "equivalent/basic.fit").read_bytes()
        self.assert_failure(ingest_bytes(data + data, source_kind="fit", track_source=SOURCE), "UNSUPPORTED_FIT_MULTIPLE_FILES")

    def test_gpx_dtd_is_rejected_without_network_or_entity_resolution(self):
        data = b'<!DOCTYPE gpx [<!ENTITY x SYSTEM "file:///etc/passwd">]>' + gpx([["<trkpt lon='0' lat='0'/>"]])
        self.assert_failure(ingest_bytes(data, source_kind="gpx", track_source=SOURCE), "UNSUPPORTED_GPX_DTD")

    def test_unsupported_gpx_route_semantics_are_explicit(self):
        data = b'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="test"><rte><rtept lon="0" lat="0"/></rte></gpx>'
        self.assert_failure(ingest_bytes(data, source_kind="gpx", track_source=SOURCE), "UNSUPPORTED_GPX_ROUTE_OR_WAYPOINT")

    def test_empty_track_source_produces_no_canonical_track(self):
        result = ingest_bytes(gpx([]), source_kind="gpx", track_source=SOURCE)
        self.assertEqual(result.outcome, "no_positioned_observations")
        self.assertEqual([issue.code for issue in result.diagnostics], ["NO_POSITIONED_OBSERVATIONS"])
        self.assertIsNone(result.canonical_track)

    def test_public_api_reports_read_and_source_kind_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assert_failure(ingest_file(Path(directory) / 'absent', source_kind="fit", track_source=SOURCE), "SOURCE_READ_FAILED")
        self.assert_failure(ingest_bytes(b"data", source_kind="other", track_source=SOURCE), "UNSUPPORTED_SOURCE_KIND")
        with self.assertRaisesRegex(ValueError, "INVALID_TRACK_SOURCE_REFERENCE"):
            ingest_bytes(b"data", source_kind="fit", track_source={"id": "source"})

    def test_unrepresentable_numeric_values_fail_closed(self):
        data = gpx([["<trkpt lon='0' lat='0'><ele>" + "9" * 400 + "</ele></trkpt>"]])
        self.assert_failure(ingest_bytes(data, source_kind="gpx", track_source=SOURCE), "NONFINITE_NUMERIC_VALUE")
        data = gpx([["<trkpt lon='0." + "0" * 999 + "1' lat='0'/>"]])
        self.assert_failure(ingest_bytes(data, source_kind="gpx", track_source=SOURCE), "NUMERIC_PRECISION_UNREPRESENTABLE")

    def test_frozen_continuity_witnesses_kill_joining_mutation(self):
        source = Path(normalization.__file__).read_text()
        mutations = (
            (source.replace("current = None  # absence", "pass  # absence"),
             "test_mixed_fit_has_two_singleton_parts_and_missing_record_neighbors"),
            (source.replace("    for index, part in enumerate(parts):", "    current = None\n    for index, part in enumerate(parts):")
                   .replace("        current: list[dict[str, Any]] | None = None", "        # mutant retains the preceding part"),
             "test_gpx_parts_and_original_point_locations"),
        )
        for mutated_source, witness in mutations:
            with self.subTest(witness=witness), tempfile.TemporaryDirectory() as directory:
                self.assertNotEqual(mutated_source, source)
                package = Path(directory) / "target_area_route_reconstruction"
                shutil.copytree(Path(normalization.__file__).parent, package,
                                ignore=shutil.ignore_patterns("__pycache__"))
                (package / "normalization.py").write_text(mutated_source)
                environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                               "PYTHONPATH": os.pathsep.join((directory, str(ROOT / "tests")))}
                result = subprocess.run([sys.executable, "-m", "unittest",
                                         "test_canonical_ingestion.CanonicalIngestionTests." + witness],
                                        env=environment, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("AssertionError", result.stderr)
                self.assertIn("Ran 1 test", result.stderr)

    def test_future_quality_positions_reference_original_parent_revision(self):
        result = self.raw("fit/mixed-position.fit")
        parent = result.canonical_track
        expected_source_records = [0, 2]
        for source_record, mapping in zip(expected_source_records, result.observation_sources):
            self.assertEqual(mapping.source.record_index, source_record)
            position = mapping.position
            obs = parent["parts"][position.part_index]["observations"][position.observation_index]
            self.assertIn("position", obs)
            self.assertEqual(position.fraction_to_next, 0)
        self.assertEqual(result.diagnostics[0].previous_position, result.observation_sources[0].position)
        self.assertEqual(result.diagnostics[0].next_position, result.observation_sources[1].position)
        self.assertTrue(parent["revision_id"].startswith("sha256:"))

    def test_packaged_xsd_matches_offline_baseline_semantics(self):
        packaged = files("target_area_route_reconstruction").joinpath("spec/gpx-1.1.xsd").read_bytes()
        expected = '\n'.join(line.expandtabs(4).rstrip() for line in (RAW / "spec/gpx-1.1.xsd").read_text().splitlines()) + '\n'
        self.assertEqual(packaged, expected.encode())
        schema = etree.XMLSchema(etree.fromstring(packaged))
        for entry in self.manifest["fixtures"]:
            if entry["format"] != "gpx" or entry["source_expectation"].get("failure_class") == "malformed_xml":
                continue
            self.assertEqual(schema.validate(etree.parse(str(RAW / entry["path"]))), entry["source_expectation"]["source_valid"])


if __name__ == "__main__":
    unittest.main()
