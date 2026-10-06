# ADR-0004 — Four-state spatial relation with evidence-aware uncertainty

**Status:** Accepted  
**Date:** 2026-10-06  
**Evidence:** EP-02, EP-07, controlled target-area attack matrix

## Context

Simple geometry predicates are insufficient for route reconstruction.

Controlled tests showed that:

- a zero-length boundary touch should not count as target traversal;
- a positive-length boundary overlap is meaningful target coverage;
- a continuity-gap chord can create a false positive intersection;
- the same chord can miss a real hidden traversal;
- a gap elsewhere in the activity should not invalidate an already proven partial relation;
- some gaps can be proven irrelevant to a TargetArea through reliable constraints.

The domain needs relation semantics based on spatial evidence, not library predicates alone.

## Decision

SpatialAssessment retains four core relation values:

- inside
- partial
- outside
- unknown

No touching or boundary fifth state is added.

Relation is based on reliable positive-length coverage plus evidence sufficiency.

### inside

Reliable usable track geometry is covered by TargetArea and no relevant unresolved uncertainty could place part of the track outside.

### partial

Reliable positive-length geometry exists both within and outside TargetArea.

### outside

No reliable positive-length target coverage exists, point contact alone does not count as traversal, and no relevant unresolved uncertainty could change the result.

### unknown

Available reliable evidence is insufficient to prove inside, partial, or outside and an unresolved spatial interval could materially change the relation.

TargetArea boundary participates in positive-length coverage, but zero-length point contact alone does not create a TargetSegment.

The chord across a continuity break is never assessment evidence.

A gap affects an assessment only when it is relevant to that TargetArea.

Reliable constraints may establish that a gap is irrelevant, but this ADR does not freeze the reachability algorithm or thresholds.

## Consequences

Geometry-library predicates such as intersects, touches, crosses, or within cannot be mapped directly to domain relations.

A relation can be determined while TargetSegment extraction is still incomplete. Therefore the domain requires a separate representation of unresolved assessment/segment completeness, although its schema is deferred.

## Alternatives rejected

### Any intersection means partial

Rejected because a point touch has zero traversal length and because inferred gap chords can create false intersections.

### Any gap means unknown

Rejected because unrelated gaps do not erase already established spatial facts.

### Low-confidence partial instead of unknown

Rejected for v0.1 because it would claim traversal without sufficient evidence.

## Follow-up

Milestone 1 fixtures must cover point touch, boundary overlap, hidden traversal, false chord traversal, and irrelevant gaps.
