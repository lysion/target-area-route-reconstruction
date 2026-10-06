# ADR-0006 — Minimum spatial CanonicalTrack contract

**Status:** Accepted  
**Date:** 2026-10-06  
**Evidence:** EP-01; paired real FIT/GPX baseline; coordinate-only synthetic attack

## Context

The deterministic spatial core must be able to reconstruct target-area route geometry from sources that do not provide timestamps, altitude, distance, speed, or other telemetry.

The open question was whether time is part of the minimum CanonicalTrack contract or whether ordered spatial coordinates are sufficient.

A clean real GPX baseline containing 2,298 ordered points was converted into a coordinate-only representation by removing timestamps, altitude, distance, speed, and all other non-coordinate attributes while preserving source order.

The coordinate-only representation produced exactly the same line geometry as the original spatial sequence and therefore the same target-area classification and clipping results.

Controlled checks produced:

- identical full route geometry after removing all non-coordinate attributes;
- identical `inside`, `partial`, and `outside` assessments;
- identical clipped TargetSegment geometry;
- a two-point coordinate-only track with no timestamp still produced an unambiguous positive-length route and target clip;
- one coordinate alone cannot form route line geometry;
- two coincident coordinates produce zero-length geometry and are not sufficient for positive-length route reconstruction.

## Decision

The minimum **canonical observation** required by the v0.1 spatial core is:

- a usable spatial coordinate in the canonical spatial reference;
- deterministic order within its continuity part.

Timestamp, altitude, distance, device speed, heart rate, cadence, and other telemetry are optional capabilities. Their absence does not invalidate otherwise usable spatial reconstruction.

A source must preserve or establish observation order. An unordered set of coordinates is not a CanonicalTrack route.

For **positive-length route geometry**, a continuity part must contain enough usable ordered observations to produce valid non-zero-length line geometry. In practice this requires at least two non-coincident usable positions.

A CanonicalTrack derivation may preserve singleton or zero-length observations as evidence, but those observations alone do not provide positive-length route geometry and cannot by themselves support target traversal or TargetSegment extraction.

## Consequences

- timestamp-free GPX-like, GeoJSON LineString-like, or other ordered coordinate sources can participate in v0.1 spatial reconstruction;
- temporal metrics and speed/pace overlays are capability-gated rather than required for core spatial validity;
- parser/schema validation must distinguish observation validity from route-geometry usability;
- missing timestamps must not cause an otherwise usable spatial track to become invalid or `outside`;
- ordering is mandatory even when time is absent.

## Alternatives rejected

### Require timestamps for every canonical point

Rejected because target-area classification and clipping remain fully determined from ordered coordinates alone.

### Treat coordinates as an unordered point set

Rejected because route geometry depends on sequence. The same coordinates in a different order can represent a different path.

### Treat any single valid coordinate as sufficient route geometry

Rejected because v0.1 TargetSegment semantics are positive-length route semantics; a singleton observation does not define a traversed route segment.

## Follow-up

Milestone 1 must include fixtures for:

- ordered coordinate-only track with no timestamps;
- coordinate-only inside / partial / outside assessments;
- two-point positive-length track;
- singleton observation that is preserved as evidence but is not route-geometry usable;
- coincident observations that do not create positive-length route geometry.
