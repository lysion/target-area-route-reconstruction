# Milestone 1 Linked Semantic Scenario Coverage

**Status:** active Milestone 1 coverage map  
**Validation layer:** `scripts/validate_semantic_fixtures.py`

This document records which frozen edge cases are now represented by linked semantic scenarios rather than isolated object fixtures.

## Covered spatial edge cases

| Edge case | Linked scenario | What is exercised |
|---|---|---|
| EC-14 — disjoint TargetArea / holes | `multipolygon`, `polygon-hole` | one semantic TargetArea may be disconnected or contain holes; both can produce multiple target-covered intervals |
| EC-15 — fully inside | `fully-inside` | complete inside relation and one full-length TargetSegment |
| EC-16 — fully outside | `fully-outside` | outside + complete with zero TargetSegments |
| EC-17 — single entry/exit | `valid-partial-crossing` | one partial assessment and one interpolated, traceable TargetSegment |
| EC-18 — repeated entry | `repeated-entry` | one assessment with multiple ordered TargetSegments |
| EC-19 — starts inside then leaves | `starts-inside-leaves` | start position alone does not determine final relation; full route yields partial |
| EC-20 — boundary semantics | `point-touch`, `boundary-overlap` | point contact stays outside with zero segment; positive-length boundary overlap counts as target coverage |
| EC-21 — target-relevant continuity gap | `relevant-gap-unknown` | no chord is created across continuity parts; unresolved target relevance remains unknown + incomplete |
| EC-22 — multiple disjoint target segments | `repeated-entry`, `multipolygon`, `polygon-hole` | multiple TargetSegments remain children of one SpatialAssessment |
| EC-23 — lineage | `valid-partial-crossing`, `repeated-entry`, `starts-inside-leaves`, `boundary-overlap`, `multipolygon`, `polygon-hole`, plus lineage/order/bounds negatives | start/end TrackPosition values regenerate target geometry; invalid lineage, out-of-bounds positions, and reversed refs fail semantically |
| EC-29 — determined relation with incomplete coverage | `partial-incomplete-gap`, `audit-inside_incomplete_world` | partial remains proven despite a gap; a CRS84-domain target proves inside without circular reliance on the submitted relation |

## Scenario chain

Every positive linked scenario uses the same full object chain:

```text
Activity
  ↓
TrackSource
  ↓
CanonicalTrack
  ↓
TargetArea
  ↓
SpatialAssessment
  ↓
TargetSegment[]
```

The semantic runner checks identity/revision references across that chain in addition to local geometry semantics.

## Original linked scenario set (retained)

Positive scenarios:

- `valid-partial-crossing`
- `fully-inside`
- `fully-outside`
- `repeated-entry`
- `starts-inside-leaves`
- `point-touch`
- `boundary-overlap`
- `relevant-gap-unknown`
- `multipolygon`
- `polygon-hole`
- `partial-incomplete-gap`

Negative semantic scenarios:

- `invalid-target-segment-lineage`
- `invalid-target-segment-out-of-bounds`
- `invalid-assessment-track-reference`
- `invalid-assessment-area-reference`
- `invalid-target-segment-reference-order`

A spatial-reference mismatch is covered as a Layer A negative fixture because the v0.1 schema fixes canonical geometry to `OGC:CRS84`; a schema-valid mismatched CRS cannot exist.

The linked scenario manifest is:

- `tests/fixtures/semantic-scenarios.json`

All individual component files are also registered in:

- `tests/fixtures/manifest.json`

so Layer A JSON Schema validation runs before Layer B semantic validation.

## Semantic assertions exercised

The scenario set now exercises:

- complete `inside`, `partial`, and `outside`;
- `unknown + incomplete`;
- zero, one, and multiple TargetSegments;
- interpolated TrackPosition boundaries;
- full-length TargetSegment lineage;
- parent-track ordering;
- exact revision references;
- positive-length boundary coverage;
- zero-length point touch;
- Polygon holes;
- MultiPolygon components;
- continuity-break no-edge semantics;
- target-relevant CoverageUncertainty;
- maximal observed coverage for both complete and incomplete scenarios.

## Adversarial additions

The same formal manifests now register 23 additional scenarios, indexed in `tests/adversarial/manifest.json`. They exercise omitted A→B→A traversal, repeated entry over identical geometry, identical geometry in separate parts (both complete and incomplete omission attacks), reordered loops, shortened known incomplete segments, contradictory incomplete relations, diagonal roundoff, length underflow, repeated coordinates, tiny interval truncation, bounds/order/cross-part negatives, and positive controls. There are 39 linked scenarios in total, all with mandatory Layer A validation. Every negative names a stable issue code.

`tests/test_spatial_oracle.py` injects an edge between adjacent parts and requires the positive multipart control to stop validating. `tests/test_contract_gates.py` separately attacks the runners' reason expectations, schema registrations, strict JSON readers and coverage declarations. These tests add behavioral evidence beyond counting mapped EC IDs.

The fixture oracle's usable-evidence assumptions and unsupported gap-bound proofs are explicit in [the quality-layer contract](quality-layer-interface.md). General local-area inside/incomplete needs independently justified gap constraints; a submitted relation or prose uncertainty is insufficient.

## Relationship to complete edge-case mapping

The full EC-01 through EC-29 mapping is now recorded in:

- `tests/edge-case-coverage.json`
- `tests/nonfile-contract-cases.json`
- `docs/milestone1-edge-case-coverage.md`

This document remains focused on linked spatial scenarios.

Current readiness is recorded in [the fresh re-exit review](milestone1-re-exit-review.md). The original exit review remains historical evidence.
