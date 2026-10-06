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
| EC-06 | Source | API point stream exists without a file | TrackSource must not require a filesystem file | PASS |
| EC-07 | Track | Valid geometry has no timestamps | Spatially usable CanonicalTrack may still be valid | REVIEW |
| EC-08 | Track | Valid geometry has no altitude | Track remains valid for spatial reconstruction | PASS |
| EC-09 | Track | Source has no usable GPS | No valid spatial CanonicalTrack; must not become outside | PASS |
| EC-10 | Track | GPS has gaps/discontinuities | CanonicalTrack preserves ordered continuity parts without inventing cross-gap geometry | PASS |
| EC-11 | Track | GPS contains extreme jumps/outliers | Raw/normalized observations remain auditable; cleaned/usable geometry is derived | PASS |
| EC-12 | Area | Same track assessed against two areas | Two independent SpatialAssessment objects | PASS |
| EC-13 | Area | Target-area boundary changes version | Re-assess without mutating source/canonical track | PASS |
| EC-14 | Area | Target area is MultiPolygon | v0.1 supports valid Polygon/MultiPolygon and standard holes | PASS |
| EC-15 | Spatial | Track fully inside area | relation=inside; maximal covered continuity parts become TargetSegments | PASS |
| EC-16 | Spatial | Track fully outside area | relation=outside; zero target segments | PASS |
| EC-17 | Spatial | Track enters and exits once | relation=partial; one target segment | PASS |
| EC-18 | Spatial | Track enters target area multiple times | relation=partial; multiple target segments | PASS |
| EC-19 | Spatial | Track starts inside then leaves | Classification uses full track, not start point | PASS |
| EC-20 | Spatial | Track only touches the area boundary | Point touch is outside; positive-length boundary overlap is target coverage | PASS |
| EC-21 | Spatial | Sparse points skip over the area between samples | No geometry is inferred across a continuity break; relevant uncertainty may yield unknown | PASS |
| EC-22 | Segment | Multiple disjoint inside portions | 1 SpatialAssessment : N TargetSegment | PASS |
| EC-23 | Segment | Segment must trace back to source points | TargetSegment retains parent TrackPosition lineage including interpolated endpoints | PASS |
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

**Resolution**

TrackSource is a source-evidence abstraction, not a file abstraction. Local FIT/GPX files are the v0.1 reference sources, but a future API point stream can be represented without changing core TrackSource semantics.

**Model impact**

Likely requires the TrackSource contract to avoid file-only fields.

**Status**

PASS

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

**Resolution**

CanonicalTrack contains one or more ordered continuity parts. No spatial edge, length, target-area intersection, TargetSegment, or network connectivity is inferred across a continuity break. The break does not assert a specific cause.

**Model impact**

Potentially significant CanonicalTrack geometry decision.

**Status**

PASS

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

**Resolution**

CanonicalTrack preserves normalized observation evidence and provenance. Judgment-based cleaning or usable geometry is derived evidence with algorithm/version provenance and must not erase the normalized observations. Exhaustive anomaly taxonomy is deferred.

**Model impact**

Potential distinction between canonical observations and derived cleaned geometry.

**Status**

PASS

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

**Resolution**

v0.1 supports valid Polygon and MultiPolygon geometry, including standard holes. Point, LineString, GeometryCollection, empty geometry, and invalid polygon geometry are rejected by the core contract.

**Model impact**

TargetArea geometry contract must be frozen.

**Status**

PASS

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

**Resolution**

relation=inside when reliable usable geometry is covered by TargetArea and no relevant unresolved uncertainty could change that conclusion. The same maximal-continuous-coverage rule used for partial tracks applies to TargetSegments; a fully covered continuous part produces a full-length TargetSegment.

**Model impact**

TargetSegment creation semantics.

**Status**

PASS

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

**Resolution**

A zero-length point contact with the TargetArea boundary does not create a TargetSegment and does not by itself change outside to partial. Positive-length boundary overlap is valid target-area coverage. No fifth touching relation is added.

**Model impact**

Classification policy, likely not a new entity.

**Status**

PASS

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

**Resolution**

A continuity break never gains a straight-line evidence edge. If an unresolved interval could materially change the TargetArea relation, the assessment may be unknown; an irrelevant break does not automatically make the whole assessment unknown.

**Model impact**

Potential confidence/evidence semantics in SpatialAssessment.

**Status**

PASS

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

**Resolution**

TargetSegment retains lineage to its parent CanonicalTrack through reproducible start and end TrackPosition values. TrackPosition must support locations interpolated between adjacent observations; exact schema field names are deferred.

**Model impact**

TargetSegment contract requires an explicit lineage design.

**Status**

PASS

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

# Evidence plan mapping

Edge cases are resolved through `docs/evidence-plan.md`, `docs/domain-model.md`, and the accepted ADRs. Statuses below reflect completed evidence and domain decisions.

| Edge case(s) | Evidence question | Evidence mode |
|---|---|---|
| EC-07, EC-08, EC-09 | EP-01 — minimum valid CanonicalTrack | REAL PREFERRED |
| EC-10, EC-21 | EP-02 — GPS interruption / continuity | REAL REQUIRED |
| EC-11 | EP-03 — GPS outliers / canonical observation semantics | REAL REQUIRED |
| EC-04, EC-10, EC-27 | EP-04 — FIT vs GPX representation | REAL REQUIRED |
| EC-23 | EP-05 — TargetSegment lineage | REAL REQUIRED + SYNTHETIC |
| EC-14 | EP-06 — TargetArea geometry contract | SYNTHETIC SUFFICIENT |
| EC-15, EC-20 | EP-07 — spatial boundary semantics | SYNTHETIC SUFFICIENT |
| EC-24 | EP-08 — manual decision lifecycle | DESIGN DECISION + workflow validation |

EC-02 and EC-06 remain architectural compatibility questions. They should be resolved when the v0.1 domain model is drafted, with the smallest change consistent with future source-adapter compatibility.

Evidence relevant to speed/pace derivation, especially GPS discontinuities and outliers, should be captured during EP-02 and EP-03 and reused later under `docs/track-metric-overlays.md`. This does not change the Milestone 0 core contract.

---

# Review queue

The current draft has four remaining Milestone 0 questions that require closure or explicit deferral before the contract can be frozen:

1. **Cross-source Activity identity** — v0.1 does not perform implicit approximate merging; decide whether an explicit reconciliation concept is required in the core or deferred as a future extension.
2. **Minimum CanonicalTrack point contract** — close EP-01, especially the no-timestamp spatial-validity case.
3. **Assessment completeness representation** — the requirement to distinguish a determined relation from unresolved/possibly incomplete TargetSegments is accepted, but its concrete contract is not frozen.
4. **Manual decisions** — EC-24 / EP-08 remains a blocking FAIL until algorithmic assessment and human override can be preserved separately.

The following previously open questions are now resolved by accepted domain decisions: TrackSource generality, continuity parts, raw/normalized versus cleaned geometry separation, TargetArea geometry types, fully-inside TargetSegment semantics, boundary-touch semantics, sparse-sampling uncertainty, and TargetSegment lineage.

Quality-detection thresholds, gap-reachability algorithms, and final TrackPosition field names are implementation/schema details and are explicitly deferred rather than blocking the domain model.

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
