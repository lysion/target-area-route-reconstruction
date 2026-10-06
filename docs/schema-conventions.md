# Shared Schema Conventions

**Milestone:** 1 — Schemas and Fixtures  
**Status:** Accepted for v0.1 schema work  
**Domain baseline:** frozen v0.1 contract in `docs/domain-model.md` and ADR-0010

This document defines representation conventions shared by the six v0.1 spatial-core JSON Schemas.

It does not change the frozen domain semantics. If a schema requirement conflicts with the domain contract, the schema must change or a superseding ADR must be created; implementation convenience is not sufficient reason to weaken a frozen invariant.

## 1. JSON Schema dialect

All v0.1 schemas use **JSON Schema Draft 2020-12**.

Every schema document must declare:

~~~json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema"
}
~~~

Milestone 1 does not assign permanent remote `$id` URLs. Repository-relative filenames are the development-time schema identifiers, and cross-schema references use relative `$ref` paths such as:

~~~json
{
  "$ref": "common.schema.json#/$defs/entityId"
}
~~~

A stable publication URI namespace may be introduced at release time without changing instance semantics.

No custom JSON Schema keywords are allowed in v0.1.

## 2. File and naming conventions

Schema filenames use lowercase kebab-case and the `.schema.json` suffix.

The six frozen entity schemas are:

- `activity.schema.json`
- `track-source.schema.json`
- `canonical-track.schema.json`
- `target-area.schema.json`
- `spatial-assessment.schema.json`
- `target-segment.schema.json`

Shared value definitions live in:

- `common.schema.json`

JSON property names use `lower_snake_case`.

Enum values use lowercase `snake_case`.

Identifiers and enum values are case-sensitive.

## 3. Schema version

Every top-level entity instance carries:

~~~json
{
  "schema_version": "0.1.0"
}
~~~

For the initial v0.1 schema family, entity schemas constrain this field with `const: "0.1.0"`.

`schema_version` identifies the serialized contract, not the Activity, parser, algorithm, source, or application version.

A change that alters accepted instance meaning or compatibility requires an explicit schema-version decision. A domain-semantic change additionally requires a superseding ADR under the frozen-contract change-control rule.

## 4. Closed core objects

Core objects are closed by default.

Concrete entity schemas should use `unevaluatedProperties: false` or an equivalent Draft 2020-12-safe closure pattern after composition.

Shared value objects should use `additionalProperties: false` when they are not composed through `allOf`.

Do not add a generic `metadata` bag to bypass schema design.

If an entity has a legitimate extension need, it may opt into the shared `extensions` object explicitly. Extension content:

- must not redefine frozen core semantics;
- must not be required to interpret a valid core instance;
- should use namespaced keys;
- is ignored by core deterministic logic unless a later contract explicitly adopts that extension.

## 5. Required, optional, and null

**Omitted and null are not synonyms.**

Default rule:

- required value present → use the declared non-null type;
- optional value unavailable/not applicable → omit the property;
- `null` is forbidden unless the entity schema explicitly gives null a distinct documented meaning.

Do not use empty string, zero, empty object, empty array, or sentinel numbers as substitutes for unknown/missing data.

The domain enum value `unknown` is a real SpatialAssessment relation state and is not equivalent to JSON null.

Schemas must not rely on the JSON Schema `default` keyword to mutate or fill input data.

## 6. Identity and revision references

Identifiers are opaque strings. Consumers must not parse semantic meaning from them.

### Stable entity identity

Shared `entityId`:

- string;
- non-empty;
- maximum 256 Unicode code points;
- case-sensitive.

Do not require UUID syntax.

### Immutable revision identity

Where a domain object has versioned/derived snapshots, use a separate opaque `revision_id`.

`revision_id` identifies one immutable serialized/derived revision. It is not the same as:

- `schema_version`;
- parser version;
- algorithm version;
- TargetArea human label;
- source-native activity ID.

### Reference shapes

Use an embedded `entityRef` when stable identity is sufficient:

~~~json
{
  "id": "activity-local-id"
}
~~~

Use a `revisionRef` when the exact immutable revision matters:

~~~json
{
  "id": "target-area-id",
  "revision_id": "target-area-revision-id"
}
~~~

References between aggregate roots use these reference objects rather than inlining a second authoritative copy of the referenced entity.

Owned value objects such as ContinuityPart, TrackPosition, and CoverageUncertainty are embedded in their owner.

## 7. Source-native identifiers

External/provider identifiers are provenance, not global entity identity.

A source-native identifier must be paired with its source namespace/origin. Never serialize a bare provider ID as though it were globally unique.

Similarity in timestamps, distance, duration, or geometry never changes identity. This convention implements ADR-0008 rather than replacing it.

## 8. Canonical spatial reference

v0.1 canonical geometry uses **OGC:CRS84**:

- longitude first;
- latitude second;
- decimal degrees;
- longitude range `[-180, 180]`;
- latitude range `[-90, 90]`.

The serialized identifier is:

~~~json
{
  "spatial_reference": "OGC:CRS84"
}
~~~

Every top-level core entity that directly serializes canonical geometry must carry or unambiguously inherit this value according to its entity schema.

Source-native coordinate encoding remains TrackSource provenance and is normalized before entering canonical geometry.

Assessment requires CanonicalTrack and TargetArea geometry to share the same canonical spatial reference.

Do not use the deprecated GeoJSON `crs` member.

## 9. Position representation

A canonical 2D position is exactly:

~~~json
[longitude, latitude]
~~~

It contains exactly two JSON numbers.

Altitude is not a third coordinate in the v0.1 canonical 2D position. If altitude is available, it is represented as a separate optional observation/metric field with explicit units.

This keeps target-area topology strictly two-dimensional and avoids conflating spatial reference with vertical datum semantics.

Repeated positions are valid observations; coordinate uniqueness is not a validity rule.

## 10. Geometry representation

TargetArea geometry uses GeoJSON-compatible geometry objects restricted by the frozen domain contract to:

- `Polygon`;
- `MultiPolygon`.

Polygon holes use standard linear-ring nesting.

TargetSegment derived geometry, when serialized, uses a GeoJSON-compatible `LineString` representation in the canonical spatial reference.

CanonicalTrack is not serialized as one unconditional GeoJSON LineString because it must preserve:

- ordered observations;
- continuity parts;
- optional per-observation evidence;
- explicit no-edge semantics between parts.

### Schema validation versus semantic geometry validation

JSON Schema validates structural shape and numeric bounds.

It cannot by itself prove every geometric invariant, such as:

- polygon ring closure by comparing first and last coordinates;
- self-intersection validity;
- exact MultiPolygon topology;
- cross-object spatial-reference equality;
- correct TrackPosition bounds against a parent track;
- exact TargetSegment regeneration from lineage.

Those invariants must have deterministic semantic validators and fixtures in later Milestone 1/2 work.

Do not introduce custom JSON Schema keywords to simulate a GIS engine.

## 11. Ordering and indices

JSON object property order has no meaning.

Array order is semantic only where the entity contract says it is semantic.

In v0.1, at minimum:

- CanonicalTrack continuity parts are ordered;
- observations within each ContinuityPart are ordered;
- lineage positions are interpreted against that ordering;
- TargetSegments are ordered by parent-track position when emitted as an ordered collection.

All schema-level indices are **zero-based**.

## 12. TrackPosition representation

The shared v0.1 TrackPosition shape is:

~~~json
{
  "part_index": 0,
  "observation_index": 42,
  "fraction_to_next": 0.375
}
~~~

Semantics:

- `part_index` — zero-based ContinuityPart index;
- `observation_index` — zero-based observation index within that part;
- `fraction_to_next` — location on the edge from this observation toward the next observation.

Canonical fraction range is:

~~~text
0 <= fraction_to_next < 1
~~~

`0` means exactly at `observation_index`.

A position that mathematically lands at fraction `1` must be normalized to the next observation with fraction `0`, when that next observation exists.

The terminal observation of a part is represented with its own `observation_index` and `fraction_to_next = 0`.

Whether an index is in range for a particular parent CanonicalTrack is a semantic cross-object validation, not a standalone JSON Schema fact.

## 13. Time representation

Canonical absolute instants use RFC 3339 / JSON Schema `date-time` strings normalized to UTC with a trailing `Z`.

Example:

~~~json
"2026-10-06T11:19:00Z"
~~~

Do not use local naive timestamps or Unix epoch numbers in canonical JSON.

Source-local/raw time representation may remain in TrackSource provenance when needed, but a canonical temporal instant must be unambiguous.

Validation tooling for this repository must enable `date-time` format assertion.

Timestamps remain optional for spatial validity under ADR-0006.

## 14. Units

Use SI-derived units and encode the unit in the property name for scalar measurements.

Preferred suffixes include:

- `_m` — metres;
- `_s` — seconds;
- `_mps` — metres per second;
- `_deg` — degrees when not already implied by the canonical position;
- `_fraction` only when a dimensionless ratio is not otherwise obvious.

Examples:

- `distance_m`
- `duration_s`
- `speed_mps`
- `altitude_m`

Pace, if serialized later, uses seconds per kilometre with an explicit name such as `pace_s_per_km`.

Do not use unitless fields whose unit must be guessed from documentation.

## 15. Numeric rules

Use JSON numbers for measurements and coordinates.

Do not serialize NaN, Infinity, or negative zero as semantic sentinels.

Non-negative measurements use `minimum: 0` unless the domain explicitly permits negatives.

Fractions use explicit bounds.

Do not round canonical coordinates merely to make files smaller. Precision reduction, if ever introduced, is a derived/export policy with provenance rather than a silent canonicalization step.

Exact coordinate equality across separate TrackSources is never assumed.

## 16. Enum rules

Enums are closed for each schema version.

Adding a new value that changes domain meaning is a contract change, not a harmless implementation detail.

Do not create convenience enum values such as `n/a`, `unset`, or `missing`.

Use a domain value such as `unknown` only when the frozen domain semantics define it.

## 17. Provenance

Derived or normalized records must preserve the provenance required by the frozen domain contract.

The shared `softwareProvenance` value object contains:

- `name`;
- `version`;
- optional exact `parameters` object when needed to reproduce the transformation;
- optional `parameters_fingerprint` when a stable external parameter set is referenced.

Entity schemas decide which provenance object is required and which parent/source references must accompany it.

A generated wall-clock timestamp is not required merely to make a deterministic derived entity valid; persistence/audit timestamps belong to runtime records when needed.

## 18. Content hashes

Where byte/content identity is represented, use an explicit hash object rather than overloading an entity ID.

Initial supported canonical hash form:

~~~json
{
  "algorithm": "sha256",
  "digest": "0123456789abcdef..."
}
~~~

The SHA-256 digest is lowercase hexadecimal with exactly 64 characters.

This definition supports later idempotency work without making a hash the semantic identity of Activity.

## 19. Extension map

The shared `extensions` shape is an object for explicitly permitted non-core data.

Rules:

- core entity schemas opt in explicitly; it is not automatically available everywhere;
- keys should be namespaced, for example `org.example.field_group`;
- extension values may be arbitrary valid JSON;
- no frozen invariant may depend on an extension;
- a field that becomes required by the deterministic core must graduate into a versioned schema instead of remaining an extension.

## 20. Schema composition

Reusable shapes belong in `common.schema.json#/$defs`.

Prefer `$ref` to duplicated definitions.

Use `allOf` only where composition materially improves reuse. Avoid inheritance-style schema hierarchies that make object closure ambiguous.

Concrete entity schemas should remain readable without following a deep reference graph.

## 21. Validation layers

Milestone 1 distinguishes three validation layers.

### Layer A — JSON Schema validation

Checks:

- required fields;
- primitive types;
- enum membership;
- numeric/string bounds;
- coordinate structural shape;
- closed-object rules;
- local conditional invariants expressible in standard Draft 2020-12.

### Layer B — semantic validation

Checks cross-field/cross-object or geometric invariants, for example:

- referenced entity/revision exists;
- TrackPosition index is valid for its parent;
- polygon topology is valid;
- SpatialAssessment and TargetArea share the required revision/reference;
- TargetSegment lineage regenerates its geometry;
- `relation` and `coverage_completeness` satisfy frozen combinations;
- a CanonicalTrack part described as usable can actually form positive-length geometry.

### Layer C — fixture expectation validation

Checks expected behavior for full scenarios:

- classification result;
- number/order of TargetSegments;
- exact lineage positions where defined;
- completeness;
- known invalid-case failure reason.

A case is not considered implemented merely because its JSON shape validates.

## 22. Error handling convention

Schema validation failure is not converted into a domain classification.

Invalid input:

- does not become `outside`;
- does not become `unknown` automatically;
- does not fabricate an empty TargetSegment list as a successful result.

Validation errors remain explicit validation/runtime outcomes.

## 23. Compatibility with the frozen contract

The following representation choices are now fixed for the v0.1 schema family:

- JSON Schema Draft 2020-12;
- UTF-8 JSON;
- lowercase snake_case properties/enums;
- top-level `schema_version = "0.1.0"`;
- opaque string IDs;
- separate `revision_id` where exact immutable revisions are required;
- relative `$ref` paths during repository development;
- OGC:CRS84 canonical 2D coordinates in longitude/latitude order;
- zero-based indices;
- the TrackPosition shape defined above;
- omit-missing rather than null-by-default;
- closed core objects with explicit extension points only;
- RFC3339 UTC canonical timestamps;
- explicit SI unit suffixes.

Changing one of these representation conventions after schemas/fixtures depend on it requires an explicit schema compatibility review. Changing a frozen domain semantic additionally requires a superseding ADR.
