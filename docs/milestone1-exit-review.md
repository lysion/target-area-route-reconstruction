# Milestone 1 Exit Review

> Historical record: this PASS was reopened after an independent adversarial audit of commit `141dc092f5a3c7845066156cafd26b3879e99137` found the previous validation oracle insufficient. Current status and corrective work are recorded in [milestone1-remediation.md](milestone1-remediation.md). This document preserves the original decision and evidence.

**Review date:** 2026-10-07  
**Milestone:** 1 — Schemas and Fixtures  
**Result:** **PASS — Milestone 1 complete**

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

## Initial blocking gap — raw FIT/GPX source fixtures

The Milestone 1 work list explicitly requires:

> create synthetic FIT/GPX/track fixtures for edge cases

The initial review found that the repository contained no committed `.fit` or `.gpx` parser-input fixtures.

The existing 113 fixtures are strong schema/domain fixtures, but they start at the serialized core-object layer. They do not provide raw parser-input evidence for the Milestone 2 entry path:

```text
FIT/GPX -> CanonicalTrack
```

This matters because Milestone 2 explicitly starts FIT and GPX ingestion and has an exit criterion requiring equivalent FIT/GPX geometry to normalize compatibly.

Closing Milestone 1 without any raw FIT/GPX fixture would move parser-test design into Milestone 2, contrary to the roadmap's test-first sequencing.

That gap was correctly treated as a Milestone 1 blocker rather than deferred into parser implementation.

## Closure requirement and resolution

The blocker is now closed with a deterministic, privacy-safe baseline under `tests/source-fixtures/`:

1. `equivalent/basic.gpx` and `equivalent/basic.fit` represent equivalent three-point route geometry and identical UTC timestamps;
2. `gpx/no-timestamps.gpx` is spatially valid without timestamps;
3. `gpx/discontinuity.gpx` contains two explicit GPX track segments and therefore establishes two continuity parts with no inferred edge between them;
4. `gpx/malformed.gpx` is intentionally malformed and must fail parsing explicitly;
5. `fit/no-position.fit` is a structurally valid FIT activity with timestamped Record messages but no position fields, so no usable CanonicalTrack or fallback `outside` classification is allowed;
6. `tests/source-fixtures/manifest.json` records SHA-256 values, source-structure expectations, future normalization expectations, and GPX/FIT equivalence requirements.

The files are generated reproducibly by `scripts/generate_synthetic_source_fixtures.py` and validated independently by `scripts/validate_source_fixture_baseline.py`.

No private activity file is committed.

## Closure validation

GitHub Actions run `37544063392` on commit `e158ed13e1b2c7cb837b5e6be5d735c0fcd14c97` executed all Milestone 1 gates successfully:

```text
Schema fixture expectations: 113/113 matched; 0 mismatch(es).
Semantic expectations: 33/33 matched; 0 mismatch(es).
Edge-case coverage: 29/29 frozen cases mapped.
Raw source fixture baseline: 6/6 files verified; 1 equivalence group verified.
```

The raw-source validator checks fixture SHA-256 integrity, GPX validity/segmentation/timestamps, FIT signature/data-size/CRC/Record structure, no-position FIT behavior, and the declared FIT/GPX coordinate/timestamp equivalence baseline.

## Decision

Milestone 1 is **DONE**.

All roadmap exit criteria pass, the source/platform-independence audit passes, the 13 non-file contract cases have explicit later-milestone ownership, and the raw FIT/GPX test-first baseline is now present and executable.

Milestone 2 — Deterministic Core may proceed without changing the frozen v0.1 domain contract.
