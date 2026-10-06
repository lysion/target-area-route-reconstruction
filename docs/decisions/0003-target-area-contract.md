# ADR-0003 — Versioned Polygon/MultiPolygon TargetArea contract

**Status:** Accepted  
**Date:** 2026-10-06  
**Evidence:** EP-06; controlled Polygon, MultiPolygon, hole, invalid-geometry attacks

## Context

A target geographic area may be contiguous, disjoint, or contain excluded interior holes.

The core needs a deterministic geometry contract without becoming a generic arbitrary-geometry engine.

Target definitions also change over time. Reassessment must not mutate track evidence or erase historical results.

## Decision

v0.1 TargetArea supports:

- valid Polygon;
- valid MultiPolygon;
- standard polygon holes.

The core rejects:

- Point;
- LineString;
- GeometryCollection;
- empty geometry;
- invalid/self-intersecting polygon geometry.

The core fails closed rather than silently repairing invalid target geometry.

TargetArea has version semantics. A revised boundary produces a new target version for assessment while source and canonical track evidence remain unchanged.

## Consequences

- One logical TargetArea may have multiple disconnected polygon components.
- Holes are handled by standard polygon topology and do not need a separate domain entity.
- SpatialAssessment identity includes a specific TargetArea version.
- Historical assessments remain auditable after boundary changes.

## Alternatives rejected

### Accept arbitrary GeometryCollection

Rejected because it creates ambiguous target-membership semantics not required by v0.1.

### Silently repair invalid polygons

Rejected because it changes user-supplied target evidence without an explicit transformation record.

## Follow-up

Any future input-repair feature must be an explicit preprocessing step with provenance.
