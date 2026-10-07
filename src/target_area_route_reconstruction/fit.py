"""FIT Record source semantics, decoded by the pinned independent library."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import fitdecode

from ._values import finite_number, utc_timestamp
from .models import Diagnostic, ParsedPart, ParsedSample, SourceFailure, SourceLocation


def _value(frame: Any, name: str) -> Any:
    fields = list(frame.get_fields(name))
    # fitdecode may expand basic altitude/speed into same-named enhanced
    # components BEFORE a native enhanced field. Preserve the native value.
    native = [field for field in fields if not field.is_expanded]
    return (native or fields)[0].value if fields else None


def _record(frame: Any, index: int) -> ParsedSample:
    location = SourceLocation("fit", index)
    lat = frame.get_value("position_lat", fallback=None)
    lon = frame.get_value("position_long", fallback=None)
    if lat is None or lon is None:
        fields = {field.name for field in frame.fields}
        reason = "POSITION_INVALID_SENTINEL" if {"position_lat", "position_long"} <= fields else "POSITION_MISSING"
        return ParsedSample(location, None, (Diagnostic(reason, location, "position"),))

    latitude = finite_number(lat, location, "position_lat") * (180.0 / 2**31)
    longitude = finite_number(lon, location, "position_long") * (180.0 / 2**31)
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise SourceFailure("POSITION_OUT_OF_RANGE", location, "position")
    observation: dict[str, Any] = {"position": [longitude, latitude]}
    diagnostics: tuple[Diagnostic, ...] = ()
    timestamp = frame.get_value("timestamp", fallback=None)
    if timestamp is not None:
        # FIT date_time values below this threshold are relative system time,
        # not evidence of a UTC calendar date.
        if frame.get_raw_value("timestamp") < 0x10000000:
            diagnostics = (Diagnostic("TIMESTAMP_RELATIVE", location, "timestamp"),)
        else:
            if not isinstance(timestamp, datetime):
                raise SourceFailure("INVALID_OBSERVATION_VALUE", location, "timestamp")
            text, diagnostics = utc_timestamp(timestamp, location)
            if text is not None:
                observation["timestamp"] = text
    for candidates, canonical in (
        (("enhanced_altitude", "altitude"), "altitude_m"),
        (("distance",), "distance_m"),
        (("enhanced_speed", "speed"), "observed_speed_mps"),
    ):
        for name in candidates:
            value = _value(frame, name)
            if value is not None:
                number = finite_number(value, location, name)
                if canonical != "altitude_m" and number < 0:
                    raise SourceFailure("INVALID_OBSERVATION_VALUE", location, name)
                observation[canonical] = number
                break
    return ParsedSample(location, observation, diagnostics)


def parse_fit(data: bytes) -> tuple[ParsedPart, ...]:
    samples: list[ParsedSample] = []
    file_ids = 0
    headers = 0
    try:
        with fitdecode.FitReader(io.BytesIO(data), check_crc=fitdecode.CrcCheck.RAISE,
                                 error_handling=fitdecode.ErrorHandling.RAISE) as reader:
            for frame in reader:
                if isinstance(frame, fitdecode.FitHeader):
                    headers += 1
                    if headers > 1:
                        raise SourceFailure("UNSUPPORTED_FIT_MULTIPLE_FILES")
                elif isinstance(frame, fitdecode.FitDataMessage):
                    if not file_ids and frame.name != "file_id":
                        raise SourceFailure("FIT_FILE_ID_MISSING")
                    if frame.name == "file_id":
                        file_ids += 1
                        if file_ids != 1 or frame.get_value("type", fallback=None) != "activity":
                            raise SourceFailure("UNSUPPORTED_FIT_FILE_TYPE")
                    elif frame.name == "record":
                        if not file_ids:
                            raise SourceFailure("FIT_FILE_ID_MISSING")
                        samples.append(_record(frame, len(samples)))
    except fitdecode.FitCRCError as exc:
        raise SourceFailure("FIT_CRC_MISMATCH") from exc
    except (fitdecode.FitError, ValueError, OverflowError, TypeError) as exc:
        raise SourceFailure("MALFORMED_SOURCE") from exc
    if headers == 0:
        raise SourceFailure("MALFORMED_SOURCE")
    if file_ids != 1:
        raise SourceFailure("FIT_FILE_ID_MISSING")
    return (ParsedPart(SourceLocation("fit", None), tuple(samples)),)
