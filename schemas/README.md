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

## Executable schema validation

The repository now includes a formal Draft 2020-12 fixture runner:

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate_schema_fixtures.py
```

Use `--verbose` to print validation errors for expected-invalid fixtures and to show semantic-layer annotations that are intentionally not evaluated by this runner.

The runner:

1. loads every `schemas/*.schema.json` document;
2. checks each schema itself with `Draft202012Validator.check_schema`;
3. assigns an in-memory file-URI `$id` so repository-relative `$ref` values resolve without changing checked-in schemas;
4. builds a standards-based `referencing.Registry`;
5. enables format checking, including canonical RFC3339/date-time constraints;
6. reads `tests/fixtures/manifest.json`;
7. validates each fixture against its declared schema;
8. compares actual validity with `expect_schema_valid`;
9. exits non-zero on any mismatch or runner/manifest/schema error.

Exit codes:

- `0` — every schema-validity expectation matched;
- `1` — at least one fixture validity result disagreed with the manifest;
- `2` — repository, manifest, JSON, schema, or reference-resolution error prevented a trustworthy run.

This runner intentionally does **not** evaluate `expect_semantic_valid` or `expect_assessable`; those belong to the separate semantic-validation runner.

GitHub Actions executes the same command on pushes to `main`, pull requests, and manual workflow dispatch through `.github/workflows/schema-validation.yml`.

## Executable semantic validation

Layer B is implemented independently in:

```bash
python scripts/validate_semantic_fixtures.py
```

Use `--verbose` to print the reasons expected-invalid semantic fixtures/scenarios are rejected.

The semantic runner does not use JSON Schema as a substitute for domain logic. It evaluates:

- explicit Polygon/MultiPolygon ring closure and Shapely/GEOS topology validity;
- CanonicalTrack positive-length assessability separately from canonical evidence validity;
- TargetSegment positive length and ordered same-part lineage;
- TrackPosition bounds against the parent CanonicalTrack;
- deterministic interpolation of TrackPosition endpoints;
- TargetSegment geometry regeneration against the parent track interval;
- TargetArea coverage of linked TargetSegment geometry;
- exact Activity → TrackSource → CanonicalTrack revision/identity links;
- exact SpatialAssessment → CanonicalTrack/TargetArea revision links;
- exact TargetSegment → SpatialAssessment/CanonicalTrack revision links;
- spatial-reference consistency;
- TargetSegment ordinal/reference ordering;
- deterministic relation and exhaustive target coverage for complete, fully observed single-part linked scenarios.

Local semantic expectations come from `tests/fixtures/manifest.json`. Cross-object expectations come from `tests/fixtures/semantic-scenarios.json`.

The runner keeps `expect_assessable` separate from `expect_semantic_valid`: a singleton CanonicalTrack is valid canonical evidence but is not assessable as positive-length route geometry.

Exit codes mirror the schema runner:

- `0` — every semantic/assessability/scenario expectation matched;
- `1` — at least one semantic expectation mismatched;
- `2` — repository, manifest, JSON, or runner state prevented a trustworthy run.

The CI workflow runs Layer A first and this independent Layer B runner second.

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

- `activity.schema.json`
- `track-source.schema.json`
- `canonical-track.schema.json`
- `target-area.schema.json`
- `spatial-assessment.schema.json`
- `target-segment.schema.json`

Initial fixtures and expected validation layers are recorded in `../tests/fixtures/manifest.json`.

### Activity representation

The Activity schema is intentionally minimal.

It freezes only:

- `schema_version`;
- stable project-local `id`;
- optional explicitly namespaced extensions.

Activity does **not** embed source-native IDs, source metadata similarity fields, TrackSource children, geometry, or spatial classification.

This is deliberate: Activity is the stable real-world event identity anchor. Source-native identity belongs to TrackSource provenance, and cross-source reconciliation remains an explicit future adapter/runtime process under ADR-0008.

An Activity with zero TrackSources is schema-valid.

### TrackSource representation

The schema freezes:

- immutable TrackSource identity/revision;
- ownership by stable Activity identity;
- source namespace/origin provenance;
- optional source-native ID and provenance locator;
- representation media type;
- optional original display/file name;
- optional SHA-256 content identity;
- no assumption that the source must be a filesystem file.

TrackSource does not contain parse status or CanonicalTrack output. A durably preserved source can remain a valid TrackSource even when parsing later fails.

A remote URL/locator alone does not establish durable acquisition; durable lifecycle enforcement remains Milestone 3/5 runtime behavior.

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

### Core schema set complete

All six frozen v0.1 core entity schemas are now present.

The schema and semantic runners are now both executable. The next Milestone 1 focus is coverage and conformance:

1. expand linked semantic scenarios beyond the initial partial-crossing case;
2. map every Milestone 0 edge case to a fixture, semantic scenario, or explicit non-file test representation;
3. add semantic cases for holes, MultiPolygon components, point touch, boundary overlap, relevant gaps, and multiple TargetSegments;
4. stabilize both runners in CI before declaring Milestone 1 complete.
