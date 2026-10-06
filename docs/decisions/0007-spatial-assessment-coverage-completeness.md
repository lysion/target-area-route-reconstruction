# ADR-0007 — SpatialAssessment coverage completeness

**Status:** Accepted  
**Date:** 2026-10-06  
**Evidence:** EP-02, EP-05, EP-07; controlled target-area gap attacks derived from the clean RC-04 baseline

## Context

The four-state spatial relation does not answer whether all target-area route coverage has been reconstructed.

Controlled cases established several distinct states:

- a clean observed crossing can be `partial` with all target coverage known;
- a track can already be provably `partial` while another unresolved gap could hide an additional target-area segment;
- a track can remain provably `inside` while an unobserved interval inside the area leaves the exact route geometry unreconstructed;
- an `outside` result can remain complete when all unresolved gaps are proven unable to reach the TargetArea;
- an unresolved gap that could change an otherwise outside result requires `unknown`.

Therefore relation certainty and reconstruction completeness are separate domain dimensions.

## Decision

SpatialAssessment has a first-class **target-coverage completeness** dimension in addition to `relation`.

The semantic values are:

- `complete`
- `incomplete`

A representative schema field name is `coverage_completeness`. Exact serialization remains a Milestone 1 schema concern, but the two-state domain semantics are frozen.

### complete

Target-area reconstruction is `complete` when the available evidence contains no unresolved target-relevant uncertainty that could change the existence, number, extent, continuity, geometry, or lineage of positive-length TargetArea-covered route portions.

Completeness is target-relative. A CanonicalTrack may contain uncertainty elsewhere and still be complete for a specific TargetArea when that uncertainty cannot affect target coverage.

### incomplete

Target-area reconstruction is `incomplete` when at least one unresolved target-relevant uncertainty could change the reconstructed TargetArea coverage, even if the core relation is already determined.

Known TargetSegments remain valid evidence-backed results, but their collection must not be presented as exhaustive.

## Relation and completeness

The dimensions are intentionally separate.

| Relation | Completeness | Meaning |
|---|---|---|
| `partial` | `complete` | inside and outside coverage are established and no additional target coverage remains unresolved |
| `partial` | `incomplete` | partial is already proven, but additional or altered target coverage may remain hidden |
| `inside` | `complete` | all reconstructable route coverage is known to remain inside |
| `inside` | `incomplete` | inside is proven, but exact target-area route coverage remains partially unobserved |
| `outside` | `complete` | no positive-length target coverage exists and no target-relevant uncertainty remains |
| `unknown` | `incomplete` | evidence is insufficient to determine the relation because unresolved target-relevant uncertainty remains |

Under the current v0.1 relation semantics:

- `unknown` implies `incomplete`;
- `outside` implies `complete`;
- `inside` and `partial` may be either complete or incomplete.

## Auditability requirement

An `incomplete` assessment must be explainable.

The assessment must retain or reference one or more unresolved target-relevant uncertainty records sufficient to identify:

- the affected CanonicalTrack interval, continuity break, or quality issue;
- why the uncertainty is relevant to the TargetArea;
- the provenance of the evidence/algorithm that left it unresolved.

This supporting uncertainty information is not a new core entity. Its exact schema is deferred to Milestone 1.

Resolved or target-irrelevant uncertainties may remain diagnostic provenance but do not force `incomplete`.

## Consequences

- `relation != unknown` must never be used as a proxy for complete reconstruction.
- A `partial, incomplete` assessment may expose known TargetSegments while explicitly stating that more coverage may exist.
- A gap elsewhere in the activity does not automatically make coverage incomplete for every TargetArea.
- Downstream route-network aggregation must be able to distinguish exhaustive TargetSegment sets from known-but-incomplete sets.
- Confidence scores are not part of the v0.1 completeness contract.

## Alternatives rejected

### One relation enum only

Rejected because a determined `partial` relation can coexist with missing TargetSegments.

### Treat every activity with a gap as incomplete for every TargetArea

Rejected because completeness is target-relative, not a global track-quality flag.

### Numeric confidence score

Rejected because a score such as 0.7 or 0.9 does not state whether the known TargetSegment set is exhaustive and does not provide deterministic domain semantics.

### Three or more completeness states

Rejected for v0.1 because current evidence requires only the distinction between exhaustive reconstruction and unresolved target-relevant reconstruction.

## Follow-up

Milestone 1 fixtures must include at least:

- `partial + complete`;
- `partial + incomplete`;
- `inside + incomplete`;
- `outside + complete`;
- `unknown + incomplete`.

The SpatialAssessment schema must also preserve enough uncertainty provenance to explain every `incomplete` result.
