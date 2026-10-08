"""M2F derived per-observed-edge temporal profile, downstream of verified M2E.

Spatial authority belongs to M2A–M2D. This module may split an already
observed TargetSegment into its original parent edges for metric display,
but may never connect observations, infer gap geometry, or reclassify targets.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from fractions import Fraction

from ._m2d_common import canonical_json
from ._quality_numerics import distance_metres, utc_seconds
from .geojson_export import GeoJSONExportResult, GeoJSONIssue, export_geojson
from .models import TrackPosition


ALGORITHM = {"name": "target-area-route-reconstruction.temporal-overlay", "version": "0.1.1"}
METRIC_MODES = frozenset({"speed_mps", "pace_s_per_km"})


def _positions(segment):
    """Mirror the parent TrackPosition vertices of the accepted M2D geometry.

    All interior observation vertices, including repeated zero-distance
    observations, must retain their order. This is *not* geometric clipping.
    """
    a = TrackPosition(**segment["start_position"])
    b = TrackPosition(**segment["end_position"])
    positions = [a]
    positions.extend(TrackPosition(a.part_index, index) for index in
                     range(a.observation_index + 1, b.observation_index + 1))
    if b.fraction_to_next:
        positions.append(b)
    if len(positions) != len(segment["geometry"]["coordinates"]):
        raise ValueError("M2F_VERTEX_LINEAGE_MISMATCH")
    return positions


def _parent_edge(left, right):
    """Map a clipped fragment exclusively to one known original parent edge.

    An integer vertex belongs to the edge starting there; an endpoint with
    fractional position belongs to that same index's edge. Never choose an
    edge across a continuity boundary or over skipped observations.
    """
    if left.part_index != right.part_index:
        raise ValueError("M2F_CROSS_PART_INTERVAL")
    p, i, f = left.part_index, left.observation_index, left.fraction_to_next
    if right.observation_index == i:
        if not (f < right.fraction_to_next <= 1):
            raise ValueError("M2F_EDGE_ORDER_INVALID")
        return p, i, Fraction(f), Fraction(right.fraction_to_next)
    if right.observation_index == i + 1 and right.fraction_to_next == 0:
        return p, i, Fraction(f), Fraction(1)
    raise ValueError("M2F_NONADJACENT_PARENT_VERTICES")


def _metrics(left, right, obs0, obs1, first_fraction, second_fraction):
    """Derived WGS84 distance and elapsed UTC, never device-observed speed.

    A valid duration requires BOTH ORIGINAL parent-edge timestamps, strictly
    increasing. This forbids using clipped endpoint times to paper over a bad
    original edge. Fractional M2C boundaries inherit time only from that
    one accepted original observation edge.
    """
    # Exact UTC applies only to the ORIGINAL edge endpoints. Clipped vertices
    # have no observed arrival times: duration at those vertices is an explicit
    # proportional allocation, never a new source timestamp.
    duration_basis = ("observed_parent_endpoints"
                      if first_fraction == 0 and second_fraction == 1
                      else "proportional_parent_edge_allocation")
    empty = {"status": None, "duration_s": None, "distance_m": None,
             "speed_mps": None, "pace_s_per_km": None,
             "duration_basis": duration_basis}
    if "timestamp" not in obs0 or "timestamp" not in obs1:
        return {**empty, "status": "missing_timestamp"}
    a, b = utc_seconds(obs0["timestamp"]), utc_seconds(obs1["timestamp"])
    if a is None or b is None:
        return {**empty, "status": "unsupported_timestamp"}
    if b <= a:
        return {**empty, "status": "nonincreasing_timestamp"}
    dt = (b - a) * (second_fraction - first_fraction)
    if dt <= 0:
        return {**empty, "status": "nonincreasing_subinterval"}

    # M2C clipping is explicitly planar CRS84; interpreting a +/-180
    # longitude discontinuity as a new geodesic/periodic path would silently
    # introduce semantics not established by the proof.
    if abs(obs1["position"][0] - obs0["position"][0]) > 180:
        return {**empty, "status": "planar_dateline_ambiguous"}

    try:
        distance = distance_metres(left, right)
        duration = float(dt)
        speed = distance / duration
        pace = 1000.0 * duration / distance if distance > 0 else None
        if not all(math.isfinite(x) for x in (distance, duration, speed)):
            raise ValueError("nonfinite metric")
        if pace is not None and not math.isfinite(pace):
            raise ValueError("nonfinite pace")
        return {"status": "valid", "duration_s": duration,
                "distance_m": distance, "speed_mps": speed,
                "pace_s_per_km": pace, "duration_basis": duration_basis}
    except (ValueError, OverflowError, ZeroDivisionError):
        return {**empty, "status": "metric_unavailable"}


def _edges(collection, bundle, evidence, quality_projection, quality_policy):
    """Add only parent-edge subsets of independently verified M2D segments."""
    observations_by_part = [p["observations"] for p in evidence.canonical_track["parts"]]
    appended, stationary = [], []
    counts = {"valid": 0, "unavailable": 0, "stationary": 0}
    screening_counts = {"passed": 0, "indeterminate": 0,
                        "unavailable": 0, "not_screened": 0}
    # M2B's verified exact diagnostic list assigns one independent decision
    # to each ORIGINAL parent edge. A configured policy does not mean its
    # numerical test actually passed (see SPEED_NUMERICALLY_INDETERMINATE).
    diagnostic_by_edge = {
        (d.interval.start.part_index, d.interval.start.observation_index): d.code
        for d in quality_projection.diagnostics
    }
    def parent_screening(p, i):
        reason = diagnostic_by_edge.get((p, i))
        if quality_policy.max_implied_speed_mps is None:
            if reason != "SPEED_RULE_DISABLED":
                raise ValueError("M2F_UNVERIFIED_SCREENING_STATE")
            return "not_screened", reason
        if reason is None:
            # Only a *verified* M2B claim may imply explicit parent-edge pass.
            return "passed", "ADMITTED"
        if reason == "SPEED_NUMERICALLY_INDETERMINATE":
            return "indeterminate", reason
        if reason in {"SPEED_TIME_MISSING", "SPEED_TIME_UNSUPPORTED",
                      "SPEED_TIME_NONINCREASING", "SPEED_DISTANCE_UNAVAILABLE"}:
            return "unavailable", reason
        # A quality-excluded edge or unknown decision cannot be a segment.
        raise ValueError("M2F_UNVERIFIED_SCREENING_STATE")
    # M2B's optional caller-owned speed rule is the *only* speed-plausibility
    # screening signal. A successful UTC calculation is not GPS validation.
    speed_screen = ("explicit_m2b_policy_enabled"
                    if quality_policy.max_implied_speed_mps is not None
                    else "not_screened")
    for segment in bundle.segments if bundle is not None else ():
        coordinates = segment["geometry"]["coordinates"]
        positions = _positions(segment)
        segment_ref = {"id": segment["id"], "revision_id": segment["revision_id"]}
        for index, (start, end) in enumerate(zip(positions, positions[1:])):
            p, i, f0, f1 = _parent_edge(start, end)
            a, b = coordinates[index], coordinates[index + 1]
            metric = _metrics(a, b, observations_by_part[p][i],
                              observations_by_part[p][i + 1], f0, f1)
            screen_result, screen_reason = parent_screening(p, i)
            parent_edge = {"part_index": p, "observation_index": i}
            provenance = {
                "target_segment": segment_ref,
                "target_segment_ordinal": segment["ordinal"],
                "fragment_ordinal": index,
                "parent_edge": parent_edge,
                "start_position": asdict(start),
                "end_position": asdict(end),
            }
            if a == b:
                # A stationary observation edge has elapsed time but no
                # positive-length LineString geometry. Never manufacture a
                # displayable route for it or silently average its pause into
                # adjacent moving edges.
                counts["stationary"] += 1
                stationary.append({**provenance, "metric": metric,
                                   "speed_screen": speed_screen,
                                   "speed_screen_result": screen_result,
                                   "speed_screen_reason": screen_reason,
                                   "reason": "no_positive_length_geometry"})
                continue
            counts["valid" if metric["status"] == "valid" else "unavailable"] += 1
            screening_counts[screen_result] += 1
            appended.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [list(a), list(b)]},
                "properties": {
                    "layer": "target_metric_edge",
                    "evidence_class": "derived_from_quality_admitted_observed_edge",
                    "metric_algorithm": ALGORITHM,
                    "metric": metric,
                    "speed_screen": speed_screen,
                    "speed_screen_result": screen_result,
                    "speed_screen_reason": screen_reason,
                    **provenance,
                },
            })
    collection["features"].extend(appended)
    collection["metadata"]["temporal_overlay"] = {
        "algorithm": ALGORITHM,
        "method": "WGS84 clipped-endpoint geodesic / strictly increasing original-edge UTC",
        "clipped_duration_semantics": "proportional_parent_edge_allocation_not_observed_arrival_time",
        "parent_speed_cap_scope": "full_original_parent_edge_not_clipped_fragment",
        "quality": "admitted_by_explicit_M2B_policy_not_GPS_truth",
        "speed_screen": speed_screen,
        "speed_cap_mps": quality_policy.max_implied_speed_mps,
        "valid_status_means": "monotone_original_UTC_and_finite_arithmetic_only_not_motion_truth",
        "counts": counts,
        "screening_counts": screening_counts,
        "stationary_observations": stationary,
        "missing_metric_semantics": "neutral_display_no_interpolation",
    }
    return collection


def export_temporal_geojson(*, bundle, proof, evidence, quality_projection,
                            quality_policy, target_area, target_reference,
                            metric_mode="speed_mps", include_outside=True):
    """Produce verified M2E GeoJSON plus optional observed-edge metric overlays.

    Failure produces no GeoJSON. Spatial display is preserved even where time
    is invalid; each affected *known* fragment is explicitly neutral rather
    than being bridged or assigned an invented speed.
    """
    if type(metric_mode) is not str or metric_mode not in METRIC_MODES:
        return GeoJSONExportResult("invalid_input", issues=(
            GeoJSONIssue("M2F_METRIC_MODE_INVALID", "metric_mode"),))
    base = export_geojson(
        bundle=bundle, proof=proof, evidence=evidence,
        quality_projection=quality_projection, quality_policy=quality_policy,
        target_area=target_area, target_reference=target_reference,
        include_outside=include_outside,
    )
    if base.outcome != "produced":
        return base
    try:
        collection = json.loads(base.geojson_json)
        _edges(collection, bundle, evidence, quality_projection, quality_policy)
        collection["metadata"]["temporal_overlay"]["mode"] = metric_mode
        return GeoJSONExportResult("produced", canonical_json(collection))
    except Exception:
        return GeoJSONExportResult("export_failure", issues=(
            GeoJSONIssue("M2F_METRIC_PROJECTION_FAILURE"),))
