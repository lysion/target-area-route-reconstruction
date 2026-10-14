"""Shared strict UTF-8 JSON admission for fixtures and runtime snapshots.

Legacy M2D parse codes are retained for caller compatibility. No schema or
spatial correctness claim follows from lexical admission alone.
"""
from __future__ import annotations

import json
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path


class StrictJSONError(ValueError):
    """Stable rejection category across fixture and runtime admission."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def loads_json(text):
    """Decode unambiguous UTF-8 JSON, without last-member-wins authority."""
    if type(text) is bytes:
        try:
            text = text.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise StrictJSONError("M2D_BUNDLE_MALFORMED") from exc
    if type(text) is not str:
        raise StrictJSONError("M2D_BUNDLE_MALFORMED")
    def illegal_constant(value):
        raise StrictJSONError("M2D_NONFINITE_JSON")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise StrictJSONError("M2D_DUPLICATE_JSON_MEMBER")
            result[key] = value
        return result
    def binary64(number):
        value = float(number)
        if not math.isfinite(value):
            raise StrictJSONError("M2D_NONFINITE_JSON")
        if value == 0 and Decimal(number) != 0:
            raise StrictJSONError("M2D_JSON_NUMBER_UNREPRESENTABLE")
        return value
    try:
        value = json.loads(text, parse_constant=illegal_constant,
                           object_pairs_hook=unique_object, parse_float=binary64)
    except StrictJSONError:
        raise
    except (ValueError, OverflowError, RecursionError, InvalidOperation) as exc:
        raise StrictJSONError("M2D_BUNDLE_MALFORMED") from exc
    def walk(item):
        if isinstance(item, float) and not math.isfinite(item):
            raise StrictJSONError("M2D_NONFINITE_JSON")
        if isinstance(item, str):
            item.encode("utf-8", errors="strict")
        if isinstance(item, dict):
            for k, v in item.items():
                walk(k)
                walk(v)
        elif isinstance(item, list):
            for v in item:
                walk(v)
    try:
        walk(value)
    except (UnicodeError, RecursionError) as exc:
        raise StrictJSONError("M2D_BUNDLE_MALFORMED") from exc
    return value


def load_json(path: str | Path):
    """Load local UTF-8 JSON; filesystem errors remain ordinary OSError."""
    return loads_json(Path(path).read_bytes())
