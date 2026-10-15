"""Offline GPX 1.1 conformance and original track/segment/point ordering."""

from __future__ import annotations

from datetime import datetime
import re
from importlib.resources import files
from typing import Any

from lxml import etree

from ._values import finite_number, utc_timestamp
from .models import Diagnostic, ParsedPart, ParsedSample, SourceFailure, SourceLocation
from .resource_limits import MAX_POSITIONED_OBSERVATIONS, MAX_CONTINUITY_PARTS, validate_limit

NS = "{http://www.topografix.com/GPX/1/1}"


def parse_gpx(data: bytes, *, max_observations: int = MAX_POSITIONED_OBSERVATIONS,
              max_parts: int = MAX_CONTINUITY_PARTS) -> tuple[ParsedPart, ...]:
    validate_limit(max_observations, MAX_POSITIONED_OBSERVATIONS, "INVALID_OBSERVATION_LIMIT")
    validate_limit(max_parts, MAX_CONTINUITY_PARTS, "INVALID_PART_LIMIT")
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False)
    try:
        root = etree.fromstring(data, parser)
    except etree.XMLSyntaxError as exc:
        raise SourceFailure("MALFORMED_SOURCE") from exc
    if root.getroottree().docinfo.doctype:
        raise SourceFailure("UNSUPPORTED_GPX_DTD")
    schema_bytes = files("target_area_route_reconstruction").joinpath("spec/gpx-1.1.xsd").read_bytes()
    schema = etree.XMLSchema(etree.fromstring(schema_bytes, parser))
    if not schema.validate(root):
        raise SourceFailure("INVALID_GPX_STRUCTURE")
    # M2A's frozen GPX baseline defines track segments. Route/waypoint-only
    # paths do not supply that continuity contract and must not be invented.
    if root.findall(NS + "rte") or root.findall(NS + "wpt"):
        raise SourceFailure("UNSUPPORTED_GPX_ROUTE_OR_WAYPOINT")

    parts: list[ParsedPart] = []
    record_index = 0
    for track_index, track in enumerate(root.findall(NS + "trk")):
        for segment_index, segment in enumerate(track.findall(NS + "trkseg")):
            if len(parts) >= max_parts:
                raise SourceFailure("PART_OR_INTERVAL_LIMIT_EXCEEDED")
            samples: list[ParsedSample] = []
            for point_index, point in enumerate(segment.findall(NS + "trkpt")):
                if record_index >= max_observations:
                    raise SourceFailure("OBSERVATION_LIMIT_EXCEEDED")
                location = SourceLocation("gpx", record_index, track_index, segment_index, point_index)
                record_index += 1
                position = [finite_number(point.attrib[axis], location, axis) for axis in ("lon", "lat")]
                observation: dict[str, Any] = {"position": position}
                diagnostics: tuple[Diagnostic, ...] = ()
                elevation = point.find(NS + "ele")
                if elevation is not None:
                    observation["altitude_m"] = finite_number(elevation.text, location, "ele")
                timestamp = point.find(NS + "time")
                if timestamp is not None:
                    timestamp_text = timestamp.text.strip()
                    try:
                        value = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
                    except ValueError:
                        diagnostics = (Diagnostic("TIMESTAMP_UNREPRESENTABLE", location, "timestamp"),)
                    else:
                        fraction = re.search(r"T\d{2}:\d{2}:\d{2}\.([0-9]+)", timestamp_text)
                        text, diagnostics = utc_timestamp(value, location,
                                                          fractional_second=fraction.group(1) if fraction else None)
                        if text is not None:
                            observation["timestamp"] = text
                samples.append(ParsedSample(location, observation, diagnostics))
            parts.append(ParsedPart(SourceLocation("gpx", None, track_index, segment_index), tuple(samples)))
    return tuple(parts)
