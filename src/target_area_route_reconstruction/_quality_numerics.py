"""Physical-distance primitive and exact UTC durations, not route interpolation."""

import math
import re
from datetime import datetime
from fractions import Fraction

from geographiclib.geodesic import Geodesic


def utc_seconds(value: str) -> Fraction | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?Z", value)
    if match is None:
        return None
    try:
        whole = datetime.fromisoformat(match[1])
        fraction = Fraction(match[2] or "0")
    except ValueError:  # including leap seconds: no fabricated elapsed time
        return None
    return Fraction(whole.toordinal() * 86400 + whole.hour * 3600
                    + whole.minute * 60 + whole.second) + fraction


def distance_metres(left, right) -> float:
    """WGS84 shortest inverse geodesic; wrapping at the antimeridian is explicit."""
    result = Geodesic.WGS84.Inverse(left[1], left[0], right[1], right[0])["s12"]
    if not math.isfinite(result) or result < 0:
        raise ValueError("DISTANCE_UNAVAILABLE")
    return result
