#!/usr/bin/env python3
"""Validate the synthetic raw FIT/GPX source-fixture baseline.

This is an integrity/conformance reader for test data, not the production
Milestone 2 ingestion implementation. It verifies bytes, basic source
structure, FIT CRC/records, GPX segmentation/timestamps, and the declared
GPX/FIT equivalence baseline.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CRC_TABLE = (
    0x0000, 0xCC01, 0xD801, 0x1400,
    0xF001, 0x3C00, 0x2800, 0xE401,
    0xA001, 0x6C00, 0x7800, 0xB401,
    0x5000, 0x9C01, 0x8801, 0x4400,
)
FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)
GPX_NS = {"g": "http://www.topografix.com/GPX/1/1"}


class FixtureError(RuntimeError):
    pass


def fit_crc(data: bytes, crc: int = 0) -> int:
    for byte in data:
        tmp = CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ tmp ^ CRC_TABLE[byte & 0xF]
        tmp = CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ tmp ^ CRC_TABLE[(byte >> 4) & 0xF]
    return crc


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureError(f"cannot load JSON {path}: {exc}") from exc


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_gpx(path: Path, source_valid: bool) -> dict[str, Any]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        if source_valid:
            raise FixtureError(f"{path}: expected valid GPX, parse failed: {exc}") from exc
        return {"source_valid": False, "failure_class": "malformed_xml"}

    if not source_valid:
        raise FixtureError(f"{path}: expected malformed GPX but XML parsed successfully")

    tracks = root.findall("g:trk", GPX_NS)
    segments = root.findall(".//g:trkseg", GPX_NS)
    points = root.findall(".//g:trkpt", GPX_NS)
    times = root.findall(".//g:trkpt/g:time", GPX_NS)

    positions = [
        (float(point.attrib["lon"]), float(point.attrib["lat"]))
        for point in points
    ]
    timestamps = [
        time.text for time in times if time.text is not None
    ]
    return {
        "source_valid": True,
        "track_count": len(tracks),
        "segment_count": len(segments),
        "point_count": len(points),
        "timestamp_count": len(times),
        "positions": positions,
        "timestamps": timestamps,
    }


def decode_fit_value(raw: bytes, base_type: int, endian: str) -> int:
    if len(raw) == 1:
        return raw[0]
    if len(raw) == 2:
        return struct.unpack(endian + "H", raw)[0]
    if len(raw) == 4:
        signed = base_type == 0x85
        return struct.unpack(endian + ("i" if signed else "I"), raw)[0]
    raise FixtureError(f"unsupported synthetic FIT field size: {len(raw)}")


def read_fit(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 14:
        raise FixtureError(f"{path}: FIT file too short")

    header_size = data[0]
    if header_size not in (12, 14):
        raise FixtureError(f"{path}: unsupported FIT header size {header_size}")
    if data[8:12] != b".FIT":
        raise FixtureError(f"{path}: missing FIT signature")

    payload_size = struct.unpack_from("<I", data, 4)[0]
    expected_size = header_size + payload_size + 2
    if len(data) != expected_size:
        raise FixtureError(
            f"{path}: length {len(data)} != declared {expected_size}"
        )

    stored_crc = struct.unpack_from("<H", data, len(data) - 2)[0]
    calculated_crc = fit_crc(data[:-2])
    if stored_crc != calculated_crc or fit_crc(data) != 0:
        raise FixtureError(f"{path}: FIT CRC mismatch")

    payload = data[header_size : header_size + payload_size]
    definitions: dict[int, tuple[int, list[tuple[int, int, int]], str]] = {}
    messages: list[tuple[int, dict[int, int]]] = []
    offset = 0

    while offset < len(payload):
        header = payload[offset]
        offset += 1
        if header & 0x80:
            raise FixtureError(f"{path}: compressed timestamp headers are outside fixture subset")

        local = header & 0x0F
        if header & 0x40:
            if offset + 5 > len(payload):
                raise FixtureError(f"{path}: truncated FIT definition")
            offset += 1  # reserved
            architecture = payload[offset]
            offset += 1
            endian = "<" if architecture == 0 else ">"
            global_message = struct.unpack_from(endian + "H", payload, offset)[0]
            offset += 2
            field_count = payload[offset]
            offset += 1
            fields = []
            for _ in range(field_count):
                if offset + 3 > len(payload):
                    raise FixtureError(f"{path}: truncated FIT field definition")
                number, size, base_type = payload[offset : offset + 3]
                offset += 3
                fields.append((number, size, base_type))
            definitions[local] = (global_message, fields, endian)
            continue

        if local not in definitions:
            raise FixtureError(f"{path}: data message references undefined local {local}")

        global_message, fields, endian = definitions[local]
        values: dict[int, int] = {}
        for number, size, base_type in fields:
            if offset + size > len(payload):
                raise FixtureError(f"{path}: truncated FIT data message")
            raw = payload[offset : offset + size]
            offset += size
            values[number] = decode_fit_value(raw, base_type, endian)
        messages.append((global_message, values))

    file_ids = [values for global_number, values in messages if global_number == 0]
    records = [values for global_number, values in messages if global_number == 20]
    if len(file_ids) != 1:
        raise FixtureError(f"{path}: expected exactly one FileId message")

    file_type = file_ids[0].get(0)
    positions = []
    timestamps = []
    positioned = 0
    timestamped = 0

    for record in records:
        if 253 in record:
            timestamped += 1
            timestamps.append(
                (FIT_EPOCH + timedelta(seconds=record[253]))
                .isoformat()
                .replace("+00:00", "Z")
            )
        if 0 in record and 1 in record:
            positioned += 1
            lat = record[0] * 180.0 / (2**31)
            lon = record[1] * 180.0 / (2**31)
            positions.append((lon, lat))

    return {
        "source_valid": True,
        "fit_crc_valid": True,
        "file_type": "activity" if file_type == 4 else str(file_type),
        "record_message_count": len(records),
        "positioned_record_count": positioned,
        "timestamped_record_count": timestamped,
        "positions": positions,
        "timestamps": timestamps,
    }


def assert_subset(actual: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value != expected_value:
            raise FixtureError(
                f"{label}: {key} expected {expected_value!r}, got {actual_value!r}"
            )


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    root = repo_root / "tests/source-fixtures"
    manifest = load_json(root / "manifest.json")
    fixtures = manifest.get("fixtures", [])
    if not isinstance(fixtures, list) or not fixtures:
        print("ERROR: source fixture manifest has no fixtures", file=sys.stderr)
        return 2

    observed: dict[str, dict[str, Any]] = {}

    try:
        for entry in fixtures:
            fixture_id = entry["id"]
            path = root / entry["path"]
            if not path.is_file():
                raise FixtureError(f"{fixture_id}: missing file {path}")
            if sha256(path) != entry["sha256"]:
                raise FixtureError(f"{fixture_id}: SHA-256 mismatch")

            if entry["format"] == "gpx":
                actual = read_gpx(
                    path,
                    bool(entry["source_expectation"]["source_valid"]),
                )
            elif entry["format"] == "fit":
                actual = read_fit(path)
            else:
                raise FixtureError(
                    f"{fixture_id}: unsupported fixture format {entry['format']!r}"
                )

            assert_subset(actual, entry["source_expectation"], fixture_id)
            observed[fixture_id] = actual
            print(f"PASS {entry['path']}")

        for equivalence in manifest.get("equivalence_expectations", []):
            members = equivalence["members"]
            if len(members) != 2:
                raise FixtureError(
                    f"equivalence group {equivalence['group']}: expected two members"
                )
            left, right = (observed[members[0]], observed[members[1]])
            left_entry = next(item for item in fixtures if item["id"] == members[0])
            right_entry = next(item for item in fixtures if item["id"] == members[1])
            tolerance = max(
                left_entry["normalization_expectation"].get("position_tolerance_deg", 0),
                right_entry["normalization_expectation"].get("position_tolerance_deg", 0),
            )
            if len(left["positions"]) != len(right["positions"]):
                raise FixtureError(
                    f"equivalence group {equivalence['group']}: position count differs"
                )
            for index, (a, b) in enumerate(zip(left["positions"], right["positions"])):
                if not (
                    math.isclose(a[0], b[0], rel_tol=0.0, abs_tol=tolerance)
                    and math.isclose(a[1], b[1], rel_tol=0.0, abs_tol=tolerance)
                ):
                    raise FixtureError(
                        f"equivalence group {equivalence['group']}: "
                        f"position {index} differs: {a!r} vs {b!r}"
                    )
            if left["timestamps"] != right["timestamps"]:
                raise FixtureError(
                    f"equivalence group {equivalence['group']}: timestamps differ"
                )
            print(f"PASS equivalence:{equivalence['group']}")

    except (FixtureError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(
        f"Raw source fixture baseline: {len(fixtures)}/{len(fixtures)} files verified; "
        f"{len(manifest.get('equivalence_expectations', []))} equivalence group(s) verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
