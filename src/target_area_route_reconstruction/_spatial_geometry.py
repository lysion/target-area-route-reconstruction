"""Per-original-edge planar CRS84 clipping, with auditable binary64 lineage."""

import math

from shapely.geometry import LineString, Point, box

from .models import TrackPosition
from .quality_models import ParentInterval
from .spatial_models import SpatialFailure


def linear_components(geometry):
    if geometry.is_empty:
        return
    if geometry.geom_type == "LineString":
        if any(a != b for a, b in zip(geometry.coords, list(geometry.coords)[1:])):
            yield geometry
    else:
        for child in getattr(geometry, "geoms", ()):
            yield from linear_components(child)


def _position(part, edge, fraction):
    return TrackPosition(part, edge + 1, 0.0) if fraction == 1 else TrackPosition(part, edge, fraction)


def _fraction(point, left, right, local_length):
    if tuple(point) == tuple(left):
        return 0.0
    if tuple(point) == tuple(right):
        return 1.0
    axis = max(range(2), key=lambda i: abs(right[i] - left[i]))
    fraction = (point[axis] - left[axis]) / (right[axis] - left[axis])
    if not math.isfinite(fraction) or not 0 < fraction < 1:
        raise SpatialFailure("SPATIAL_FRACTION_UNREPRESENTABLE")
    regenerated = tuple(left[i] + fraction * (right[i] - left[i]) for i in range(2))
    scale = max(abs(v) for xy in (left, right, point, regenerated) for v in xy)
    allowed = min(1e-12, 8 * math.ulp(scale), local_length / 4)
    if any(abs(x - y) > allowed for x, y in zip(point, regenerated)):
        raise SpatialFailure("SPATIAL_LINEAGE_NUMERICAL_FAILURE")
    return fraction


def clip_edge(part, edge, left, right, area):
    """Return positive inside/outside fragments on ONE admitted parent edge.

    No geometric length cutoff, cross-edge merge, union, repair or buffering.
    The two classifications must partition the full parent parameter interval.
    """
    line = LineString((left, right))
    inside, outside = [], []
    for target, clipped in ((inside, line.intersection(area)), (outside, line.difference(area))):
        for component in linear_components(clipped):
            a, b = component.coords[0], component.coords[-1]
            local_length = min(math.hypot(b[0] - a[0], b[1] - a[1]),
                               math.hypot(right[0] - left[0], right[1] - left[1]))
            low, high = sorted((_fraction(a, left, right, local_length), _fraction(b, left, right, local_length)))
            if not low < high:
                raise SpatialFailure("SPATIAL_FRAGMENT_COLLAPSED")
            target.append((low, high))
        target.sort()
    partition = sorted(inside + outside)
    cursor = 0.0
    for low, high in partition:
        if low != cursor:
            raise SpatialFailure("SPATIAL_PARTITION_NUMERICAL_FAILURE")
        cursor = high
    if cursor != 1.0:
        raise SpatialFailure("SPATIAL_PARTITION_NUMERICAL_FAILURE")
    def ranges(spans):
        return tuple(ParentInterval(_position(part, edge, a), _position(part, edge, b)) for a, b in spans)
    return ranges(inside), ranges(outside)


def point_covered(position, area):
    return bool(area.covers(Point(position)))


def bound_relation(bound, area):
    envelope = box(*bound.bbox)
    if area.disjoint(envelope):
        return "disjoint"
    if area.covers(envelope):
        return "covered"
    return "intersects"
