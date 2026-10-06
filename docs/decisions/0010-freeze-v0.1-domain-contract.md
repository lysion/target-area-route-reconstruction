# ADR-0010 — Freeze the v0.1 domain contract

**Status:** Accepted  
**Date:** 2026-10-06  
**Decision:** Milestone 0 complete; v0.1 domain contract frozen

## Context

Milestone 0 required an evidence-backed, source-independent domain contract before schema work could begin.

The project has now completed:

- representative real-world evidence review;
- controlled spatial attacks;
- ADR-0001 through ADR-0009;
- EP-01 through EP-08 decisions at the level required for the v0.1 core;
- EC-01 through EC-29 full regression;
- a final contract freeze review.

The final edge-case regression result is:

- PASS: 26
- REVIEW: 0
- FAIL: 0
- DEFERRED: 3

All deferred cases have explicit later-milestone ownership.

The freeze review found no structural model blocker. It clarified two implicit requirements before freeze:

1. geometry participating in assessment must be normalized to a common declared canonical spatial reference;
2. EP-03 freezes the source/normalized/derived-quality provenance boundary, but does not require an exhaustive GPS anomaly taxonomy or mandatory embedded cleaned-geometry schema.

## Decision

The v0.1 domain contract is frozen.

The six spatial-core entities are:

- Activity
- TrackSource
- CanonicalTrack
- TargetArea
- SpatialAssessment
- TargetSegment

The semantic contract recorded in `docs/domain-model.md`, ADR-0001 through ADR-0010, and `docs/contract-freeze-review.md` is the governing baseline for Milestone 1.

Milestone 0 is DONE.

Milestone 1 — Schemas and Fixtures is ACTIVE.

## Frozen invariants

The following may not be changed as an implementation convenience:

- raw source evidence is immutable;
- Activity identity is not inferred from cross-source similarity;
- TrackSource is distinct from CanonicalTrack;
- normalized observations remain auditable;
- no geometry is inferred across continuity breaks;
- timestamps and telemetry are optional for spatial validity;
- TargetArea is versioned and uses valid Polygon/MultiPolygon area geometry;
- SpatialAssessment is Track × TargetArea-version specific;
- missing usable route geometry does not become `outside`;
- relation is `inside | partial | outside | unknown`;
- target-coverage completeness is distinct from relation;
- TargetSegment is maximal, continuous, positive-length, ordered, and parent-traceable;
- TrackPosition supports interpolated boundary positions;
- ManualDecision never mutates algorithmic spatial evidence;
- assessment geometry uses a common declared canonical spatial reference.

## Allowed Milestone 1 decisions

Schema work may decide representation details that do not change the frozen semantics, including:

- field names;
- ID format;
- nullability encoding;
- TrackPosition serialization;
- coordinate-reference identifier serialization;
- CoverageUncertainty shape;
- optional quality annotations;
- fixture file organization.

These are schema decisions, not domain redesign.

## Change control

Any later change to a frozen invariant requires:

1. a new ADR that supersedes or amends the relevant accepted decision;
2. updates to `docs/domain-model.md`;
3. updates to affected edge cases and fixtures;
4. a roadmap update when milestone scope or public contracts change.

A failing implementation test does not by itself justify weakening the frozen contract.

## Consequences

- Milestone 1 can proceed with machine-readable schemas and fixtures.
- Domain ambiguities discovered during schema work must be treated as possible contract defects, not silently resolved in code.
- Milestone 0 evidence remains the design rationale for v0.1.
