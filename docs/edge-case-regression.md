# Milestone 0 Edge-Case Regression

**Run date:** 2026-10-06  
**Scope:** EC-01 through EC-29  
**Contract under test:** `docs/domain-model.md` plus ADR-0001 through ADR-0009  
**Result:** PASS

## Purpose

This regression verifies that the current v0.1 domain contract can represent every accepted Milestone 0 edge case without ad-hoc core fields, contradictory lifecycle rules, or source/platform coupling.

The regression is a domain-contract audit. It is not yet an executable test suite; machine-readable fixtures belong to Milestone 1.

## Gate criteria

The regression passes only when:

1. every non-deferred case is expressible by the documented core entities, supporting value concepts, or an explicitly documented extension layer;
2. there are zero blocking `FAIL` cases;
3. there are zero blocking `REVIEW` cases;
4. every `DEFERRED` case has a concrete later-milestone boundary;
5. no accepted case requires weakening provenance, immutability, continuity, or auditability invariants;
6. source platform and file format do not leak into core spatial semantics.

## Result summary

| Status | Count |
|---|---:|
| PASS | 26 |
| REVIEW | 0 |
| FAIL | 0 |
| DEFERRED | 3 |
| Total | 29 |

No regression case requires a seventh spatial-core entity.

The six v0.1 spatial-core entities remain:

- Activity
- TrackSource
- CanonicalTrack
- TargetArea
- SpatialAssessment
- TargetSegment

Supporting concepts used by the accepted contract include ContinuityPart, TrackPosition, CoverageUncertainty, and the audit/runtime extension record ManualDecision.

## Regression findings applied

The case-by-case audit found four ambiguities in wording rather than structural model failures. They were corrected during this regression.

### R-01 — Missing track evidence is not an `unknown` SpatialAssessment

EC-09 previously mixed two states:

- no usable CanonicalTrack exists;
- an existing assessable CanonicalTrack has unresolved spatial evidence.

The contract now distinguishes them.

If no usable positive-length CanonicalTrack exists, no SpatialAssessment is created. Workflow/task state remains unresolved and must never be converted to `outside`.

The `unknown` relation is reserved for an existing assessable CanonicalTrack whose unresolved spatial evidence can change its TargetArea relation.

This clarification is reflected in ADR-0004 and `docs/domain-model.md`.

### R-02 — `outside` requires evidence sufficiency

EC-16 now states explicitly that absence of observed TargetArea intersection is insufficient when a target-relevant unresolved interval remains.

`outside + complete` requires both:

- no reliable positive-length target coverage;
- no unresolved target-relevant uncertainty that could change that conclusion.

### R-03 — Entry count is derived, not a required core field

EC-18 previously included `entry_count > 1` in expected behavior.

The domain only requires multiple ordered TargetSegments. A consumer may derive entry count from the ordered target-coverage intervals; no dedicated stored core field is required.

### R-04 — Sparse sampling and continuity are not synonymous

EC-21 previously risked implying that any pair of observations without intermediate points must be treated as a gap.

The contract now states:

- within one accepted ContinuityPart, adjacent observations may form canonical line geometry under the interpolation rule;
- missing intermediate samples alone do not create a continuity break;
- if a sampling interval is judged too sparse or uncertain to support interpolation, that uncertainty must be represented before assessment as a continuity break or equivalent unresolved quality interval;
- the threshold for that judgment is an implementation/quality rule, not a domain identity rule.

This clarification is reflected in ADR-0001 and `docs/domain-model.md`.

---

## Case-by-case audit

| Case | Final status | Contract basis | Regression conclusion |
|---|---|---|---|
| EC-01 | PASS | Activity lifecycle | Activity may exist with zero TrackSources and zero CanonicalTracks; metadata alone cannot create spatial classification. |
| EC-02 | PASS | ADR-0008 | Cross-source similarity never proves identity. Explicitly known same-event sources may share one Activity; reconciliation is future auditable runtime/adapter behavior. |
| EC-03 | PASS | Activity stable local identity; runtime boundary | Re-ingestion does not redefine the real-world Activity. Enforcement of repeated-ingestion idempotency belongs to persistent runtime. |
| EC-04 | PASS | Activity 1:N TrackSource; ADR-0002 | FIT and GPX may be separate source evidence for one explicitly known Activity; source differences do not imply Activity multiplicity. |
| EC-05 | PASS | TrackSource lifecycle | Corrupted durable source evidence remains a TrackSource; parse failure produces no CanonicalTrack and cannot imply outside. |
| EC-06 | PASS | TrackSource abstraction | TrackSource represents provenance-bearing evidence, not specifically a filesystem file; future API point streams fit without core redesign. |
| EC-07 | PASS | ADR-0006 | Ordered usable coordinates are sufficient for spatial reconstruction; timestamps are optional capabilities. |
| EC-08 | PASS | ADR-0006 | Altitude is optional and does not affect spatial validity. |
| EC-09 | PASS | ADR-0004 assessment precondition | No usable CanonicalTrack means no SpatialAssessment. Workflow remains unresolved and outside is never synthesized. |
| EC-10 | PASS | ADR-0001 | One logical CanonicalTrack may contain ordered continuity parts; no geometry is inferred across breaks. |
| EC-11 | PASS | ADR-0002 | Normalized observations remain auditable; judgment-based cleaning/usable geometry is separate derived evidence with provenance. |
| EC-12 | PASS | SpatialAssessment identity | Relation belongs to CanonicalTrack × TargetArea version, so one track can have independent assessments against multiple areas. |
| EC-13 | PASS | ADR-0003 | TargetArea version changes trigger new derived assessments without mutating TrackSource or CanonicalTrack evidence. |
| EC-14 | PASS | ADR-0003 | Valid Polygon/MultiPolygon with standard holes is sufficient; disconnected components remain one semantic TargetArea. |
| EC-15 | PASS | ADR-0004, ADR-0005, ADR-0007 | Fully covered usable geometry yields inside; maximal covered continuity parts become TargetSegments; completeness remains independently expressible. |
| EC-16 | PASS | ADR-0004, ADR-0007 | Outside requires no positive-length target coverage and no target-relevant unresolved uncertainty; TargetSegments are empty. |
| EC-17 | PASS | ADR-0004, ADR-0005 | One observed enter/exit interval yields partial and one traceable TargetSegment. |
| EC-18 | PASS | ADR-0005 | Repeated entry yields multiple ordered TargetSegments under one SpatialAssessment; entry count need not be a stored core field. |
| EC-19 | PASS | ADR-0004 | Full usable track evidence determines relation; start point is not final proof. |
| EC-20 | PASS | ADR-0004 | Zero-length point touch is not route traversal; positive-length boundary overlap is target coverage; no fifth relation is needed. |
| EC-21 | PASS | ADR-0001, ADR-0004 | Accepted within-part interpolation is distinct from unresolved sparse intervals; unresolved intervals do not gain invented chords and may produce unknown. |
| EC-22 | PASS | ADR-0005 | Multiple disjoint covered intervals are multiple TargetSegments owned by one assessment. |
| EC-23 | PASS | ADR-0005 | TargetSegment lineage is expressed by reproducible parent TrackPositions, including interpolated endpoints. |
| EC-24 | PASS | ADR-0009 | ManualDecision is an auditable review/runtime overlay; algorithmic SpatialAssessment is immutable and effective classification is derived. |
| EC-25 | DEFERRED | Milestone 3 | Content hashing, duplicate prevention, and idempotent repeated-file ingestion belong to Persistent Runtime. |
| EC-26 | DEFERRED | Milestone 5 with Milestone 3 durability support | Remote acquisition belongs to Source Adapter Layer; a URL/locator alone is not durable saved evidence. |
| EC-27 | PASS | TrackSource/CanonicalTrack provenance; ADR-0002 | Canonical derivations retain parser/normalizer identity and version and remain traceable to immutable source evidence. |
| EC-28 | DEFERRED | Milestone 6 | Objective-aware stopping and constrained acquisition belong to Resource-Aware Acquisition and must not alter core entity identity. |
| EC-29 | PASS | ADR-0007 | Relation certainty and target-coverage completeness are independent; partial/inside can be incomplete while known TargetSegments remain valid. |

---

## Cross-cutting invariant regression

### Evidence immutability

PASS.

No accepted case requires mutation of raw TrackSource evidence, normalized observations, or historical algorithmic results.

### Source/derived separation

PASS.

The contract consistently separates:

`TrackSource → CanonicalTrack → quality/usable geometry → SpatialAssessment/TargetSegment`

ManualDecision is a review/runtime overlay and does not alter this evidence chain.

### Continuity

PASS.

No accepted case requires cross-gap geometry. Within-part interpolation is explicitly distinguished from an unresolved continuity interval.

### TargetArea versioning

PASS.

All target-derived results are version-relative and recomputable without source mutation.

### Spatial relation semantics

PASS.

The four-state relation remains sufficient:

- inside
- partial
- outside
- unknown

Boundary contact, completeness, and manual task-facing interpretation do not require additional relation states.

### Coverage completeness

PASS.

`complete / incomplete` captures whether the known TargetSegment set is exhaustive for the specific TargetArea without conflating it with relation certainty.

### TargetSegment lineage

PASS.

The TrackPosition requirement is sufficient for real clipping, repeated entry, MultiPolygon, holes, and interpolated boundary crossings.

### Manual audit lifecycle

PASS.

ManualDecision provides a first-class auditable extension without expanding the six spatial-core entities.

### Platform/format independence

PASS.

No accepted domain rule depends on COROS, FIT, GPX, a GIS library predicate, an acquisition quota, or a filesystem path.

---

## Deferred-case boundary audit

### EC-25 — duplicate raw-file ingestion

**Boundary:** Milestone 3 — Persistent Runtime.

Required later capabilities include content identity/hash, idempotent ingestion, and persisted provenance.

### EC-26 — remote URL without durable evidence

**Boundary:** Milestone 5 — Source Adapter Layer, using persistence semantics established in Milestone 3.

Remote locator issuance is not acquisition success. A source is not durably available until evidence has been persisted and validated according to runtime policy.

### EC-28 — objective-aware completion before source exhaustion

**Boundary:** Milestone 6 — Resource-Aware Acquisition.

Stopping rules, quota/cost/latency optimization, and marginal-information-value policy remain task/runtime concerns rather than domain identity.

All three DEFERRED cases have explicit later-milestone ownership and do not block v0.1 schema definition.

---

## Schema-readiness observations

The regression found no remaining domain ambiguity that requires a core-entity redesign before Milestone 1.

The following details are intentionally not frozen by Milestone 0 and should be decided during schema/implementation work without changing the accepted domain semantics:

- exact JSON field names and index base for TrackPosition;
- exact CoverageUncertainty serialization;
- quality thresholds for continuity-break detection;
- algorithms for proving a gap target-irrelevant;
- persisted representation of cleaned/usable geometry;
- cross-source reconciliation persistence model;
- ManualDecision persistence and multiple-decision precedence.

These are implementation or extension contracts, not unresolved v0.1 spatial-domain questions.

## Regression conclusion

**Milestone 0 edge-case regression: PASS.**

There are:

- zero blocking FAIL cases;
- zero blocking REVIEW cases;
- three explicitly bounded DEFERRED cases;
- no required ad-hoc spatial-core entity or field.

The domain contract is ready for the final Milestone 0 freeze review.
