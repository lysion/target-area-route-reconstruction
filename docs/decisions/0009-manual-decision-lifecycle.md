# ADR-0009 — Manual decisions are auditable overlays, not mutations of SpatialAssessment

**Status:** Accepted  
**Date:** 2026-10-06  
**Evidence:** EP-08 design decision and workflow validation; EC-24

## Context

An algorithmic SpatialAssessment can be correct as spatial evidence while a human reviewer intentionally chooses a different task-facing interpretation.

Representative workflow:

- algorithmic assessment: `relation = partial`;
- reviewer decision for a specific task: treat the activity as `outside`;
- later audit must still show the original algorithmic result, algorithm/version, reviewer decision, reason, actor, time, and effective task-facing result.

Putting override fields directly inside SpatialAssessment would mix algorithmic evidence with human interpretation and give them the same lifecycle.

## Decision

SpatialAssessment remains immutable algorithmic evidence.

Manual review is represented by a first-class **ManualDecision** audit-layer record linked to an exact SpatialAssessment version.

ManualDecision is not one of the six v0.1 spatial-core entities. It belongs to the review/runtime extension layer because spatial reconstruction is valid without human review and because manual decisions have an independent audit lifecycle.

A ManualDecision must preserve at least:

- stable decision identity;
- exact referenced SpatialAssessment identity/version;
- decision scope or task context;
- task-facing relation chosen by the reviewer;
- reason/rationale;
- actor or decision-source provenance;
- decision timestamp;
- lifecycle provenance such as superseding/revocation linkage when later changed.

A ManualDecision never rewrites:

- SpatialAssessment.relation;
- SpatialAssessment.coverage completeness;
- TargetSegments;
- CanonicalTrack;
- source evidence.

## Effective result

The task-facing effective classification is a derived projection:

~~~text
algorithmic SpatialAssessment
        +
applicable ManualDecision
        ↓
effective task-facing classification
~~~

The projection must expose both the algorithmic result and the manual decision provenance.

Without an applicable ManualDecision, the effective task-facing relation is the algorithmic relation.

The exact precedence/resolution policy for multiple applicable decisions is a runtime concern, but it must be deterministic and auditable.

## Scope boundary

A manual decision may change task-facing interpretation, but it does not fabricate spatial evidence.

If a reviewer possesses new track evidence that changes the spatial facts, that evidence should enter the evidence/normalization pipeline and produce a new algorithmic assessment rather than being encoded as an override.

Likewise, a manual relation override does not delete or synthesize TargetSegments.

## Lifecycle

Manual decisions are append-only audit facts.

A correction, replacement, or revocation must preserve the prior decision and reference it rather than destructively editing history.

This supports an independent lifecycle from SpatialAssessment.

## Consequences

- EC-24 can be represented without changing the six spatial-core entities;
- the deterministic spatial core never needs human-review logic;
- manual review can be added in the persistent-runtime milestone;
- downstream consumers can explicitly choose algorithmic or effective task-facing classification;
- audit can reconstruct why an effective classification differed from the algorithmic result.

## Alternatives rejected

### Override fields inside SpatialAssessment

Rejected because human interpretation would overwrite or contaminate algorithmic evidence and version provenance.

### Mutate relation in place

Rejected because it destroys auditability.

### Treat manual review as an unstructured note

Rejected because it cannot deterministically produce an effective classification or support lifecycle/audit requirements.

### Promote ManualDecision into the six spatial-core entities

Rejected because manual review is optional workflow behavior, not required to represent route geometry or algorithmic spatial assessment.

## Follow-up

Milestone 3 should define persistence for ManualDecision and deterministic effective-result resolution.

Milestone 1 may represent EC-24 as a non-file contract fixture without adding ManualDecision to the six spatial JSON Schemas.
