"""Versioned basic-local admission ceilings for expensive per-source work."""

DEFAULT_SOURCE_BYTES = 64 * 1024 * 1024
MAX_SOURCE_BYTES = 256 * 1024 * 1024
DEFAULT_POSITIONED_OBSERVATIONS = 200_000
MAX_POSITIONED_OBSERVATIONS = 1_000_000
DEFAULT_CONTINUITY_PARTS = 10_000
MAX_CONTINUITY_PARTS = 100_000
DEFAULT_TARGET_VERTICES = 20_000
MAX_TARGET_VERTICES = 100_000
DEFAULT_OUTPUT_VERTICES = 250_000
MAX_OUTPUT_VERTICES = 1_000_000


def validate_limit(value, maximum, code):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(code)
    return value
