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

Implemented core schemas:

- `canonical-track.schema.json`
- `target-area.schema.json`
- `spatial-assessment.schema.json`
- `target-segment.schema.json`

Initial fixtures and expected validation layers are recorded in `../tests/fixtures/manifest.json`.

### CanonicalTrack representation

The schema freezes:

- exact TrackSource revision provenance;
- canonical OGC:CRS84 spatial reference;
- one or more ordered ContinuityPart objects;
- one or more ordered observations per part;
- required 2D position for every canonical observation;
- optional timestamp, altitude, cumulative distance, and observed/device speed;
- parser/normalizer software provenance.

The schema deliberately does not serialize one unconditional LineString. Array boundaries are the explicit no-edge boundaries between continuity parts.

A singleton part is valid canonical evidence. Whether the overall track has usable positive-length route geometry is a semantic-validation question and controls whether SpatialAssessment may be created.

Observed/device speed is represented as `observed_speed_mps`; derived geometric speed remains a later derived metric and must not silently reuse the same semantic field.

### TargetArea representation

The schema freezes:

- stable identity plus immutable revision identity;
- OGC:CRS84 canonical spatial reference;
- Polygon or MultiPolygon geometry only;
- standard hole nesting through GeoJSON-compatible coordinates;
- explicit provenance for the exact boundary revision.

JSON Schema rejects unsupported geometry types and empty coordinate containers structurally. Ring closure, self-intersection, hole validity, and full polygon topology remain semantic-validator responsibilities.

### SpatialAssessment representation

The schema freezes:

- exact CanonicalTrack and TargetArea revision references;
- `relation = inside | partial | outside | unknown`;
- `coverage_completeness = complete | incomplete`;
- structured `coverage_uncertainties`;
- ordered TargetSegment revision references;
- algorithm provenance.

Schema-level invariants include:

- `unknown → incomplete`;
- `outside → complete`;
- `outside → zero TargetSegment refs`;
- `inside/partial → at least one TargetSegment ref`;
- `incomplete → at least one CoverageUncertainty`;
- `complete → zero CoverageUncertainty`.

Cross-object spatial claims remain semantic-validator responsibilities.

### TargetSegment representation

The schema freezes:

- exact parent SpatialAssessment revision;
- exact parent CanonicalTrack revision;
- zero-based ordinal;
- OGC:CRS84 geometry;
- start/end TrackPosition lineage;
- derived LineString geometry.

Positive length, parent-position bounds, geometry/lineage regeneration, and ordering consistency are semantic validation requirements rather than JSON Schema-only checks.

### Remaining core schema order

1. TrackSource
2. Activity

The four spatially coupled schemas are now present. The next validation step is cross-object semantic validation across CanonicalTrack, TargetArea, SpatialAssessment, and TargetSegment revisions.
