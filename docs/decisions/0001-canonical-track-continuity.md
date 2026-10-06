# ADR-0001 — CanonicalTrack continuity parts and no inferred geometry across gaps

**Status:** Accepted  
**Date:** 2026-10-06  
**Evidence:** EP-02; representative real FIT/GPX cases; controlled synthetic attack

## Context

Real activities can remain one Activity while usable position observations disappear and later resume.

Observed cases showed that:

- position gaps may occur with or without timer pauses;
- timestamps, distance, speed, and heart-rate telemetry may continue while position is unavailable;
- GPX exports may represent the same Activity as many track segments;
- normal continuous activities can remain a single continuous segment;
- connecting gap endpoints can invent a path that was never observed.

The domain must therefore represent missing spatial continuity without changing Activity identity or manufacturing geometry.

## Decision

CanonicalTrack supports one or more ordered **continuity parts**.

A continuity break means that the model has no continuous spatial observation across that interval.

No geometry is inferred between the final observation of one part and the first observation of the next.

A continuity break by itself:

- does not create a new Activity;
- does not automatically create a new CanonicalTrack;
- does not mean timer pause;
- does not assert a specific physical cause.

The chord between break endpoints is not evidence geometry.

## Consequences

The deterministic core must not:

- include cross-gap chords in track length;
- intersect cross-gap chords with TargetArea;
- create TargetSegments across gaps;
- create route-network connectivity across gaps.

Continuity detection and quality thresholds remain implementation concerns and are not frozen by this ADR.

## Alternatives rejected

### One unconditional point series

Rejected because it produces false spatial continuity and can create false target-area intersections.

### One CanonicalTrack per observed section

Rejected because it confuses track identity with spatial observation continuity.

## Follow-up

Milestone 1 fixtures must include at least:

- a continuous baseline;
- a non-pause position gap;
- a pause-associated gap;
- a gap whose endpoint chord crosses a TargetArea.
