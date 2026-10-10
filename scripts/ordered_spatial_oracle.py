"""Milestone 1 oracle for observed coverage in ordered parent-track space.

Geometry predicates locate covered portions of each *existing* observation
edge. Part index, edge index, and interpolation fraction retain the identity
of each traversal; topological set equality is never a coverage proof.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any, Iterator

from shapely.geometry import LineString, Point


@dataclass(frozen=True, order=True)
class Position:
    part_index: int
    observation_index: int
    fraction_to_next: float


@dataclass(frozen=True)
class Interval:
    start: Position
    end: Position


@dataclass(frozen=True)
class ObservedFacts:
    inside: bool
    outside: bool


@dataclass(frozen=True)
class NumericalPolicy:
    """Coordinate comparison error only; it never sets minimum route length.

    The cap tolerates binary64/GEOS interpolation noise in OGC:CRS84 degrees.
    For short edges it shrinks below one quarter of the edge length so a true
    short covered interval cannot be equated with a collapsed endpoint.
    """

    coordinate_error_cap_deg: float = 1e-12

    def coordinate_error(self, *, scale: float, local_length: float) -> float:
        return min(self.coordinate_error_cap_deg, 8 * math.ulp(scale), local_length / 4)

    def coordinates_close(
        self,
        left: tuple[float, float] | list[float],
        right: tuple[float, float] | list[float],
        *,
        local_length: float,
        operand_scale: float = 0.0,
    ) -> bool:
        scale = max(operand_scale, *(abs(float(x)) for x in (*left, *right)))
        allowed = self.coordinate_error(scale=scale, local_length=local_length)
        return all(abs(float(a) - float(b)) <= allowed for a, b in zip(left, right))


POLICY = NumericalPolicy()


def positive_length(coordinates: Any) -> bool:
    """Distinct adjacent represented positions imply length, without a cutoff."""
    points = list(coordinates)
    return any(tuple(a) != tuple(b) for a, b in zip(points, points[1:]))


def coordinate_length(coordinates: Any) -> float:
    points = list(coordinates)
    return math.fsum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def track_scale(track: dict[str, Any]) -> float:
    return max(abs(value) for part in track["parts"] for obs in part["observations"] for value in obs["position"])


def _position(part: int, edge: int, fraction: float) -> Position:
    if fraction <= 0:
        return Position(part, edge, 0.0)
    if fraction >= 1:
        return Position(part, edge + 1, 0.0)
    return Position(part, edge, fraction)


def _linear_components(geometry: Any) -> Iterator[LineString]:
    if geometry.is_empty:
        return
    if isinstance(geometry, LineString):
        if positive_length(geometry.coords):
            yield geometry
        return
    for component in getattr(geometry, "geoms", ()):
        yield from _linear_components(component)


def observed_edges(track: dict[str, Any]) -> Iterator[tuple[int, int, LineString]]:
    """The only source of assessment edges; array part boundaries are excluded."""
    for part_index, part in enumerate(track["parts"]):
        observations = part["observations"]
        for edge_index in range(len(observations) - 1):
            edge = LineString((
                observations[edge_index]["position"],
                observations[edge_index + 1]["position"],
            ))
            if positive_length(edge.coords):
                yield part_index, edge_index, edge


def _geos_overlay_or_fail(edge, area, method):
    """M1's GEOS-based fixtures are NOT an independent numerical oracle.

    A GEOS RuntimeWarning about division by zero or invalid floating-point
    math invalidates a claimed coverage result even if a geometry is returned.
    The separate R2 Fraction rectangle witness tests actual math without GEOS.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            return getattr(edge, method)(area)
    except RuntimeWarning as exc:
        raise ValueError("ORACLE_NUMERICAL_FAILURE") from exc


def observed_facts(track: dict[str, Any], area: Any) -> ObservedFacts:
    inside = outside = False
    for _, _, edge in observed_edges(track):
        inside |= any(True for _ in _linear_components(_geos_overlay_or_fail(edge, area, "intersection")))
        outside |= any(True for _ in _linear_components(_geos_overlay_or_fail(edge, area, "difference")))
    return ObservedFacts(inside, outside)


def _gap_is_zero_and_covered(
    track: dict[str, Any], area: Any, end: Position, start: Position
) -> bool:
    if end.part_index != start.part_index or end > start:
        return False
    if end == start:
        return True
    observations = track["parts"][end.part_index]["observations"]
    if end.fraction_to_next != 0 or start.fraction_to_next != 0:
        return False
    for index in range(end.observation_index, start.observation_index):
        left = observations[index]["position"]
        right = observations[index + 1]["position"]
        if left != right or not area.covers(Point(left)):
            return False
    return True


def covered_intervals(track: dict[str, Any], area: Any) -> list[Interval]:
    """Return every maximal observed covered interval in parent order.

    A repeated traversal produces a separate parameter interval even when its
    coordinates coincide with an earlier traversal or another part.
    """
    pieces: list[Interval] = []
    for part_index, edge_index, edge in observed_edges(track):
        edge_pieces: list[Interval] = []
        left, right = edge.coords
        axis = max(range(2), key=lambda index: abs(right[index] - left[index]))

        def fraction(point: Any) -> float:
            # Dominant-axis division avoids length-squared underflow and
            # gives exact 0/1 for unchanged observation endpoints.
            return (point[axis] - left[axis]) / (right[axis] - left[axis])

        for line in _linear_components(_geos_overlay_or_fail(edge, area, "intersection")):
            a = fraction(line.coords[0])
            b = fraction(line.coords[-1])
            low, high = sorted((a, b))
            start = _position(part_index, edge_index, low)
            end = _position(part_index, edge_index, high)
            if start < end:
                edge_pieces.append(Interval(start, end))
        pieces.extend(sorted(edge_pieces, key=lambda item: item.start))

    merged: list[Interval] = []
    for piece in pieces:
        if merged and _gap_is_zero_and_covered(track, area, merged[-1].end, piece.start):
            merged[-1] = Interval(merged[-1].start, piece.end)
        else:
            merged.append(piece)
    # Repeated coordinates at either end remain observations in the maximal
    # interval. Only zero-length edges in the SAME part may extend an interval.
    extended: list[Interval] = []
    for interval in merged:
        start, end = interval.start, interval.end
        observations = track["parts"][start.part_index]["observations"]
        while start.fraction_to_next == 0 and start.observation_index > 0:
            previous = Position(start.part_index, start.observation_index - 1, 0)
            if not _gap_is_zero_and_covered(track, area, previous, start):
                break
            start = previous
        while end.fraction_to_next == 0 and end.observation_index + 1 < len(observations):
            following = Position(end.part_index, end.observation_index + 1, 0)
            if not _gap_is_zero_and_covered(track, area, end, following):
                break
            end = following
        extended.append(Interval(start, end))
    return extended


def position_from_dict(value: dict[str, Any]) -> Position:
    return Position(value["part_index"], value["observation_index"], value["fraction_to_next"])


def interpolate(track: dict[str, Any], value: Position) -> tuple[float, float]:
    observations = track["parts"][value.part_index]["observations"]
    left = observations[value.observation_index]["position"]
    if value.fraction_to_next == 0:
        return float(left[0]), float(left[1])
    right = observations[value.observation_index + 1]["position"]
    t = value.fraction_to_next
    return (float(left[0]) + t * (float(right[0]) - float(left[0])),
            float(left[1]) + t * (float(right[1]) - float(left[1])))


def positions_match(track: dict[str, Any], actual: Position, expected: Position, *, interval_length: float) -> bool:
    if (actual.part_index, actual.observation_index) != (expected.part_index, expected.observation_index):
        return False
    observations = track["parts"][expected.part_index]["observations"]
    if expected.observation_index + 1 < len(observations):
        edge_length = coordinate_length((
            observations[expected.observation_index]["position"],
            observations[expected.observation_index + 1]["position"],
        ))
    else:
        edge_length = 1.0
    if edge_length == 0:
        return actual.fraction_to_next == expected.fraction_to_next
    # Subtracting large coordinates on a short edge can amplify fraction
    # error (e.g. 112.9 - 112.895). Propagate the same coordinate error budget.
    local_length = min(edge_length, interval_length)
    fraction_scale = max(abs(actual.fraction_to_next), abs(expected.fraction_to_next))
    fraction_error = max(8 * math.ulp(fraction_scale),
                         POLICY.coordinate_error(scale=track_scale(track), local_length=local_length) / edge_length)
    if abs(actual.fraction_to_next - expected.fraction_to_next) > fraction_error:
        return False
    return POLICY.coordinates_close(
        interpolate(track, actual), interpolate(track, expected),
        local_length=local_length, operand_scale=track_scale(track),
    )
