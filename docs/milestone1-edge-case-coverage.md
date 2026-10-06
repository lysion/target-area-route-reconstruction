# Milestone 1 Edge-Case Coverage

**Status:** COMPLETE MAPPING — EC-01 through EC-29 all have an explicit representation  
**Machine-readable source:** `tests/edge-case-coverage.json`

Milestone 1 requires every frozen Milestone 0 edge case to have one of three representation types:

1. **fixture** — a standalone schema/semantic fixture;
2. **linked semantic scenario** — a multi-entity graph validated by `scripts/validate_semantic_fixtures.py`;
3. **explicit non-file contract case** — a machine-readable future test contract for lifecycle/runtime behavior that cannot honestly be proven by a standalone core entity fixture during Milestone 1.

The mapping itself is validated by:

```bash
python scripts/validate_edge_case_coverage.py
```

## EC-01 through EC-13

| Edge case | Representation | Primary artifact |
|---|---|---|
| EC-01 | fixture | `activity/valid-minimal.json` |
| EC-02 | non-file contract case | cross-source identity/reconciliation test contract |
| EC-03 | non-file contract case | persistent idempotency test contract |
| EC-04 | non-file graph/integration contract | one Activity → multiple TrackSources |
| EC-05 | fixture + non-file execution contract | corrupted TrackSource fixture + parser-failure contract |
| EC-06 | fixture | non-file/API-stream TrackSource fixture |
| EC-07 | fixture | coordinate-only CanonicalTrack |
| EC-08 | fixture | coordinate-only/no-altitude CanonicalTrack |
| EC-09 | fixture + non-file absence contract | non-assessable canonical evidence + no-assessment parser contract |
| EC-10 | fixture + linked scenario | multipart CanonicalTrack + `relevant-gap-unknown` |
| EC-11 | non-file execution contract | quality-cleaning provenance contract |
| EC-12 | non-file multi-assessment contract + negative linked reference scenario | exact TargetArea revision reference |
| EC-13 | non-file revision-lifecycle contract + negative linked reference scenario | immutable CanonicalTrack across TargetArea revisions |

## EC-14 through EC-23

These remain covered by the linked scenarios documented in `docs/milestone1-linked-scenario-coverage.md`.

Coverage includes:

- MultiPolygon and polygon holes;
- fully inside/outside;
- single and repeated entry;
- starts-inside departure;
- point touch and positive-length boundary overlap;
- relevant continuity gaps;
- multiple TargetSegments;
- interpolated lineage.

## EC-24 through EC-29

| Edge case | Representation | Primary artifact |
|---|---|---|
| EC-24 | non-file contract case | ManualDecision audit/runtime lifecycle |
| EC-25 | non-file contract case | Milestone 3 content-hash/idempotency behavior |
| EC-26 | non-file contract case | Milestone 5 acquisition + Milestone 3 durability behavior |
| EC-27 | non-file comparative execution contract | same TrackSource, different normalizer/parser revisions |
| EC-28 | non-file contract case | Milestone 6 objective-aware stopping |
| EC-29 | schema fixture + linked semantic scenario | `valid-partial-incomplete.json` + `partial-incomplete-gap` |

## Explicit non-file test contracts

The machine-readable non-file representations live in:

- `tests/nonfile-contract-cases.json`

Each case records:

- frozen edge-case ID;
- assertion to preserve;
- execution milestone;
- expected future test shape;
- why a standalone v0.1 entity fixture would be misleading or insufficient.

This is deliberate. Milestone 1 does not fabricate persistence, adapter, acquisition, reconciliation, or ManualDecision schemas merely to make every edge case look like a JSON entity fixture.

## Negative cross-object cases

The current negative set includes:

| Case | Layer | Assertion |
|---|---|---|
| invalid TargetSegment lineage | semantic | geometry cannot disagree with TrackPosition lineage |
| out-of-bounds TrackPosition | semantic | parent CanonicalTrack indices must exist |
| wrong CanonicalTrack revision | semantic | SpatialAssessment must reference the exact linked track revision |
| wrong TargetArea revision | semantic | SpatialAssessment must reference the exact linked area revision |
| reversed TargetSegment reference order | semantic | assessment refs must follow parent-track segment order |
| spatial-reference mismatch | schema | v0.1 fixes canonical geometry to OGC:CRS84, so mismatch is rejected before Layer B |

The spatial-reference case is intentionally a Layer A negative rather than a schema-valid Layer B scenario: under the frozen v0.1 schema, a core geometry object declaring another CRS is structurally invalid, so a schema-valid CRS mismatch cannot honestly be constructed.

## Current coverage counts

At the time this mapping was completed:

- frozen edge cases mapped: **29 / 29**;
- fixture manifest entries: **113**;
- linked semantic scenarios: **16**;
- explicit non-file contract cases: **13**;
- registered negative cross-object cases: **6**;
- independent common-definition conformance fixtures: **14**.

These counts are implementation status, not a claim that CI has already passed every current case. The repository runners/CI remain the authoritative execution result.

## Milestone 1 implication

The exit criterion

> all Milestone 0 edge cases have reproducible fixtures or explicit non-file test representations

is now structurally satisfied.

Remaining Milestone 1 work is validation conformance: run/stabilize the Layer A, Layer B, and coverage-map runners; add any missing common-definition conformance tests; then perform the Milestone 1 exit review.
