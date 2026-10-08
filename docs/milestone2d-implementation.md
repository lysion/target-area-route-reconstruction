# M2D — TargetSegment extraction and SpatialAssessment assembly

**Status:** ACTIVE, draft implementation in PR #8; not independently accepted.

**Contract baseline:** ADR-0011 accepted in PR #7 after the original PR #6 blocker. The original `docs/milestone2d-target-segments.md` remains the historical stop/reproducer record. It is not the current M2D completion status.

## Purpose and boundary

Consume an **exact verified M2C supporting proof**, never spatial metadata or a schema-valid untrusted proof. The public entry points are:

- `assemble_spatial_entities(proof, evidence, quality_projection, quality_policy, target_area, target_reference)`
- `verify_spatial_entities(bundle, proof, evidence, quality_projection, quality_policy, target_area, target_reference)`

The producer first demands a valid `verify_spatial_relation` result, which includes the M2B quality gate. Non-assessable proof returns `non_assessable` and no entities. Invalid or stale M2C claims return `invalid_input` with stable issue codes. A malformed assembly or unrepresentable geometry fails explicitly; it cannot be converted to `unknown` or `outside`.

No missing GPS geometry, gap chord, new source evidence, relation change or completeness change is created in M2D.

## Extraction

For each independently verified quality-admitted parent interval, collect the M2C proved positive-length covered fragments in original parent order. Covered zero-distance original edges may extend an adjacent observed segment's TrackPosition lineage, but they never form a positive-length segment alone.

Coalesce only end-to-start adjacent parent intervals **within that admissible run**. Source part boundaries, quality-excluded edges, uncovered positive intervals and gaps always split segments. Identical geometry across different visits remains a separate occurrence.

Regenerate every final ordered LineString from the exact original parent TrackPosition start/end and all intermediate observations. Do not use clipping geometry, simplify, de-duplicate or resample. M2C owns clipping; M2D owns maximal grouping and original-parent regeneration.

## CoverageUncertainty

Every M2C gap where `target_coverage_unresolved` is true becomes one uncertainty. Its affected range copies the exact gap's real start/end; absent leading/trailing neighbors become explicit null only under ADR-0011. Resolved/target-irrelevant gaps are not exported as uncertainties.

Each record includes the gap index, kind, causes, diagnostic indices, optional quality-exclusion index, bound classification, M2A evidence fingerprint, exact QualityProjection fingerprint and M2C proof digest. Source and quality uncertainty are distinguishable.

## Deterministic identity and reciprocal revisions

The six entity schemas require a SpatialAssessment revision in each TargetSegment, and TargetSegment revision references in the assessment. The v0.1 schema specifies opaque IDs, not a hash algorithm for these mutually referencing documents.

This M2D implementation uses the **versioned pre-reference assembly seed** policy `m2d-prereference-seed-v1`:

1. Gather exact verified proof, ordered segment semantic payloads and uncertainty payloads.
2. Canonically serialize and SHA-256 hash this pre-reference seed.
3. Derive assessment stable ID from parent CanonicalTrack and TargetArea stable IDs; derive assessment revision from the seed.
4. Derive every ordinal-specific segment ID/revision from the same seed plus its ordered semantic payload.
5. Construct all final reciprocal references in one pass, without post-creation mutation.

Final mutually referencing JSON is **not** hashed to a fixed point. Equal evidence/version/parameters produces byte-identical snapshots. A quality/target/proof change changes the seed and revision. IDs are opaque; their string format is not user-facing evidence of semantics.

All entity snapshots in the public supporting bundle are held as immutable serialized UTF-8 JSON strings; property access creates detached dicts.

## Verifier scope

The verifier never imports or invokes the producer. It independently gates authority through M2C, validates both JSON schemas, derives the complete ordered/maximal interval set, checks regeneration from parent observations, checks the unresolved-gap mapping, relation/completeness preservation, algorithm provenance, ordinal/revision identity, and reciprocal references.

The parent interpolation/serialization and hashing primitives are intentionally shared. Independent M1 fixture lineage checks and adversarial mutations are needed as additional confidence; the verifier is not claimed to be a separately implemented geometric clipping engine.

## Current acceptance limits

- M2E GeoJSON/map and M2F temporal metrics remain out of scope.
- Useful local short-gap bounds and missing-route reconstruction remain unsupported.
- First v0.1.0 implementation targets ordinary CRS84 planar interpolation as M2C explicitly declares.
- This is **a draft implementation**, not M2D DONE, until complete CI, adversarial mutation witnesses and independent review pass.
