# ADR-0005 — TargetSegment multiplicity, maximality, ordering, and lineage

**Status:** Accepted  
**Date:** 2026-10-06  
**Evidence:** EP-05; real-track clipping; repeated-entry, MultiPolygon, and hole attacks

## Context

TargetArea clipping commonly creates entry and exit points between recorded GPS observations.

One track may also enter the same target multiple times, cross multiple MultiPolygon components, or be split by polygon holes.

A geometry-only clipped result is insufficient for auditability because later processing must be able to identify exactly which parent-track interval produced each target segment.

## Decision

One SpatialAssessment owns zero, one, or many TargetSegments.

A TargetSegment is one **maximal continuous positive-length portion** of a parent CanonicalTrack that is covered by the assessed TargetArea.

Multiple disjoint covered portions are separate TargetSegments even when a geometry library returns them as one MultiLineString result.

TargetSegments are ordered by their position on the parent CanonicalTrack.

Each TargetSegment must retain parent-track lineage through reproducible start and end **TrackPosition** values.

TrackPosition must be able to express a location between adjacent canonical observations, including an interpolation fraction.

A representative form is:

~~~text
part_index
point_index
fraction_to_next
~~~

The exact field names, index base, numeric precision, and serialization are deferred to schema design.

## Consequences

- repeated target entry produces multiple ordered TargetSegments;
- MultiPolygon components do not create separate SpatialAssessment objects;
- polygon holes naturally split target coverage into separate TargetSegments;
- a single continuous fully covered track part produces a full-length TargetSegment;
- continuity breaks always separate TargetSegments because no geometry exists across them;
- TargetSegment geometry can be regenerated and audited from its parent lineage.

## Alternatives rejected

### Geometry only

Rejected because clipped coordinates alone cannot prove their parent-track origin after algorithms or TargetArea versions change.

### Start/end point indices only

Rejected because real boundary intersections frequently occur between recorded observations.

### One MultiLineString equals one TargetSegment

Rejected because this loses entry count, order, per-segment lineage, and independent derived metrics.

## Follow-up

Milestone 1 schemas must encode TrackPosition semantics without coupling them to a specific GIS library.
