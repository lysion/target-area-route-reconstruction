#!/usr/bin/env python3
"""Generate deterministic, privacy-safe raw FIT/GPX test fixtures.

This is test-fixture tooling, not the production Milestone 2 parser.
The FIT writer retains the original minimal FileId/Record examples and also
emits one representative Activity file with Lap, Session, and Activity summary
messages. It is fixture tooling, not production parsing.
"""

from __future__ import annotations

import argparse
import struct
from datetime import datetime, timezone
from pathlib import Path

CRC_TABLE = (
    0x0000, 0xCC01, 0xD801, 0x1400,
    0xF001, 0x3C00, 0x2800, 0xE401,
    0xA001, 0x6C00, 0x7800, 0xB401,
    0x5000, 0x9C01, 0x8801, 0x4400,
)
FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)


def fit_crc(data: bytes, crc: int = 0) -> int:
    for byte in data:
        tmp = CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ tmp ^ CRC_TABLE[byte & 0xF]
        tmp = CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ tmp ^ CRC_TABLE[(byte >> 4) & 0xF]
    return crc


def fit_timestamp(value: datetime) -> int:
    return int((value - FIT_EPOCH).total_seconds())


def semicircles(degrees: float) -> int:
    return int(round(degrees * (2**31) / 180.0))


def definition_message(
    local_message: int,
    global_message: int,
    fields: list[tuple[int, int, int]],
) -> bytes:
    data = bytearray([0x40 | local_message, 0x00, 0x00])
    data.extend(struct.pack("<H", global_message))
    data.append(len(fields))
    for field_number, size, base_type in fields:
        data.extend((field_number, size, base_type))
    return bytes(data)


def data_message(local_message: int, payload: bytes) -> bytes:
    return bytes([local_message]) + payload


def file_id_block(created: datetime) -> bytes:
    fields = [
        (0, 1, 0x00),
        (1, 2, 0x84),
        (2, 2, 0x84),
        (3, 4, 0x8C),
        (4, 4, 0x86),
    ]
    payload = struct.pack(
        "<BHHII",
        4,          # file type: activity
        1,          # manufacturer: Garmin (arbitrary standard enum for fixture)
        1,          # product: deterministic fixture value
        123456789,
        fit_timestamp(created),
    )
    return definition_message(0, 0, fields) + data_message(0, payload)


def build_fit(
    records: list[tuple[datetime, float | None, float | None]],
    *,
    complete_activity: bool = False,
    force_position_fields: bool = False,
) -> bytes:
    created = records[0][0]
    data = bytearray(file_id_block(created))

    with_positions = force_position_fields or any(lat is not None and lon is not None for _, lat, lon in records)
    if with_positions:
        fields = [(253, 4, 0x86), (0, 4, 0x85), (1, 4, 0x85)]
        data.extend(definition_message(1, 20, fields))
        for timestamp, lat, lon in records:
            data.extend(
                data_message(
                    1,
                    struct.pack(
                        "<Iii",
                        fit_timestamp(timestamp),
                        semicircles(lat) if lat is not None else 0x7FFFFFFF,
                        semicircles(lon) if lon is not None else 0x7FFFFFFF,
                    ),
                )
            )
    else:
        fields = [(253, 4, 0x86)]
        data.extend(definition_message(1, 20, fields))
        for timestamp, _, _ in records:
            data.extend(
                data_message(1, struct.pack("<I", fit_timestamp(timestamp)))
            )

    if complete_activity:
        start = fit_timestamp(records[0][0])
        end = fit_timestamp(records[-1][0])
        elapsed_ms = (end - start) * 1000
        summary_fields = [
            (253, 4, 0x86),  # timestamp
            (254, 2, 0x84),  # message_index
            (2, 4, 0x86),    # start_time
            (7, 4, 0x86),    # total_elapsed_time, scaled by 1000
            (8, 4, 0x86),    # total_timer_time, scaled by 1000
        ]
        for local, global_number in ((2, 19), (3, 18)):
            fields = summary_fields + [(0, 1, 0x00), (1, 1, 0x00)]
            payload = struct.pack("<IHIIIBB", end, 0, start, elapsed_ms, elapsed_ms,
                                  9 if global_number == 19 else 8, 1)  # lap/session stop
            if global_number == 18:
                fields += [(5, 1, 0x00), (25, 2, 0x84), (26, 2, 0x84)]
                payload += struct.pack("<BHH", 1, 0, 1)  # running, first lap, lap count
            else:
                fields += [(25, 1, 0x00)]
                payload += struct.pack("<B", 1)  # running
            data.extend(definition_message(local, global_number, fields))
            data.extend(data_message(local, payload))
        activity_fields = [
            (253, 4, 0x86), (0, 4, 0x86), (1, 2, 0x84),
            (2, 1, 0x00), (3, 1, 0x00), (4, 1, 0x00), (5, 4, 0x86),
        ]
        data.extend(definition_message(4, 34, activity_fields))
        data.extend(data_message(4, struct.pack("<IIHBBBI", end, elapsed_ms, 1, 0, 26, 1, end)))

    header = bytearray([14 if complete_activity else 12, 0x20])
    header.extend(struct.pack("<H", 2100))
    header.extend(struct.pack("<I", len(data)))
    header.extend(b".FIT")
    if complete_activity:
        header.extend(struct.pack("<H", fit_crc(header)))

    without_crc = bytes(header) + bytes(data)
    return without_crc + struct.pack("<H", fit_crc(without_crc))


def build_gpx(
    records: list[tuple[datetime, float, float]],
    *,
    include_time: bool = True,
    split_at: int | None = None,
) -> str:
    chunks = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="target-area-route-reconstruction" '
        'xmlns="http://www.topografix.com/GPX/1/1">',
        '<trk><name>Synthetic fixture</name>',
    ]
    segments = [records] if split_at is None else [records[:split_at], records[split_at:]]

    for segment in segments:
        chunks.append("<trkseg>")
        for timestamp, lat, lon in segment:
            chunks.append(f'<trkpt lat="{lat:.7f}" lon="{lon:.7f}">')
            if include_time:
                chunks.append(
                    f"<time>{timestamp.isoformat().replace('+00:00', 'Z')}</time>"
                )
            chunks.append("</trkpt>")
        chunks.append("</trkseg>")

    chunks.extend(("</trk>", "</gpx>"))
    return "\n".join(chunks) + "\n"


def write_fixtures(root: Path) -> None:
    (root / "equivalent").mkdir(parents=True, exist_ok=True)
    (root / "gpx").mkdir(parents=True, exist_ok=True)
    (root / "fit").mkdir(parents=True, exist_ok=True)

    basic = [
        (datetime(2026, 10, 7, 0, 0, 0, tzinfo=timezone.utc), 28.2000, 112.9000),
        (datetime(2026, 10, 7, 0, 0, 10, tzinfo=timezone.utc), 28.2050, 112.9050),
        (datetime(2026, 10, 7, 0, 0, 20, tzinfo=timezone.utc), 28.2100, 112.9100),
    ]
    discontinuity = [
        (datetime(2026, 10, 7, 1, 0, 0, tzinfo=timezone.utc), 28.2000, 112.9000),
        (datetime(2026, 10, 7, 1, 0, 10, tzinfo=timezone.utc), 28.2020, 112.9020),
        (datetime(2026, 10, 7, 1, 1, 0, tzinfo=timezone.utc), 28.2080, 112.9080),
        (datetime(2026, 10, 7, 1, 1, 10, tzinfo=timezone.utc), 28.2100, 112.9100),
    ]

    (root / "equivalent" / "basic.gpx").write_text(
        build_gpx(basic), encoding="utf-8"
    )
    (root / "equivalent" / "basic.fit").write_bytes(
        build_fit([(t, lat, lon) for t, lat, lon in basic])
    )
    (root / "gpx" / "no-timestamps.gpx").write_text(
        build_gpx(basic, include_time=False), encoding="utf-8"
    )
    (root / "gpx" / "discontinuity.gpx").write_text(
        build_gpx(discontinuity, split_at=2), encoding="utf-8"
    )
    (root / "gpx" / "malformed.gpx").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">\n'
        '<trk><trkseg><trkpt lat="28.2" lon="112.9"></trkseg></trk>\n'
        '</gpx>\n',
        encoding="utf-8",
    )
    (root / "fit" / "no-position.fit").write_bytes(
        build_fit([(t, None, None) for t, _, _ in basic])
    )
    (root / "fit" / "complete-activity.fit").write_bytes(
        build_fit(basic, complete_activity=True)
    )
    (root / "fit" / "invalid-position-sentinel.fit").write_bytes(
        build_fit([(t, None, None) for t, _, _ in basic], force_position_fields=True)
    )
    (root / "fit" / "mixed-position.fit").write_bytes(
        build_fit([basic[0], (basic[1][0], None, None), basic[2]])
    )
    original_gpx = (root / "equivalent" / "basic.gpx").read_text(encoding="utf-8")
    (root / "gpx" / "invalid-root.gpx").write_text(
        original_gpx.replace("<gpx ", "<notgpx ").replace("</gpx>", "</notgpx>"), encoding="utf-8"
    )
    (root / "gpx" / "invalid-range.gpx").write_text(
        original_gpx.replace('lat="28.2000000"', 'lat="91.0000000"', 1), encoding="utf-8"
    )
    (root / "gpx" / "invalid-version.gpx").write_text(
        original_gpx.replace('version="1.1"', 'version="1.0"', 1), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/source-fixtures"),
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    output = args.output_dir
    if not output.is_absolute():
        output = repo_root / output
    write_fixtures(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
