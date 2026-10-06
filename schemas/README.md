# Schemas

Milestone 1 encodes the frozen v0.1 domain contract into machine-verifiable JSON Schemas and reproducible fixtures.

## Dialect

All schemas use JSON Schema Draft 2020-12.

Shared representation rules are defined in:

- `../docs/schema-conventions.md`

Shared reusable definitions are in:

- `common.schema.json`

## Planned core entity schemas

- `activity.schema.json`
- `track-source.schema.json`
- `canonical-track.schema.json`
- `target-area.schema.json`
- `spatial-assessment.schema.json`
- `target-segment.schema.json`

## Validation layers

A valid JSON Schema instance is not automatically a semantically valid route-reconstruction object.

Milestone 1/2 distinguishes:

1. JSON Schema validation — types, required fields, enums, numeric bounds, closed-object rules;
2. semantic validation — geometry topology, cross-object references, lineage bounds, relation/completeness invariants;
3. fixture expectation validation — expected classification, clipping, segment order, and known failure reason.

## Development rules

- Core schemas are closed by default.
- Optional means omitted, not null, unless null has explicit semantics.
- Core geometry uses OGC:CRS84 with `[longitude, latitude]` ordering.
- Cross-schema references use repository-relative `$ref` paths.
- Do not add COROS-, FIT-, GPX-, or GIS-library-specific fields to portable core schemas.
- Do not change frozen domain semantics to make schema composition easier.
- A domain-semantic conflict requires a new/superseding ADR.

## Current status

Shared schema conventions and `common.schema.json` are complete.

Next schema order:

1. CanonicalTrack
2. TargetArea
3. SpatialAssessment
4. TargetSegment
5. TrackSource
6. Activity
