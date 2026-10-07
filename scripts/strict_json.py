"""Fail closed on non-JSON and non-finite numbers in contract fixtures."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"JSON number is outside finite binary64 range: {value[:80]}")
    return result


def _non_json_constant(value: str) -> None:
    raise ValueError(f"non-JSON numeric constant: {value}")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(
            handle,
            parse_constant=_non_json_constant,
            parse_float=_finite_float,
        )
