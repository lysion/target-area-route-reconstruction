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

## Common-definition conformance

`common.schema.json` is exercised independently through the test-only wrapper `common-conformance.schema.json`.

The current conformance fixtures cover paired valid/invalid cases for:

- opaque `entityId`;
- exact `revisionRef`;
- canonical `spatialReference`;
- CRS84 `position2d` bounds/order;
- UTC `timestampUtc`;
- canonical `trackPosition` fraction semantics;
- lowercase SHA-256 `sha256Hash`.

These are intentionally small contract probes rather than additional domain entities.

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
8. compares actual validity with `expect_schema_valid`, and for negatives requires `expect_schema_error` to match the instance path and schema keyword (not prose);
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

Before any linked semantic check, the runner requires every component to be registered in the fixture manifest, associated with the correct entity schema, expected schema-valid, and actually Layer A-valid. It then evaluates independent domain logic:

- explicit Polygon/MultiPolygon ring closure and Shapely/GEOS topology validity;
- CanonicalTrack positive-length assessability separately from canonical evidence validity;
- TargetSegment positive length and ordered same-part lineage;
- TrackPosition bounds against the parent CanonicalTrack;
- deterministic interpolation of TrackPosition endpoints;
- TargetSegment geometry regeneration against the parent track interval;
- TargetArea-covered ordered parent intervals, preserving direction, multiplicity and part identity;
- exact Activity → TrackSource → CanonicalTrack revision/identity links;
- exact SpatialAssessment → CanonicalTrack/TargetArea revision links;
- exact TargetSegment → SpatialAssessment/CanonicalTrack revision links;
- spatial-reference consistency;
- TargetSegment ordinal/reference ordering;
- maximal coverage of all reliable observed intervals, even when additional coverage is unresolved;
- evidence-first relation facts, including proven `partial` with incomplete coverage.

Semantic negatives require a stable `expect_semantic_issue_code`; an unrelated rejection cannot satisfy the expected failure. The [numerical policy](../docs/numerical-policy.md) defines interpolation/comparison. The [quality hand-off](../docs/quality-layer-interface.md) states the oracle's all-observed-edges-reliable assumption and its current gap-proof capability limit. It does not claim to implement production quality validation.

Local semantic expectations come from `tests/fixtures/manifest.json`. Cross-object expectations come from `tests/fixtures/semantic-scenarios.json`.

The runner keeps `expect_assessable` separate from `expect_semantic_valid`: a singleton CanonicalTrack is valid canonical evidence but is not assessable as positive-length route geometry.

Exit codes mirror the schema runner:

- `0` — every semantic/assessability/scenario expectation matched;
- `1` — at least one semantic expectation mismatched;
- `2` — repository, manifest, JSON, or runner state prevented a trustworthy run.

The CI workflow runs Layer A first and this independent Layer B runner second.

Milestone 1 representation completeness is checked separately with:

```bash
python scripts/validate_edge_case_coverage.py
```

That runner verifies that EC-01 through EC-29 are all mapped exactly once to registered fixtures, linked semantic scenarios, or explicit non-file contract cases. Non-file cases must retain assertion, execution owner/milestone, future test shape and reason. Duplicate/malformed entries and negative references to positive cases fail.

## Raw parser-input fixture baseline

Milestone 1 also includes a privacy-safe raw FIT/GPX baseline under `../tests/source-fixtures/`.

It contains:

- equivalent GPX and FIT route/timestamp inputs;
- GPX without timestamps;
- GPX with two explicit track segments;
- intentionally malformed GPX;
- structurally valid FIT with timestamped records but no positions.
- a complete representative FIT Activity with FileId/Record/Lap/Session/Activity summaries;
- FIT invalid-position sentinels and a positioned/missing/positioned sequence;
- well-formed XML with invalid GPX root, coordinate range or version.

The baseline is described by `../tests/source-fixtures/manifest.json` and validated with:

```bash
python scripts/validate_source_fixture_baseline.py
```

The validator checks hashes, local official GPX 1.1 XSD conformance using pinned lxml, FIT framing/header and file CRC/fields using both the fixture reader and pinned fitdecode, and declared FIT/GPX equivalence. Original minimal FIT streams are labeled separately from the complete Activity. Production parsing remains Milestone 2 work.

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

The schema and semantic runners are executable. The full EC-01 through EC-29 representation map is now complete.

Current coverage artifacts:

- `../tests/edge-case-coverage.json` — machine-readable 29/29 mapping;
- `../tests/nonfile-contract-cases.json` — explicit lifecycle/runtime test contracts;
- `../docs/milestone1-edge-case-coverage.md` — human-readable complete mapping;
- `../docs/milestone1-linked-scenario-coverage.md` — linked spatial scenario details.

Current registered set: 260 schema fixtures, 39 linked semantic scenarios (including 23 adversarial/control scenarios), 13 non-file contract cases, and 6 coverage-map negative cross-object registrations. Fifteen schema fixtures independently exercise common definitions, including exact lowercase 64-character SHA-256 digests. Six metric inputs retain the M1 optional-capability commitment.

There are 56 local/linked semantic expectations and 12 raw files in two FIT/GPX equivalence groups. Entity fixture counts include shared-shaped scenario components and are not independent behavioral coverage counts. Conventional unit/integration and mutation tests run with `python -m unittest discover -s tests -p 'test_*.py'`.

The previous PASS was invalidated by the adversarial audit. Current milestone status and final results are governed by [ROADMAP](../ROADMAP.md) and [the fresh re-exit review](../docs/milestone1-re-exit-review.md); historical counts remain in the original reviews.
