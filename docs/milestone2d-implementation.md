# M2D — TargetSegment extraction and SpatialAssessment assembly

**Status:** DONE — PR #8 final head `2477468d79428acb776d96967bbf66aaa539ecaf` passed CI [37766687849](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37766687849), independent re-review [5455755938](https://github.com/lysion/target-area-route-reconstruction/pull/8#pullrequestreview-5455755938) returned PASS, merged as `3e99364459188e24efd3bd901cc2cb9ad3d5dd1a`. ADR-0012 accepted.

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

The accepted snapshot contract is specified in [ADR-0012](decisions/0012-m2d-canonical-assembly-snapshots.md). M2D algorithm `0.1.1` serializes `snapshot_policy=m2d-canonical-payload-v1`. Semantic tolerance does not authorize a different canonical payload under an unchanged revision.

## Verifier scope

The verifier never imports or invokes the producer. It independently gates authority through M2C, validates both JSON schemas, derives the complete ordered/maximal interval set, checks regeneration from parent observations, checks the unresolved-gap mapping, relation/completeness preservation, algorithm provenance, ordinal/revision identity, and reciprocal references.

The parent interpolation/serialization and hashing primitives are intentionally shared. Independent M1 fixture lineage checks and adversarial mutations are needed as additional confidence; the verifier is not claimed to be a separately implemented geometric clipping engine.

## Current acceptance limits

- M2E GeoJSON/map and M2F temporal metrics remain out of scope.
- Useful local short-gap bounds and missing-route reconstruction remain unsupported.
- First v0.1.0 implementation targets ordinary CRS84 planar interpolation as M2C explicitly declares.
- This implementation passed final-head CI and independent review; M2D is **DONE**. M2E is the active next checkpoint, and M2F is NOT STARTED.

## Historical validation at initial implementation handoff

Before the independent adversarial audit, the code-bearing change passed [Contract validation CI run 37733440399](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37733440399):

| Gate | Result |
|---|---:|
| Entire unittest suite | 190/190 |
| M1 schema fixture expectations | 260/260 |
| Semantic expectations | 56/56 |
| Frozen edge-case mapping | 29/29 |
| Raw source baseline | 12/12; 2 equivalence groups |
| Independent M1 geometry oracle on production M2D output | 19 valid scenarios |
| Actual production-code mutants killed by unmodified witnesses | 10/10 |
| Isolated installed-wheel M2A→M2B→M2C→M2D | 3 end-to-end cases + invalid GPX rejection |
| Earlier ADR-0011 open-gap acceptance tests | retained and passing |

Explicit negative coverage includes stale upstream proof/references, corrupted reciprocal revisions, altered relation, missing/duplicate traversals, mutated segment geometry, omitted target-relevant uncertainty and false point-anchor substitution for a leading gap. Distinct visited occurrences and stationary/repeated observations remain ordered.

**Historical review gate:** PR #8 remained open until independent review; its final head subsequently passed review and was merged. Passing CI alone was never the acceptance decision.


## PR #8 admission remediation and before/after evidence

Baseline: `533b0b94c90e08391892daa481c49f125f4a59ac`, main `4dd33936680432eedbd5bc4d2aa5196cdc01dfe4`. Existing branch was fast-forwarded, with no rewritten/discarded commits. The [governing task](https://github.com/lysion/target-area-route-reconstruction/pull/8#issuecomment-6053442931) follows independent NOT READY review 5452187379 and [PR #9 red CI](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37734860667). The original two PR #9 tests were reproduced locally as exactly two assertion failures before edits.

| Finding | Before | Corrected behavior / permanent witness |
|---|---|---|
| B1: duplicate JSON authority | last-member-wins assessment accepted | Recursive duplicate rejection, including escaped aliases/equal values/nested fields/later segments; `M2D_DUPLICATE_JSON_MEMBER` |
| B2: numerical/identity ambiguity | one ULP reported as a lineage mismatch despite independent M1 acceptance | Explicit canonical-snapshot policy (ADR-0012); original input stays M1-valid, M2D snapshot-invalid, without a geometry mismatch |
| Unbound schema-legal content | Added assessment/segment extensions accepted with unchanged revisions | Whole canonical expected payload checked after independent invariants; `M2D_CANONICAL_SNAPSHOT_MISMATCH` |
| Type ambiguity | Provenance `false` accepted as index `0`; proof parameter `8.0` treated as integer `8` | Type-sensitive canonical provenance checks, additional post-M2C metadata gate |
| Mutable bundle container | List accepted for immutable segment tuple | Exact wrapper/string/tuple shape required |
| Unhandled malformed input | Deep JSON raised `RecursionError` | Stable malformed-bundle result; engine/internal failures never become successful empty output |
| Numeric underflow | `1e-9999` silently decoded as zero | Explicit `M2D_JSON_NUMBER_UNREPRESENTABLE`; tiny representable geometry remains valid |

The original PR #9 file/branch is not modified or merged. Its unchanged one-ULP **acceptance expectation** is not adopted: comment 6053442931 expressly permits canonical-snapshot option (b). The same input and independent M1 comparison live in `test_pr9_one_ulp_is_semantic_not_snapshot_equivalence`; the new assertion distinguishes semantic validity from immutable snapshot validity. This is a documented policy adjudication, not a claim that the historical red test passed unchanged.

### Ownership and independence

- `spatial_entities.py`: producer, per-admitted-run maximal grouping, uncertainty conversion, pre-reference seed and assembly.
- `spatial_entities_verifier.py`: mandatory M2C authority gate, independently swept expected intervals, schema/lineage/relation/uncertainty/ref/identity/payload checks. It never imports or calls the producer.
- `_m2d_common.py`: strict JSON, packaged schema loading, type-sensitive metadata comparisons, numerical interpolation/regeneration/comparison and hash/serialization primitives.
- `spatial_entities_models.py`: unchanged supporting result wrappers and public API values; no seventh entity or persistence.

The verifier's expected-payload construction follows semantic checks; it is not a call to the producer followed by equality. Shared interpolation/serialization remains a shared-oracle risk. The 19 M1 scenario comparisons, hand-checked tiny/ordered/diagonal witnesses and actual shared-regeneration mutation detect demonstrated common-mode errors. No claim of independent spatial reclassification is made or needed.

### Failure identity

| Codes | Meaning |
|---|---|
| `M2D_DUPLICATE_JSON_MEMBER` | Ambiguous member at any nesting level; path identifies assessment or segment index |
| `M2D_NONFINITE_JSON`, `M2D_JSON_NUMBER_UNREPRESENTABLE` | NaN/Inf/overflow or nonzero underflow, before semantic acceptance |
| `M2D_BUNDLE_MALFORMED`, `M2D_ENTITY_SCHEMA_INVALID` | Wrapper/JSON failure or frozen schema violation |
| `M2D_SPATIAL_PROOF_INVALID`, `M2D_PROOF_METADATA_MISMATCH`, `M2D_AUTHORITY_CHECK_FAILED` | Failed upstream gate, type-sensitive provenance mismatch, or authority-check exception; no assembly |
| `M2D_NONASSESSABLE_ENTITIES` | Entity supplied for non-assessable proof |
| `M2D_TARGET_COVERAGE_NOT_EXHAUSTIVE`, `M2D_MAXIMALITY_OR_LINEAGE_MISMATCH` | Missing/extra coverage or wrong ordered maximal parent ranges |
| `M2D_GEOMETRY_REGEN_MISMATCH` | Wrong vertex count/order, collapsed positive geometry, or coordinate mismatch beyond bounded comparison |
| `M2D_CANONICAL_SNAPSHOT_MISMATCH` | Payload not bound to this algorithm/revision, even if semantically close |
| `M2D_PARENT_REFERENCE_MISMATCH`, `M2D_SEGMENT_PARENT_MISMATCH` | Wrong exact parent/target authority or CRS |
| `M2D_RELATION_OR_COMPLETENESS_CHANGED`, `M2D_UNCERTAINTY_MISMATCH`, `M2D_ALGORITHM_MISMATCH` | Altered inherited facts, uncertainty provenance or parameters |
| `M2D_ASSESSMENT_IDENTITY_MISMATCH`, `M2D_SEGMENT_REFERENCES_MISMATCH`, `M2D_RECIPROCAL_REFERENCES_MISMATCH` | Stale/forged identities or inconsistent reciprocal references |
| `M2D_VERIFICATION_FAILURE`, `M2D_ASSEMBLY_FAILURE`, `M2D_ASSEMBLY_NUMERICAL_OR_STRUCTURAL_FAILURE`, `M2D_ASSEMBLY_VERIFICATION_FAILED` | Explicit internal/numerical/self-verification failure, never valid empty entities |

Malformed JSON and schema failures short-circuit before domain checks. Numerical closeness and canonical payload may produce distinct codes; negatives assert their intended code, not merely “invalid.” The verifier catches unexpected `Exception` at its public boundary; process-control `BaseException` is not swallowed. Deterministic codes do not include exception strings or filesystem paths.

### Full admission audit coverage

`tests/test_spatial_entities.py` retains the original 22 tests and ten production-code mutations. `tests/test_spatial_entities_hardening.py` adds strict JSON/revision, independent malformed-entity attacks and authority/failure tests. Actual mutated production copies are killed by unchanged witnesses with `AssertionError`, not import/runtime crashes; seven additional mutants attack duplicate handling/reason identity, assessment/segment snapshot checks, semantic tolerance, nonzero underflow and metadata gating.

Coverage includes all six relation/completeness combinations supported by the frozen contract, non-assessable singleton/all-excluded tracks, repeated visits/parts/coordinates, zero-distance retained vertices, Polygon holes/MultiPolygon, boundary/point contact, fractional/diagonal/tiny geometry, non-maximal split, overlap/reorder/drop/duplicate/shortening, source/quality gap merge, FIT missing runs with exact diagnostic indices, leading/trailing nulls, stale authority, unchanged input evidence, forged reciprocal revisions and verifier independence. Incomplete results must contain all known proved coverage.

Current M2B supports no local disjoint proof method: the converter's target-irrelevant branch has a narrow predicate test, while a fabricated disjoint M2C claim is rejected by the public gate. This is not advertised as a valid production disjoint-bound witness. No new gap constraints, target classification, missing path or M2E behavior was introduced.

### M2E handoff and remaining obligations

[Support boundaries and ownership](v0.1-support-boundaries.md) classify all current M2 limitations. Strict authority, full observed segment coverage, exact uncertainty, immutable identity, independent adversarial/mutation checks and installed-wheel behavior are M2D admission requirements. Local gap bounds, more quality algorithms, periodic/geodesic clipping and comprehensive FIT profile combinations remain explicitly unsupported; M3 persistence, M2E export/map, M2F metrics and M7 reconstruction are later work. M2E must consume accepted entity snapshots and display uncertainty without converting it to geometry. Independent acceptance occurred in review 5455755938 and PR #8 was merged; M2D is DONE and M2E may proceed.

### Remediation validation record

CI-equivalent local environment: Python 3.11.16, jsonschema 4.26.0, Shapely 2.1.2 / GEOS 3.13.1, fitdecode 0.11.0, lxml 6.1.3, GeographicLib 2.1. Runtime dependencies and core schemas are unchanged by this remediation.

| Command / gate | Result |
|---|---:|
| `python -m unittest discover -s tests -p 'test_spatial_entities*.py' -v` | 56/56 (22 original + 34 admission tests) |
| `python -m unittest discover -s tests -p 'test_*.py' -v` | 224/224 (190 original + 34 new) |
| M2A / M2B / M2C focused classes within full suite | 39 / 49 / 44, all pass |
| ADR-0011 contract regressions | 11/11 |
| `python scripts/validate_schema_fixtures.py --verbose` | 260/260, eight schema documents |
| `python scripts/validate_semantic_fixtures.py --verbose` | 56/56 expectations; 39 linked scenarios |
| `python scripts/validate_edge_case_coverage.py` | 29/29; six negative registrations; 13 owned non-file cases |
| `python scripts/validate_source_fixture_baseline.py` | 12/12 files; two equivalence groups |
| Independent M1 parent-lineage oracle | All 19 valid scenario outputs, original one-ULP and additional diagonal witness |
| Actual production mutations | Original 10/10 + admission 7/7 assertion-killed |
| Isolated wheel outside checkout | Three M2A→M2D pipelines, six duplicate/snapshot attacks, five packaged schemas, invalid GPX XSD rejection |
| `git diff --check` | PASS |

CI now additionally checks commit whitespace and runs the expanded outside-checkout wheel checks. The final-head GitHub Actions result/link is recorded in PR #8 alongside the exact head SHA; this in-commit record does not claim a future CI run has passed. Independent acceptance is still pending.

Self-adversarial review confirmed no schema or M2A–M2C production edits, no geometry-set equality/deduplication, no gap chord or new gap-bound method, no post-creation reciprocal-reference mutation, no persistence/metric/export/map code, and no calls from the verifier to the producer. Input evidence snapshots are unchanged across assembly. Historical PASS and NOT READY evidence are both retained above.
