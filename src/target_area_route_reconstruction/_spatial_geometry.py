"""Per-original-edge planar CRS84 clipping, with auditable binary64 lineage."""

import math
import sys
import warnings

from shapely.geometry import LineString, box

from ._spatial_exact import exact_coverage, exact_point_covered
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


# GEOS intersection operates on floating-point expressions whose products
# can underflow even when both source coordinates and the target are valid
# binary64 CRS84 values. Never use a squared-length epsilon to delete positive
# observations. Instead, conservatively refuse to classify a tiny edge whose
# bounding box meets ANY actual polygon-ring boundary segment. Simple exact
# coordinate ordering (no GEOS predicates or length arithmetic) is used for
# this *preflight*, so the check does not share GEOS's underflow failure.
# Edges wholly separated from every ring boundary (e.g. a 1e-200 degree edge
# well inside a 2-degree box) remain eligible and retain positive length.
_GEOMETRY_SQUARE_UNDERFLOW_GUARD = 16 * math.sqrt(sys.float_info.min)


def _boundary_segments(geometry):
    # Read each target's original linear ring vertices without asking GEOS to
    # construct a new boundary geometry, overlay or length. Polygon holes and
    # separate MultiPolygon components must all participate in the proof that
    # no boundary segment envelope can meet the parent edge envelope.
    if geometry.geom_type == "Polygon":
        for ring in (geometry.exterior, *geometry.interiors):
            vertices = list(ring.coords)
            yield from zip(vertices, vertices[1:])
    elif geometry.geom_type == "MultiPolygon":
        for polygon in geometry.geoms:
            yield from _boundary_segments(polygon)
    else:
        raise SpatialFailure("SPATIAL_NUMERICAL_BOUNDARY_UNSUPPORTED")


def _preflight_tiny_boundary_contact(left, right, area):
    dx, dy = right[0] - left[0], right[1] - left[1]
    if max(abs(dx), abs(dy)) >= _GEOMETRY_SQUARE_UNDERFLOW_GUARD:
        return None
    # Positive-length remains a coordinate inequality, not an epsilon test.
    if tuple(left) == tuple(right):
        return None
    x0, x1 = sorted((left[0], right[0]))
    y0, y1 = sorted((left[1], right[1]))
    for a, b in _boundary_segments(area):
        if (max(min(a[0], b[0]), x0) <= min(max(a[0], b[0]), x1)
                and max(min(a[1], b[1]), y0) <= min(max(a[1], b[1]), y1)):
            raise SpatialFailure("SPATIAL_NUMERICAL_BOUNDARY_UNRESOLVED")
    # No ring SEGMENT can intersect the exact axis-aligned parent envelope:
    # this edge cannot change its inside/outside predicate anywhere. GEOS
    # overlay itself may silently erase a subnormal positive line even without
    # a RuntimeWarning, so DO NOT call line.intersection/difference here.
    # Evaluate stationary point coverage; both endpoints must agree.
    start_covered = exact_point_covered(left, area)
    end_covered = exact_point_covered(right, area)
    if start_covered != end_covered:
        raise SpatialFailure("SPATIAL_NUMERICAL_POINT_PREDICATE_MISMATCH")
    return start_covered


def clip_edge(part, edge, left, right, area):
    """Return positive inside/outside fragments on ONE admitted parent edge.

    No geometric length cutoff, cross-edge merge, union, repair or buffering.
    The two classifications must partition the full parent parameter interval.
    """
    proven_stationary_class = _preflight_tiny_boundary_contact(left, right, area)
    if proven_stationary_class is not None:
        # Check the endpoint predicate with independent exact topology too.
        exact_inside, exact_outside = exact_coverage(left, right, area)
        complete_inside = exact_inside == ((0, 1),) and not exact_outside
        complete_outside = exact_outside == ((0, 1),) and not exact_inside
        if not (complete_inside if proven_stationary_class else complete_outside):
            raise SpatialFailure("SPATIAL_EXACT_PARTITION_MISMATCH")
        # Full ORIGINAL positive edge retains its original parent lineage.
        whole = (ParentInterval(TrackPosition(part, edge),
                                TrackPosition(part, edge + 1)),)
        return (whole, ()) if proven_stationary_class else ((), whole)
    line = LineString((left, right))
    inside, outside = [], []
    # Shapely can emit NumPy RuntimeWarning instead of raising GEOSException
    # for division-by-zero/invalid topology math. Such a classification is
    # NEVER usable evidence, even if it yields an apparently valid partition.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            clipped_inside = line.intersection(area)
            clipped_outside = line.difference(area)
    except RuntimeWarning as exc:
        raise SpatialFailure("SPATIAL_NUMERICAL_ENGINE_WARNING") from exc
    for target, clipped in ((inside, clipped_inside), (outside, clipped_outside)):
        for component in linear_components(clipped):
            a, b = component.coords[0], component.coords[-1]
            local_length = min(math.hypot(b[0] - a[0], b[1] - a[1]),
                               math.hypot(right[0] - left[0], right[1] - left[1]))
            low, high = sorted((_fraction(a, left, right, local_length), _fraction(b, left, right, local_length)))
            if not low < high:
                raise SpatialFailure("SPATIAL_FRAGMENT_COLLAPSED")
            target.append((low, high))
        target.sort()
    # Independently derive the topology of every positive original edge
    # using exact rationals, irrespective of *parent edge length*. The old
    # tiny-edge preflight missed ordinary edges crossing subnormal-width
    # target rings; GEOS can silently erase those with NO RuntimeWarning.
    # A lossy binary64 conversion must not erase a mathematically positive
    # interval. Nor may shared-GEOS producer/verifier agreement confer proof.
    expected_inside, expected_outside = exact_coverage(left, right, area)
    for intervals in (expected_inside, expected_outside):
        for low, high in intervals:
            if not float(low) < float(high):
                raise SpatialFailure("SPATIAL_FRACTION_UNREPRESENTABLE")

    # Enforce matching topology and near-binary64 boundary position. GEOS is
    # used as an optimized producer only when exact geometry confirms its
    # complete positive-length partition. 8 ulps is the *declared* spatial
    # comparison budget, never a positive-length deletion threshold.
    for claimed, expected in ((inside, expected_inside), (outside, expected_outside)):
        if len(claimed) != len(expected):
            raise SpatialFailure("SPATIAL_EXACT_PARTITION_MISMATCH")
        for (actual_low, actual_high), (exact_low, exact_high) in zip(claimed, expected):
            for actual, rational in ((actual_low, exact_low), (actual_high, exact_high)):
                reference = float(rational)
                if not math.isfinite(reference):
                    raise SpatialFailure("SPATIAL_FRACTION_UNREPRESENTABLE")
                if abs(actual - reference) > 8 * max(math.ulp(actual), math.ulp(reference)):
                    raise SpatialFailure("SPATIAL_EXACT_BOUNDARY_MISMATCH")

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
    return exact_point_covered(position, area)


def bound_relation(bound, area):
    envelope = box(*bound.bbox)
    if area.disjoint(envelope):
        return "disjoint"
    if area.covers(envelope):
        return "covered"
    return "intersects"
