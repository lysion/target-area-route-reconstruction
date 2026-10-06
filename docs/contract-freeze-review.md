# Milestone 0 Contract Freeze Review

**Review date:** 2026-10-06  
**Scope:** v0.1 domain contract  
**Inputs reviewed:** `docs/domain-model.md`, ADR-0001 through ADR-0009, `docs/evidence-plan.md`, `docs/real-world-cases.md`, `docs/edge-cases.md`, `docs/edge-case-regression.md`, `docs/track-metric-overlays.md`, `ROADMAP.md`, and `README.md`  
**Final result:** PASS — v0.1 domain contract is ready to freeze

## Review standard

The freeze review applies the Milestone 0 exit criteria from `ROADMAP.md` and asks whether any unresolved ambiguity would force Milestone 1 schemas to invent domain semantics that should have been decided earlier.

A freeze does not mean every implementation detail is known. It means the v0.1 domain boundaries, invariants, identities, relations, provenance requirements, and extension boundaries are stable enough to encode without redesign.

## Exit-criteria audit

| Exit criterion | Result | Review finding |
|---|---|---|
| Required edge cases are representable without ad-hoc core fields | PASS | EC-01 through EC-29 regression passes. ManualDecision is explicitly an audit/runtime extension rather than an ad-hoc spatial-core field. |
| Zero FAIL cases | PASS | 0 FAIL. |
| Zero blocking REVIEW cases | PASS | 0 REVIEW. |
| Future concerns are explicitly DEFERRED | PASS | EC-25 → Milestone 3; EC-26 → Milestone 5 with Milestone 3 durability semantics; EC-28 → Milestone 6. |
| Core entities have stable identity and ownership boundaries | PASS | Six spatial-core entities are stable: Activity, TrackSource, CanonicalTrack, TargetArea, SpatialAssessment, TargetSegment. Supporting concepts have explicit owners. |
| Model is source-platform independent | PASS | No core identity or relation depends on COROS, Garmin, Strava, or another provider. |
| Model is track-format independent | PASS | FIT/GPX differences are isolated in TrackSource and normalization provenance. |
| TargetArea version changes do not mutate raw evidence | PASS | TargetArea versioning and recomputation semantics are explicit in ADR-0003 and domain model. |
| Accepted decisions are reflected in domain model | PASS | ADR-0001 through ADR-0009 semantics are represented in the domain contract. |
| No unresolved ambiguity blocks schema definition | PASS after clarification | Spatial reference compatibility and quality-controlled-geometry scope were made explicit during this review. |
| Full edge-case regression completed | PASS | 26 PASS, 0 REVIEW, 0 FAIL, 3 bounded DEFERRED. |

## Freeze-review clarifications

The review found no structural model failure, but it identified two places where implicit assumptions should not be left for Milestone 1 to guess.

### FR-01 — Canonical spatial reference compatibility must be explicit

Before the review, the domain model referred to a “canonical spatial reference” but did not explicitly state the compatibility precondition for Track × TargetArea operations.

The contract now requires:

- CanonicalTrack coordinates to have an unambiguous canonical spatial reference;
- TargetArea geometry to be expressed in the same canonical spatial reference before assessment;
- source-native coordinate encodings to remain provenance;
- any reprojection/normalization to be deterministic and provenance-aware.

The freeze does **not** require Milestone 0 to choose a particular serialization field name or GIS library API. Milestone 1 must encode an unambiguous representation.

### FR-02 — Quality provenance is frozen; universal cleaning schema is not

EP-03 established the necessary domain boundary:

- source/normalized observations remain auditable;
- judgment-based cleaned or usable geometry is derived output;
- derived quality decisions retain algorithm/version provenance.

The review confirms that an exhaustive GPS anomaly taxonomy and a universal cleaned-geometry representation are **not** prerequisites for freezing the core domain.

Therefore:

- cleaned/usable geometry is not a mandatory embedded field of the core CanonicalTrack contract;
- Milestone 1 may define optional quality annotations or derived-result contracts;
- Milestone 2 owns concrete validation/cleaning algorithms and thresholds.

This removes the risk that “EP-03 is not exhaustive” could be misread as a schema blocker.

## Entity freeze

The v0.1 spatial-core entity set is frozen as:

1. Activity
2. TrackSource
3. CanonicalTrack
4. TargetArea
5. SpatialAssessment
6. TargetSegment

The following are supporting/extension concepts, not additional spatial-core aggregate roots:

- ContinuityPart — owned by CanonicalTrack;
- TrackPosition — value concept for parent-track positions and lineage;
- CoverageUncertainty — owned by SpatialAssessment;
- ManualDecision — first-class audit/runtime extension record linked to SpatialAssessment.

Changing this boundary after freeze requires a superseding ADR and affected fixture/schema updates.

## Semantic freeze

The following semantics are frozen for v0.1:

- raw source evidence is immutable;
- TrackSource and CanonicalTrack are distinct provenance layers;
- CanonicalTrack preserves ordered observations and explicit continuity;
- no geometry is inferred across continuity breaks;
- ordered usable coordinates are sufficient for the minimum spatial contract; timestamps and telemetry are optional capabilities;
- TargetArea supports valid Polygon/MultiPolygon geometry with standard holes and is versioned;
- spatial assessment is relative to CanonicalTrack × TargetArea version;
- no SpatialAssessment is created when no usable positive-length CanonicalTrack exists;
- relation values are `inside | partial | outside | unknown`;
- zero-length point contact is not traversal; positive-length boundary overlap is target coverage;
- target-coverage completeness is `complete | incomplete` and is distinct from relation;
- TargetSegment is a maximal continuous positive-length covered interval with parent-track lineage;
- TrackPosition must support boundary positions between recorded observations;
- cross-source Activity identity is explicit and never similarity-implied;
- ManualDecision never mutates algorithmic SpatialAssessment;
- geometry participating in assessment must share a common declared canonical spatial reference.

## Intentionally unfrozen implementation details

The following may be decided in later milestones without reopening the domain freeze, provided they preserve the frozen semantics:

- JSON field names and nullability representation;
- ID encoding and storage technology;
- TrackPosition index base and numeric serialization;
- exact CRS field/identifier serialization and reprojection implementation;
- quality thresholds for continuity-break or outlier detection;
- gap-reachability algorithm used to prove target irrelevance;
- optional quality annotation / cleaned-geometry representation;
- CoverageUncertainty serialization details;
- cross-source reconciliation persistence model;
- ManualDecision persistence and precedence rules;
- GIS library choice;
- map rendering and speed/pace visualization details.

## Schema-readiness conclusion

Milestone 1 can now define schemas without making new domain decisions about:

- what an Activity is;
- what counts as source evidence versus normalized evidence;
- minimum spatial validity;
- continuity;
- TargetArea geometry and versioning;
- relation states;
- completeness;
- TargetSegment multiplicity and lineage;
- cross-source identity;
- manual override lifecycle.

If schema work encounters a need to change one of those semantics, that is a contract change and requires a superseding ADR rather than an implementation shortcut.

## Freeze decision

**PASS.**

Milestone 0 satisfies its exit criteria after applying FR-01 and FR-02.

The v0.1 domain contract may be frozen, Milestone 0 may be marked DONE, and Milestone 1 — Schemas and Fixtures may become ACTIVE.
