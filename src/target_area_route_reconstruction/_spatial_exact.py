"""Exact binary64-input line/polygon reference partition for M2C admission.

All coordinates are converted to *exact* rationals represented by their
binary64 inputs. This evaluates polygon boundaries and interval topology
without GEOS overlays, floating-point determinants, or a positive-length
cutoff. M2C is allowed to fail closed when Float64 cannot express a distinct
positive fragment; it must never label that fragment as outside/complete.
"""
from __future__ import annotations

from fractions import Fraction


def _difference(a, b):
    return a[0] - b[0], a[1] - b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _on_segment(p, a, b):
    return (_cross(_difference(p, a), _difference(b, a)) == 0
            and all(min(a[i], b[i]) <= p[i] <= max(a[i], b[i]) for i in (0, 1)))


def _in_ring(p, ring):
    """Return 0 outside, 1 inside, 2 on boundary, using exact ray casting."""
    inside = False
    for a, b in zip(ring, ring[1:]):
        if _on_segment(p, a, b):
            return 2
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if p[0] < x:
                inside = not inside
    return int(inside)


def _covered(p, polygons):
    for rings in polygons:
        outer = _in_ring(p, rings[0])
        if outer == 2:
            return True
        if outer == 1:
            hole_results = [_in_ring(p, ring) for ring in rings[1:]]
            if 2 in hole_results or not any(hole_results):
                return True
    return False


def _rings(area):
    if area.geom_type == "Polygon":
        polygons = [area]
    elif area.geom_type == "MultiPolygon":
        polygons = list(area.geoms)
    else:
        raise ValueError("UNSUPPORTED_SPATIAL_GEOMETRY")
    result = []
    for polygon in polygons:
        rings = (polygon.exterior, *polygon.interiors)
        result.append([[tuple(Fraction(v) for v in vertex) for vertex in ring.coords]
                       for ring in rings])
    return result


def exact_point_covered(position, area):
    """Exact boundary-inclusive coverage for a stationary observation."""
    return _covered(tuple(Fraction(x) for x in position), _rings(area))


def exact_coverage(left, right, area):
    """Return maximal (inside, outside) positive parameter intervals.

    Boundary-only point touches add breakpoints but cannot cause a fictitious
    positive interval. Collinear overlap endpoints are included. Hole
    boundaries are covered; hole interiors are excluded.
    """
    a = tuple(Fraction(x) for x in left)
    b = tuple(Fraction(x) for x in right)
    delta = _difference(b, a)
    if a == b:
        raise ValueError("EXACT_EDGE_MUST_BE_POSITIVE")
    polygons = _rings(area)
    critical = {Fraction(0), Fraction(1)}
    for rings in polygons:
        for ring in rings:
            for c, d in zip(ring, ring[1:]):
                side = _difference(d, c)
                det = _cross(delta, side)
                if det:
                    t = _cross(_difference(c, a), side) / det
                    u = _cross(_difference(c, a), delta) / det
                    if 0 <= t <= 1 and 0 <= u <= 1:
                        critical.add(t)
                elif _cross(_difference(c, a), delta) == 0:
                    axis = 0 if delta[0] else 1
                    for v in (c, d):
                        t = (v[axis] - a[axis]) / delta[axis]
                        if 0 <= t <= 1:
                            critical.add(t)
    inside, outside = [], []
    for low, high in zip(sorted(critical), sorted(critical)[1:]):
        mid = (low + high) / 2
        pos = (a[0] + mid * delta[0], a[1] + mid * delta[1])
        covered = _covered(pos, polygons)
        selected = inside if covered else outside
        if selected and selected[-1][1] == low:
            selected[-1] = (selected[-1][0], high)
        else:
            selected.append((low, high))
    return tuple(inside), tuple(outside)
