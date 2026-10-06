# Edge Cases

This document is the design-time stress test for the v0.1 domain model.

It exists to answer one question:

> Can the current domain model represent real and failure-prone route-reconstruction scenarios without ad-hoc exceptions?

This is a **Milestone 0 design artifact**, not an automated test suite. Cases that survive the domain-model review will later become schemas, fixtures, unit tests, integration tests, and agent evals.

## Status vocabulary

- `PASS` — the current draft model can represent the case without changing the core entity set or violating current invariants.
- `REVIEW` — the case exposes a decision that must be resolved before the domain contract can be frozen.
- `FAIL` — the current model cannot represent the case correctly without a model change.
- `DEFERRED` — the case is valid but belongs primarily to a later milestone; it is retained here because it constrains future compatibility.

A `PASS` does not mean implementation is complete. It only means the **domain model is expressive enough** for the case.

## Current candidate entities

- `Activity`
- `TrackSource`
- `CanonicalTrack`
- `TargetArea`
- `SpatialAssessment`
- `TargetSegment`

## Global invariants under test

The edge cases below are intended to validate these cross-cutting rules:

1. An `Activity` represents a real-world activity event, not a file.
2. An `Activity` may exist without a usable track.
3. An `Activity` may have multiple `TrackSource` objects.
4. Raw track evidence is immutable.
5. A `TrackSource` is distinct from a parsed/normalized `CanonicalTrack`.
6. The deterministic core operates on `CanonicalTrack`, not on FIT-, GPX-, or platform-specific structures.
7. Spatial classification is a relation between a track and a target area; it is not an intrinsic property of the track.
8. `TargetArea` is versioned and provenance-aware.
9. `SpatialAssessment` preserves algorithm/version provenance.
10. Missing or invalid track evidence must never be silently interpreted as `outside`.
11. `TargetSegment` is derived data and must remain traceable to its parent `CanonicalTrack`.
12. A single assessment may produce zero, one, or multiple target segments.
13. Manual judgment must not erase algorithmic evidence.
14. Source-platform limitations and acquisition quotas must not alter the core domain semantics.

---

## Summary matrix

| ID | Category | Scenario | Expected domain behavior | Status |
|---|---|---|---|---|
| EC-01 | Activity | Metadata exists, no track source | Activity remains representable without a track | PASS |
| EC-02 | Activity | Same activity appears from two sources | Duplicate identity must not be assumed solely from matching metadata | REVIEW |
| EC-03 | Activity | Same source activity is imported repeatedly | Re-import must not create a new real-world activity fact | PASS |
| EC-04 | Source | One activity has FIT and GPX sources | One Activity may own multiple TrackSource objects | PASS |
| EC-05 | Source | Source file exists but is corrupted | TrackSource remains evidence; parse failure is explicit | PASS |
| EC-06 | Source | API point stream exists without a file | TrackSource must not require a filesystem file | REVIEW |
| EC-07 | Track | Valid geometry has no timestamps | Spatially usable CanonicalTrack may still be valid | REVIEW |
| EC-08 | Track | Valid geometry has no altitude | Track remains valid for spatial reconstruction | PASS |
| EC-09 | Track | Source has no usable GPS | No valid spatial CanonicalTrack; must not become outside | PASS |
| EC-10 | Track | GPS has gaps/discontinuities | Quality must express discontinuity without inventing continuity | REVIEW |
| EC-11 | Track | GPS contains extreme jumps/outliers | Raw evidence preserved; normalized quality flags the anomaly | REVIEW |
| EC-12 | Area | Same track assessed against two areas | Two independent SpatialAssessment objects | PASS |
| EC-13 | Area | Target-area boundary changes version | Re-assess without mutating source/canonical track | PASS |
| EC-14 | Area | Target area is MultiPolygon | Area model must support disjoint valid components | REVIEW |
| EC-15 | Spatial | Track fully inside area | relation=inside; segment semantics must be defined | REVIEW |
| EC-16 | Spatial | Track fully outside area | relation=outside; zero target segments | PASS |
| EC-17 | Spatial | Track enters and exits once | relation=partial; one target segment | PASS |
| EC-18 | Spatial | Track enters target area multiple times | relation=partial; multiple target segments | PASS |
| EC-19 | Spatial | Track starts inside then leaves | Classification uses full track, not start point | PASS |
| EC-20 | Spatial | Track only touches the area boundary | Boundary-touch semantics must be defined | REVIEW |
| EC-21 | Spatial | Sparse points skip over the area between samples | Sampling limits must not be mistaken for observed entry | REVIEW |
| EC-22 | Segment | Multiple disjoint inside portions | 1 SpatialAssessment : N TargetSegment | PASS |
| EC-23 | Segment | Segment must trace back to source points | Store lineage to canonical point indices/ranges or equivalent | REVIEW |
| EC-24 | Decision | Human override disagrees with algorithm | Preserve algorithmic result and separate manual decision | FAIL |
| EC-25 | Runtime | Same source file imported twice | Content identity should support deduplication/idempotency | DEFERRED |
| EC-26 | Runtime | Acquisition returns URL but file is not durably saved | Must not record source as saved/available | DEFERRED |
| EC-27 | Runtime | Parser version changes | New canonical output must remain traceable to parser version | PASS |
| EC-28 | Objective | Classification complete before all remote tracks acquired | Completion depends on task objective, not total exhaustion | DEFERRED |

---

# Detailed cases

## Activity identity and lifecycle

### EC-01 — Activity metadata exists without track evidence

**Scenario**

An activity is known from a platform activity list or user metadata, but no FIT, GPX, API stream, or other usable track source is currently available.

**Objects involved**

- Activity
- TrackSource
- CanonicalTrack

**Expected domain behavior**

- The `Activity` exists independently.
- Zero `TrackSource` objects is valid.
- Zero `CanonicalTrack` objects is valid.
- Spatial classification cannot be inferred merely from activity metadata.
- The absence of a track does not imply `outside`.

**Invariant under test**

`Activity` is an event, not a track container that must always be populated.

**Model impact**

No core model change required.

**Status**

PASS

---

### EC-02 — The apparent same activity exists in two external sources

**Scenario**

A user imports an activity from two platforms or exports, and both records have very similar start time, distance, duration, and geometry.

**Objects involved**

- Activity
- TrackSource

**Expected domain behavior**

The model must not assume that similar metadata proves identity. It must support either:

- two distinct Activities that later become linked as equivalent; or
- one Activity with source aliases, if identity has been established by an explicit reconciliation process.

**Invariant under test**

Source identifiers are not globally meaningful by themselves, and cross-source deduplication is a decision process rather than a simple field comparison.

**Open question**

Does v0.1 need an explicit cross-source identity-link/reconciliation concept, or can this remain outside the initial contract because v0.1 is local-file only?

**Model impact**

Potentially none for v0.1, but future adapter compatibility may require an identity-link concept.

**Status**

REVIEW

---

### EC-03 — Repeated import of the same source activity

**Scenario**

The same activity/source is imported more than once.

**Objects involved**

- Activity
- TrackSource

**Expected domain behavior**

Repeated ingestion must not create a second real-world Activity merely because ingestion happened twice.

**Invariant under test**

Identity is stable across repeated processing.

**Model impact**

No new core entity required; persistent runtime will enforce idempotency.

**Status**

PASS

---

# Track source and provenance

### EC-04 — One Activity has both FIT and GPX sources

**Scenario**

The same activity is available as an original FIT file and an exported GPX file.

**Objects involved**

- Activity
- TrackSource
- CanonicalTrack

**Expected domain behavior**

- Exactly one Activity may own multiple TrackSource objects.
- Each source preserves its own format, origin, provenance, and content identity.
- Parsing different sources may produce different normalized candidates.
- Source multiplicity must not imply Activity multiplicity.

**Invariant under test**

`Activity 1:N TrackSource`.

**Open question**

Canonical-source preference is a later policy; it must not be hard-coded into Activity identity.

**Model impact**

No core entity change required.

**Status**

PASS

---

### EC-05 — Track source is present but corrupted

**Scenario**

A FIT or GPX file exists and has been durably saved, but the parser cannot decode it.

**Objects involved**

- TrackSource
- CanonicalTrack

**Expected domain behavior**

- The TrackSource remains a valid record of acquired evidence.
- Parse status is failure.
- No valid CanonicalTrack is produced from that parse attempt.
- The activity must not be classified as outside merely because parsing failed.

**Invariant under test**

Acquisition success and parse success are separate states.

**Model impact**

No new core entity required, but parse outcome/provenance must be representable in runtime state.

**Status**

PASS

---

### EC-06 — Track source is an API point stream, not a file

**Scenario**

A provider returns a sequence of track points through an API, with no FIT/GPX file.

**Objects involved**

- TrackSource
- CanonicalTrack

**Expected domain behavior**

The model should still be able to represent the original evidence and its provenance without requiring a filesystem path.

**Invariant under test**

`TrackSource` represents evidence, not specifically a file.

**Open question**

Should `TrackSource` use a generic locator/content descriptor instead of a mandatory file path?

**Model impact**

Likely requires the TrackSource contract to avoid file-only fields.

**Status**

REVIEW

---

# Canonical track completeness and quality

### EC-07 — Spatially valid track without timestamps

**Scenario**

A GPX/GeoJSON-style track has ordered coordinates but no timestamps.

**Objects involved**

- CanonicalTrack

**Expected domain behavior**

- The track can still support spatial classification and clipping.
- Time-based analytics are unavailable.
- Missing timestamps do not automatically invalidate the spatial track.

**Invariant under test**

The minimum valid CanonicalTrack for this project is spatial, not necessarily temporal.

**Open question**

The minimum required point contract must be frozen. Current candidate minimum:

- sequence/order
- longitude
- latitude

**Model impact**

CanonicalTrack schema must make timestamps optional.

**Status**

REVIEW

---

### EC-08 — Track without altitude

**Scenario**

Coordinates and point order are valid, but altitude is absent.

**Objects involved**

- CanonicalTrack

**Expected domain behavior**

The track remains valid for target-area reconstruction.

**Invariant under test**

Altitude is optional for the v0.1 spatial core.

**Model impact**

No core change required.

**Status**

PASS

---

### EC-09 — Source contains no usable GPS coordinates

**Scenario**

A valid activity file contains workout metadata but no usable position records.

**Objects involved**

- TrackSource
- CanonicalTrack
- SpatialAssessment

**Expected domain behavior**

- TrackSource may still be valid evidence.
- No spatially valid CanonicalTrack is available.
- Spatial outcome is unresolved/unknown, not outside.

**Invariant under test**

No evidence of intersection is not equivalent to evidence of non-intersection.

**Model impact**

CanonicalTrack validity and SpatialAssessment `unknown` semantics must be explicit.

**Status**

PASS

---

### EC-10 — GPS track contains a gap

**Scenario**

A track has valid points, then a long period or distance with no recorded GPS, then resumes.

**Objects involved**

- CanonicalTrack
- SpatialAssessment
- TargetSegment

**Expected domain behavior**

The model must preserve the observed points while representing that the path between separated observations is uncertain.

**Invariant under test**

The system must not silently convert missing observations into certain continuous geometry.

**Open questions**

- Does CanonicalTrack require explicit discontinuity markers/parts?
- Should a track be modeled as one ordered series with breaks, or as multiple geometry parts?
- How should spatial clipping behave across a gap?

**Model impact**

Potentially significant CanonicalTrack geometry decision.

**Status**

REVIEW

---

### EC-11 — GPS contains extreme jump/outlier

**Scenario**

A track includes one or more obviously implausible position jumps.

**Objects involved**

- CanonicalTrack

**Expected domain behavior**

- Raw evidence is unchanged.
- Normalization/validation may flag suspicious points.
- Any cleaned/derived geometry must remain distinguishable from the raw parsed observations.

**Invariant under test**

Validation and cleaning must not destroy provenance.

**Open question**

Does v0.1 CanonicalTrack contain quality flags only, or both observed and cleaned point representations?

**Model impact**

Potential distinction between canonical observations and derived cleaned geometry.

**Status**

REVIEW

---

# Target-area semantics

### EC-12 — One track is assessed against multiple target areas

**Scenario**

The same CanonicalTrack is assessed against two different areas.

**Objects involved**

- CanonicalTrack
- TargetArea
- SpatialAssessment

**Expected domain behavior**

Each `Track × TargetArea` pair gets an independent SpatialAssessment.

**Invariant under test**

Spatial relation is not stored as a property of CanonicalTrack.

**Model impact**

No change required.

**Status**

PASS

---

### EC-13 — Target-area boundary is revised

**Scenario**

A target area is updated from v1 to v2 because the working boundary was corrected or changed.

**Objects involved**

- TargetArea
- SpatialAssessment
- CanonicalTrack

**Expected domain behavior**

- CanonicalTrack does not change.
- TargetArea v1 remains identifiable.
- TargetArea v2 is separately versioned.
- New assessments can be computed against v2.
- Historical assessments against v1 remain auditable.

**Invariant under test**

Target definition changes must not mutate source track evidence.

**Model impact**

TargetArea must have stable identity/version semantics.

**Status**

PASS

---

### EC-14 — Target area is disjoint

**Scenario**

A valid target definition contains multiple disconnected polygons.

**Objects involved**

- TargetArea
- SpatialAssessment
- TargetSegment

**Expected domain behavior**

The target area should still be one logical assessment target even when represented by MultiPolygon geometry.

**Invariant under test**

TargetArea is a semantic geographic target, not necessarily one contiguous polygon.

**Open question**

Should v0.1 explicitly support Polygon and MultiPolygon, while rejecting arbitrary GeometryCollection?

**Model impact**

TargetArea geometry contract must be frozen.

**Status**

REVIEW

---

# Spatial relation semantics

### EC-15 — Track fully inside the target area

**Scenario**

Every usable segment of a CanonicalTrack lies inside the target area.

**Objects involved**

- SpatialAssessment
- TargetSegment

**Expected domain behavior**

`relation = inside`.

**Open question**

Should an `inside` assessment create:

- one TargetSegment covering the full CanonicalTrack; or
- zero TargetSegment objects because no clipping was necessary?

For downstream uniformity, one full-length TargetSegment may be preferable, but this must be explicitly decided.

**Model impact**

TargetSegment creation semantics.

**Status**

REVIEW

---

### EC-16 — Track fully outside the target area

**Scenario**

The usable track geometry does not intersect the target area.

**Objects involved**

- SpatialAssessment
- TargetSegment

**Expected domain behavior**

- `relation = outside`
- zero TargetSegment objects

**Invariant under test**

Outside requires usable spatial evidence.

**Model impact**

No change required.

**Status**

PASS

---

### EC-17 — Track enters and exits once

**Scenario**

The track begins outside, enters the target area, and later exits.

**Objects involved**

- SpatialAssessment
- TargetSegment

**Expected domain behavior**

- `relation = partial`
- one TargetSegment
- target segment remains traceable to the CanonicalTrack

**Model impact**

No change required.

**Status**

PASS

---

### EC-18 — Track enters the target area multiple times

**Scenario**

The track enters, exits, and later re-enters the same target area.

**Objects involved**

- SpatialAssessment
- TargetSegment

**Expected domain behavior**

- one SpatialAssessment for the Track × TargetArea pair
- `relation = partial`
- `entry_count > 1`
- multiple TargetSegment objects

**Invariant under test**

`SpatialAssessment 1:N TargetSegment`.

**Model impact**

No change required.

**Status**

PASS

---

### EC-19 — Track starts inside and then leaves

**Scenario**

The activity start position is inside the target area, but most of the route lies outside.

**Objects involved**

- Activity
- CanonicalTrack
- SpatialAssessment

**Expected domain behavior**

Classification is derived from full usable track evidence. Start position alone cannot determine inclusion.

**Invariant under test**

Metadata/start-point heuristics are candidate evidence, not final spatial proof.

**Model impact**

No change required.

**Status**

PASS

---

### EC-20 — Track only touches the boundary

**Scenario**

The track geometrically touches the target boundary but does not clearly travel through the polygon interior.

**Objects involved**

- SpatialAssessment

**Expected domain behavior**

The project must define deterministic boundary semantics rather than leaving the result library-dependent.

**Open questions**

Possible policies include:

- boundary counts as inside;
- only positive interior length counts as inside;
- a pure point-touch is outside but boundary-overlap is partial.

The selected rule must be reflected in fixtures and implementation.

**Model impact**

Classification policy, likely not a new entity.

**Status**

REVIEW

---

### EC-21 — Sparse samples jump across the target area

**Scenario**

Two consecutive GPS points lie on opposite sides of a target area, but no observations exist between them.

A straight line interpolation would intersect the area, but the actual path is unknown.

**Objects involved**

- CanonicalTrack
- SpatialAssessment

**Expected domain behavior**

The model/algorithm must distinguish observed points from inferred connecting geometry.

**Invariant under test**

Spatial certainty must not exceed evidence quality.

**Open questions**

- Is linear interpolation an accepted v0.1 assumption?
- Is there a maximum gap threshold beyond which relation becomes uncertain?
- Does this produce `unknown` or a low-confidence `partial` assessment?

**Model impact**

Potential confidence/evidence semantics in SpatialAssessment.

**Status**

REVIEW

---

# Target-segment lineage

### EC-22 — Multiple disjoint target segments

**Scenario**

A single CanonicalTrack contains several separate portions inside the target area.

**Objects involved**

- SpatialAssessment
- TargetSegment

**Expected domain behavior**

Multiple TargetSegment objects belong to one assessment.

**Invariant under test**

A target segment is not synonymous with an assessment.

**Model impact**

No change required.

**Status**

PASS

---

### EC-23 — Target segment must remain traceable to canonical observations

**Scenario**

A clipped target segment is exported, but later a user needs to know exactly which part of the canonical track produced it.

**Objects involved**

- CanonicalTrack
- TargetSegment

**Expected domain behavior**

TargetSegment must retain lineage to its parent CanonicalTrack.

**Open questions**

Possible lineage representation:

- start/end canonical point indices;
- one or more index ranges;
- references to point IDs;
- geometry plus parent range metadata.

The chosen representation must also handle boundary-interpolated points created by clipping.

**Model impact**

TargetSegment contract requires an explicit lineage design.

**Status**

REVIEW

---

# Manual decisions and auditability

### EC-24 — Human override disagrees with algorithmic assessment

**Scenario**

The algorithm classifies a Track × TargetArea pair as `partial`, but a human reviewer decides that the activity should be treated as outside for the task.

**Objects involved**

- SpatialAssessment
- potential Decision/Override concept

**Expected domain behavior**

The system must preserve:

- the algorithmic result;
- algorithm/version provenance;
- the manual decision;
- the reason;
- decision provenance/time;
- the effective task-facing classification.

The human decision must not overwrite or destroy the algorithmic assessment.

**Invariant under test**

Manual interpretation and algorithmic evidence are separate layers.

**Current model gap**

The six candidate entities do not yet cleanly represent a first-class manual decision.

**Model impact**

A decision is required before domain-contract freeze:

- add a separate `Decision` / `Override` entity; or
- explicitly declare manual decisions outside the v0.1 core while preserving a compatible extension point.

**Status**

FAIL

---

# Runtime and later-milestone compatibility

### EC-25 — Same raw file is imported twice

**Scenario**

The same file is provided repeatedly under the same or different filename.

**Expected domain behavior**

Persistent runtime should use content identity/hash and provenance to avoid duplicate facts.

**Why retained in Milestone 0**

The future runtime requirement constrains TrackSource identity semantics.

**Status**

DEFERRED

---

### EC-26 — Acquisition produces a URL but not durable evidence

**Scenario**

A remote system returns a FIT download URL, but the file is never successfully saved and reopened.

**Expected domain behavior**

The system must not represent the TrackSource as durably available/saved.

**Why retained in Milestone 0**

This constrains TrackSource lifecycle semantics even though remote acquisition is deferred.

**Status**

DEFERRED

---

### EC-27 — Parser version changes canonical output

**Scenario**

A later parser version interprets a source differently or fixes a parsing defect.

**Objects involved**

- TrackSource
- CanonicalTrack

**Expected domain behavior**

Canonical output must retain parser identity/version and remain traceable to the same immutable TrackSource.

**Invariant under test**

Derived normalized data is reproducible and version-aware.

**Model impact**

CanonicalTrack provenance must include parser/version.

**Status**

PASS

---

### EC-28 — Task can finish without acquiring every possible remote track

**Scenario**

A future task objective is network coverage or classification sufficiency, and remaining remote tracks are unlikely to change the answer.

**Expected domain behavior**

Completion belongs to task/runtime policy, not to Activity, TrackSource, or CanonicalTrack identity.

**Why retained in Milestone 0**

This prevents resource-policy concepts from leaking into the core domain model.

**Status**

DEFERRED

---

# Review queue

The current draft has the following unresolved domain questions that must be resolved before Milestone 0 can be marked DONE:

1. **Cross-source Activity identity** — whether v0.1 needs an explicit reconciliation/alias model.
2. **TrackSource generality** — ensure the contract supports non-file source evidence.
3. **Minimum CanonicalTrack point contract** — whether timestamps are optional and what constitutes minimum spatial validity.
4. **Track discontinuities** — how to represent GPS gaps without inventing continuity.
5. **Observed vs cleaned geometry** — whether cleaning belongs inside CanonicalTrack or only in derived data.
6. **TargetArea geometry types** — Polygon/MultiPolygon support and GeometryCollection policy.
7. **Inside TargetSegment semantics** — whether fully-inside tracks generate a full-length TargetSegment.
8. **Boundary-touch semantics** — deterministic classification rules.
9. **Sparse-sampling uncertainty** — interpolation and confidence rules.
10. **TargetSegment lineage** — point/index lineage, including clipped boundary interpolation.
11. **Manual decisions** — the current six-entity model does not cleanly preserve algorithm result plus human override.

The next Milestone 0 work should resolve these items with the smallest domain-model changes possible. Any architectural change should be recorded in `docs/domain-model.md` and, when materially consequential, in an ADR.

# Promotion path

Cases in this document are expected to evolve as follows:

```text
Milestone 0
docs/edge-cases.md
human-readable design specification
        ↓
Milestone 1
tests/fixtures/ + expected outputs
machine-readable contract examples
        ↓
Milestone 2
unit/integration tests
deterministic implementation verification
        ↓
Milestone 4
agent evals
orchestration and decision-behavior verification
```

A case should not be removed simply because implementation becomes inconvenient. If a case is intentionally deferred or rejected, the rationale must be documented.
