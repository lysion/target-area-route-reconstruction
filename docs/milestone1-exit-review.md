# Milestone 1 Exit Review

**Review date:** 2026-10-07  
**Milestone:** 1 — Schemas and Fixtures  
**Result:** **NOT READY — one blocking gap remains**

## Review scope

This review checks the Milestone 1 goal, work items, deliverables, and exit criteria in `ROADMAP.md` against the current repository state.

The review also checks two final concerns called out at the end of Milestone 1 execution:

1. source/platform independence of the six core schemas and validators;
2. ownership of the 13 explicit non-file contract cases.

## Exit-criteria audit

| Criterion | Result | Evidence |
|---|---|---|
| Schemas validate all intended valid fixtures | PASS | Contract-validation CI on commit `74ae23e103303a71b0ed9f730ee8dda66fa28ff5`: 113/113 schema expectations matched. The manifest contains 95 expected-valid schema fixtures and all were accepted. |
| Invalid fixtures fail for documented reasons | PASS | The same CI run matched all 18 expected-invalid schema fixtures. Semantic validation also matched 33/33 expectations, including local semantic-invalid and linked negative scenarios. |
| All Milestone 0 edge cases have reproducible fixtures or explicit non-file test representations | PASS | `scripts/validate_edge_case_coverage.py` reports 29/29 frozen edge cases mapped, with 6 registered negative cross-object cases. |
| No schema depends on COROS-specific fields | PASS | No core/common schema property name contains COROS, Garmin, Strava, FIT, or GPX-specific identity semantics. TrackSource uses generic namespace/native-id/media-type provenance. FIT/GPX appear only as descriptive representation examples. |
| Shared representation rules are independently exercised | PASS | 14 common-definition conformance probes cover ID, revision reference, CRS, coordinate bounds/order, UTC timestamp, TrackPosition canonicalization, and SHA-256 representation. |
| Validation layers execute together | PASS | GitHub Actions run `37542808552` completed successfully: Layer A 113/113, Layer B 33/33, coverage 29/29. |

## Source/platform-independence audit

The six core schemas remain portable:

- `Activity` contains only project-local identity plus optional extensions;
- `TrackSource` uses generic `namespace`, `native_id`, `locator`, `media_type`, and optional content hash;
- `CanonicalTrack` depends only on canonical observations, continuity, provenance, and OGC:CRS84;
- `TargetArea`, `SpatialAssessment`, and `TargetSegment` contain no provider-specific fields;
- the three validation runners contain no COROS/Garmin/Strava/FIT/GPX-specific branching.

Result: **PASS**.

## Non-file contract ownership audit

All 13 non-file contract cases contain:

- a frozen assertion;
- an explicit execution milestone;
- a future test shape;
- a reason the invariant is not honestly representable as one Milestone 1 core-entity fixture.

Ownership is:

- Milestone 2 — Deterministic Core: 6 cases;
- Milestone 2 — Deterministic Core / integration fixtures: 1 case;
- Milestone 3 — Persistent Runtime: 3 cases;
- Milestone 5 — Source Adapter Layer: 1 case;
- Milestone 5 with Milestone 3 durability: 1 case;
- Milestone 6 — Resource-Aware Acquisition: 1 case.

No non-file case is missing ownership.

Result: **PASS**.

## Blocking gap — raw FIT/GPX source fixtures are absent

The Milestone 1 work list explicitly requires:

> create synthetic FIT/GPX/track fixtures for edge cases

The repository currently contains **no `.fit` files and no `.gpx` files**.

The existing 113 fixtures are strong schema/domain fixtures, but they start at the serialized core-object layer. They do not provide raw parser-input evidence for the Milestone 2 entry path:

```text
FIT/GPX -> CanonicalTrack
```

This matters because Milestone 2 explicitly starts FIT and GPX ingestion and has an exit criterion requiring equivalent FIT/GPX geometry to normalize compatibly.

Closing Milestone 1 without any raw FIT/GPX fixture would move parser-test design into Milestone 2, contrary to the roadmap's test-first sequencing.

Therefore this is a **Milestone 1 blocker**, even though the four narrow exit-criteria bullets already pass.

## Minimum closure requirement

Milestone 1 does not need a large raw-format corpus before exit. It needs a small, deterministic source-fixture baseline that is sufficient to begin Milestone 2 test-first.

Minimum recommended set:

1. one synthetic GPX and one synthetic FIT representing equivalent route geometry and timestamps;
2. one no-timestamp spatially valid source case where the format permits it, or an explicit format-specific equivalent demonstrating timestamp optionality;
3. one discontinuity/segmentation source case sufficient to test no-edge continuity semantics;
4. one malformed/no-usable-position source case sufficient to test parse failure or non-assessability without producing `outside`;
5. a machine-readable source-fixture expectation manifest describing expected normalization facts without requiring the parser implementation to exist yet.

The raw fixtures must be synthetic and privacy-safe. Real private activity files must not be committed.

## Decision

Milestone 1 remains **ACTIVE**.

The domain/schema/semantic contract work is complete and green, but the milestone should not be marked DONE until the missing synthetic FIT/GPX source-fixture baseline is committed and its expectation manifest is reviewed.

After that addition, rerun:

```text
validate_schema_fixtures.py
validate_semantic_fixtures.py
validate_edge_case_coverage.py
```

and perform a short closure re-review. No additional domain redesign is required.
