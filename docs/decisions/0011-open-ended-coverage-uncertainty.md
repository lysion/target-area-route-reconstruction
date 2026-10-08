# ADR-0011 — Explicit open-ended CoverageUncertainty ranges

**Status:** Accepted — pre-release v0.1.0 representation erratum

**Date:** 2026-10-08

**Checkpoint:** M2D contract unblock

**Evidence:** `tests/test_m2d_contract.py`, `tests/m2d-contract/`; blocker record in `docs/milestone2d-target-segments.md`

## Context

M2A/M2B/M2C accept real leading and trailing source gaps without fabricating positioned observations. A verified M2C proof can be assessable with `unknown + incomplete`, with an unresolved gap `start=None` (leading) or `end=None` (trailing).

The original SpatialAssessment CoverageUncertainty referenced shared `trackRange`, which required two real TrackPositions. That range correctly represents closed observed-parent intervals, but cannot losslessly identify an absent leading/trailing source neighbor. Copying null fails Layer A; omitting fails `required`; repeating the known endpoint yields a schema-valid *false-green point range*, not the original uncertainty. A fabricated sentinel or virtual observation is prohibited.

The blocker was independently confirmed in PR #6. FIT and GPX controls demonstrate the same failure. The issue is a serialized representation mismatch, not a change to the accepted spatial classification or source gap evidence.

## Decision

Keep the six entity identities, original source evidence, TrackPosition, and shared `common.schema.json#/$defs/trackRange` unchanged.

Within `spatial-assessment.schema.json` only, add a dedicated closed-object `$defs.coverageUncertaintyRange` used by `coverage_uncertainties[].affected_track_range`. It requires exactly the fields `start` and `end`, with exactly three mutually exclusive valid variants:

| Variant | start | end | Meaning |
|---|---|---|---|
| bounded | TrackPosition | TrackPosition | Both real parent neighbors exist; positions are ordered |
| leading | null | TrackPosition | No positioned source neighbor on the leading side |
| trailing | TrackPosition | null | No positioned source neighbor on the trailing side |

Both-null, omitted endpoints, and extra properties are invalid.

Null has one narrow meaning: **no positioned source neighbor is available on that side of the gap**. It is not a virtual TrackPosition, a coordinate, positive/negative infinity, a zero-length interval, a movement claim, or a route reconstruction. Leading/trailing are evidence extents, not spatial geometry. Ordinary `trackRange` remains two-ended and non-null everywhere else.

## Semantic and authority checks

Layer A checks the exact three shape variants and rejects both-null, omitted, malformed, and extra-property forms.

Layer B validates every present TrackPosition against its parent; bounded endpoints are ordered. Because a standalone SpatialAssessment does not contain the authoritative M2B/M2C gap record, only an M2D verifier receiving the exact verified M2C proof can establish the full cross-layer claim:

- each unresolved target-relevant gap is represented exactly once;
- the null side and existing neighbor match the same original M2C Gap and M2A provenance;
- resolved or target-irrelevant gaps produce no CoverageUncertainty;
- source vs quality causes and algorithm/evidence provenance remain distinguishable;
- a point-anchor substitute is rejected even if it is schema-valid;
- absent endpoints must never authorize TargetSegment, interpolation, or other geometry.

This distinction is deliberate: schema validity alone does not prove evidence equivalence.

## Schema compatibility/version decision

This is an **explicit pre-release erratum** to the unreleased v0.1.0 schema family, not a silent amendment to a released contract. M2D is still blocked before the first v0.1.0 release, and M3 durable entity persistence has not begun.

For this one correction, **retain `schema_version = 0.1.0`**; do not introduce premature parallel version dispatch or a non-existent migration obligation. Previously valid bounded v0.1.0 instances remain valid, with unchanged meaning. The accepted instance set only expands to include leading/trailing uncertainty that the frozen domain already permitted.

Record the exception in `docs/schema-conventions.md`, amend the runtime packaged schema and validators, preserve the original failure history, and add exact positive/negative contract and production hand-off regression tests.

After the first public release, any change to accepted instance semantics or compatibility must make an explicit new schema-version decision; this erratum must not be cited as a precedent for silent changes.

## Consequences and non-goals

ADR-0004 and ADR-0007 relation/completeness semantics, the M2C proof, quality-gating, parent observation identity, and TargetSegment geometry remain unchanged. This decision neither infers a missing track nor authorizes M2D to change relation, completeness, or observational evidence.

M2D may resume only after the amended contract and regressions pass. Production TargetSegment assembly, exact reciprocal revisions, independent verifier, and mutation tests remain separate M2D obligations.

## Alternatives rejected

- Repeating the known endpoint as both ends: falsely converts a missing prefix/suffix into a positioned point range.
- Widening general `trackRange` nullability: contaminates unrelated parent-lineage semantics.
- Dropping or hiding uncertainty in an extension/provenance: invalidates required core meaning.
- Forging a sentinel observation or out-of-bounds TrackPosition: violates parent evidence.
- Changing M2C relation/completeness or treating the case non-assessable: contradicts the independently verified proof.
- Introducing pre-release version dispatch solely for this compatible correction: unnecessary complexity before any released/persisted v0.1 entity.

## Acceptance evidence

PR #6 records the failing original contract. The follow-up amendment must run Layer A/B fixtures, the production-derived FIT/GPX probes, all accepted M1/M2 regressions, and the isolated wheel check, with no frozen semantic regression.
