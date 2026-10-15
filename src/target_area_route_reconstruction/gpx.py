"""Offline GPX 1.1 conformance and original track/segment/point ordering."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
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
    schema_bytes = files("target_area_route_reconstruction").joinpath("spec/gpx-1.1.xsd").read_bytes()
    schema_parser = etree.XMLParser(resolve_entities=False, load_dtd=False,
                                    no_network=True, huge_tree=False)
    schema = etree.XMLSchema(etree.fromstring(schema_bytes, schema_parser))

    # First establish well-formed XML and reject DTDs before schema or domain
    # errors, matching the frozen failure precedence without retaining a tree.
    try:
        preflight = etree.iterparse(BytesIO(data), events=("start", "end"),
                                   resolve_entities=False, load_dtd=False,
                                   no_network=True, huge_tree=False)
        root_seen = False
        for event, element in preflight:
            if event == "start" and not root_seen:
                root_seen = True
                if element.getroottree().docinfo.doctype:
                    raise SourceFailure("UNSUPPORTED_GPX_DTD")
            if event == "end":
                parent = element.getparent()
                element.clear()
                if parent is not None:
                    while element.getprevious() is not None:
                        del parent[0]
    except SourceFailure:
        raise
    except etree.XMLSyntaxError as exc:
        raise SourceFailure("MALFORMED_SOURCE") from exc

    # Validate and capture only the small fields needed for the canonical
    # model. Clearing completed points/segments keeps the XML tree bounded by
    # the current parser frontier; the retained result is bounded separately
    # by max_observations/max_parts.
    raw_parts: list[tuple[SourceLocation, tuple[tuple[SourceLocation, str, str, str | None, str | None], ...]]] = []
    record_index = 0
    track_index = -1
    segment_index = -1
    point_index = 0
    samples: list[tuple[SourceLocation, str, str, str | None, str | None]] | None = None
    unsupported_path = False
    root = None
    context = etree.iterparse(BytesIO(data), events=("start", "end"), schema=schema,
                              resolve_entities=False, load_dtd=False, no_network=True,
                              huge_tree=False)
    try:
        for event, element in context:
            if event == "start":
                if root is None:
                    root = element
                    if element.getroottree().docinfo.doctype:
                        raise SourceFailure("UNSUPPORTED_GPX_DTD")
                if element.tag == NS + "trk":
                    track_index += 1
                    segment_index = -1
                elif element.tag == NS + "trkseg":
                    if len(raw_parts) >= max_parts:
                        raise SourceFailure("PART_OR_INTERVAL_LIMIT_EXCEEDED")
                    segment_index += 1
                    point_index = 0
                    samples = []
                elif element.tag in (NS + "rte", NS + "wpt"):
                    unsupported_path = True
                continue

            if element.tag == NS + "trkpt":
                if record_index >= max_observations:
                    raise SourceFailure("OBSERVATION_LIMIT_EXCEEDED")
                location = SourceLocation("gpx", record_index, track_index, segment_index, point_index)
                record_index += 1
                point_index += 1
                elevation = element.find(NS + "ele")
                timestamp = element.find(NS + "time")
                if samples is None:
                    raise SourceFailure("INVALID_GPX_STRUCTURE")
                samples.append((location, element.attrib["lon"], element.attrib["lat"],
                                elevation.text if elevation is not None else None,
                                timestamp.text if timestamp is not None else None))
                parent = element.getparent()
                element.clear()
                if parent is not None:
                    while element.getprevious() is not None:
                        del parent[0]
            elif element.tag == NS + "trkseg":
                if samples is None:
                    raise SourceFailure("INVALID_GPX_STRUCTURE")
                raw_parts.append((SourceLocation("gpx", None, track_index, segment_index), tuple(samples)))
                samples = None
                parent = element.getparent()
                element.clear()
                if parent is not None:
                    while element.getprevious() is not None:
                        del parent[0]
            elif element.tag == NS + "trk":
                parent = element.getparent()
                element.clear()
                if parent is not None:
                    while element.getprevious() is not None:
                        del parent[0]
            elif root is not None and element.getparent() is root:
                element.clear()
                while element.getprevious() is not None:
                    del root[0]
    except SourceFailure:
        raise
    except etree.XMLSyntaxError as exc:
        # The preflight pass already proved the bytes are well-formed XML.
        raise SourceFailure("INVALID_GPX_STRUCTURE") from exc

    # M2A's frozen GPX baseline defines track segments. Route/waypoint-only
    # paths do not supply that continuity contract and must not be invented.
    if unsupported_path:
        raise SourceFailure("UNSUPPORTED_GPX_ROUTE_OR_WAYPOINT")

    parts: list[ParsedPart] = []
    for source_location, raw_samples in raw_parts:
        samples: list[ParsedSample] = []
        for location, longitude, latitude, elevation, timestamp_text in raw_samples:
            position = [finite_number(longitude, location, "lon"),
                        finite_number(latitude, location, "lat")]
            observation: dict[str, Any] = {"position": position}
            if elevation is not None:
                observation["altitude_m"] = finite_number(elevation, location, "ele")
            diagnostics: tuple[Diagnostic, ...] = ()
            if timestamp_text is not None:
                timestamp_text = timestamp_text.strip()
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
        parts.append(ParsedPart(source_location, tuple(samples)))
    return tuple(parts)
