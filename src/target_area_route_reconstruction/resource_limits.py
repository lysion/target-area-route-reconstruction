"""Versioned basic-local admission ceilings for expensive per-source work."""

from dataclasses import asdict, dataclass

DEFAULT_SOURCE_BYTES = 64 * 1024 * 1024
MAX_SOURCE_BYTES = 256 * 1024 * 1024
DEFAULT_POSITIONED_OBSERVATIONS = 200_000
MAX_POSITIONED_OBSERVATIONS = 1_000_000
DEFAULT_CONTINUITY_PARTS = 10_000
MAX_CONTINUITY_PARTS = 100_000
DEFAULT_QUALITY_FRAGMENTATION = 10_000
MAX_QUALITY_FRAGMENTATION = 100_000
DEFAULT_TARGET_VERTICES = 20_000
MAX_TARGET_VERTICES = 100_000
DEFAULT_OUTPUT_VERTICES = 250_000
MAX_OUTPUT_VERTICES = 1_000_000


@dataclass(frozen=True)
class TaskResourceProfile:
    """Task-bound admission profile; values are part of graph identity."""

    max_source_bytes: int = DEFAULT_SOURCE_BYTES
    max_observations: int = DEFAULT_POSITIONED_OBSERVATIONS
    max_parts: int = DEFAULT_CONTINUITY_PARTS
    max_quality_fragments: int = DEFAULT_QUALITY_FRAGMENTATION
    max_target_vertices: int = DEFAULT_TARGET_VERTICES
    max_output_vertices: int = DEFAULT_OUTPUT_VERTICES


DEFAULT_TASK_RESOURCE_PROFILE = TaskResourceProfile()


def normalize_task_resource_profile(profile):
    if type(profile) is not TaskResourceProfile:
        raise ValueError("INVALID_TASK_RESOURCE_PROFILE")
    limits = asdict(profile)
    for field, maximum, code in (
        ("max_source_bytes", MAX_SOURCE_BYTES, "INVALID_SOURCE_BYTES_LIMIT"),
        ("max_observations", MAX_POSITIONED_OBSERVATIONS, "INVALID_OBSERVATION_LIMIT"),
        ("max_parts", MAX_CONTINUITY_PARTS, "INVALID_PART_LIMIT"),
        ("max_quality_fragments", MAX_QUALITY_FRAGMENTATION, "INVALID_QUALITY_FRAGMENT_LIMIT"),
        ("max_target_vertices", MAX_TARGET_VERTICES, "INVALID_TARGET_VERTEX_LIMIT"),
        ("max_output_vertices", MAX_OUTPUT_VERTICES, "INVALID_OUTPUT_VERTEX_LIMIT"),
    ):
        validate_limit(limits[field], maximum, code)
    return limits


def validate_limit(value, maximum, code):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(code)
    return value
