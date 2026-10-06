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
| EC-23 — lineage | `valid-partial-crossing`, `repeated-entry`, `starts-inside-leaves`, `boundary-overlap`, `multipolygon`, `polygon-hole`, plus `invalid-target-segment-lineage` | start/end TrackPosition values regenerate target geometry and invalid lineage fails semantically |

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

## Current linked scenario set

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

Negative scenarios:

- `invalid-target-segment-lineage`
- `invalid-assessment-track-reference`

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
- exhaustive target coverage for complete scenarios.

## Remaining Milestone 1 coverage work

This is not yet the complete EC-01 through EC-29 mapping.

Remaining work includes:

- explicit fixture/test representations for the non-spatial identity/source/runtime edge cases outside EC-14 through EC-23;
- additional negative cross-object cases such as out-of-bounds TrackPosition, reversed segment order, wrong TargetArea revision, and spatial-reference mismatch;
- CI-confirmed execution of the complete Layer A and Layer B suites;
- final Milestone 1 exit review.
