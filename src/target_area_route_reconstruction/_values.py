"""Finite values and UTC serialization supported by the frozen observations."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .models import Diagnostic, SourceFailure, SourceLocation


def finite_number(value: Any, source: SourceLocation, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SourceFailure("INVALID_NUMERIC_VALUE", source, field) from exc
    if not math.isfinite(number):
        raise SourceFailure("NONFINITE_NUMERIC_VALUE", source, field)
    if number == 0 and isinstance(value, (str, Decimal)) and Decimal(value) != 0:
        raise SourceFailure("NUMERIC_PRECISION_UNREPRESENTABLE", source, field)
    return number


def utc_timestamp(value: datetime, source: SourceLocation, *, fractional_second: str | None = None) -> tuple[str | None, tuple[Diagnostic, ...]]:
    if value.tzinfo is None or value.utcoffset() is None:
        return None, (Diagnostic("TIMESTAMP_TIMEZONE_MISSING", source, "timestamp"),)
    try:
        utc = value.astimezone(timezone.utc)
        if fractional_second is not None:
            text = utc.replace(microsecond=0).isoformat(timespec="seconds").replace("+00:00", "Z")
            return text[:-1] + "." + fractional_second + "Z", ()
        return utc.isoformat().replace("+00:00", "Z"), ()
    except (OverflowError, ValueError):
        return None, (Diagnostic("TIMESTAMP_UNREPRESENTABLE", source, "timestamp"),)
