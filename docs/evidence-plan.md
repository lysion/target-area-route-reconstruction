# Evidence Plan

This document defines how Milestone 0 will use real-world and synthetic evidence to resolve the open questions in `docs/edge-cases.md`.

The purpose is not to collect many activity files. The purpose is to obtain the **minimum evidence needed to distinguish competing domain-model designs** before the v0.1 contract is frozen.

## Governing rule

Every blocking design question follows the same sequence:

```text
Design question
  ↓
Candidate models
  ↓
Required evidence
  ↓
Observed facts
  ↓
Candidate comparison
  ↓
Synthetic attack
  ↓
Decision
  ↓
Full edge-case regression
```

A candidate design is not accepted merely because it is logically attractive. Where real data shape can materially change the model, the design must be checked against representative real activity data.

## Evidence classes

- **REAL REQUIRED** — real FIT/GPX data shape can materially change the domain contract; real evidence is required before freezing the decision.
- **REAL PREFERRED** — real evidence is useful, but a carefully constructed synthetic case may complete the decision if real evidence is unavailable.
- **SYNTHETIC SUFFICIENT** — the question is primarily geometric or contractual and is better tested with controlled synthetic cases.
- **DESIGN DECISION** — the issue is primarily lifecycle, auditability, or architecture; real files do not determine the answer, although a real workflow may be used to validate usefulness.

## Evidence strength

Evidence strength describes how much real-world variation should be observed before a question can reasonably converge:

- **E1** — synthetic or contractual evidence is sufficient.
- **E2** — one representative real case plus a synthetic attack.
- **E3** — multiple materially different real cases plus a synthetic attack.

Evidence strength is not a sample-size target. Collection stops when new cases no longer expose a materially different data shape relevant to the decision.

## Decision outcomes

Each evidence question ends in one of three outcomes:

- **SUPPORTED** — evidence supports one candidate strongly enough to form a domain decision.
- **CONTRADICTED** — evidence invalidates or materially weakens a candidate.
- **INCONCLUSIVE** — current evidence cannot distinguish candidates safely.

`INCONCLUSIVE` is a valid result. Lack of a real example is never evidence that the case cannot occur.

## Observation discipline

Real-world cases must separate observation from interpretation.

### Observation

Record only what the source actually contains or what can be deterministically measured, for example:

- number of position records;
- whether timestamps continue through a GPS gap;
- whether device distance continues;
- whether pause/resume events exist;
- largest time gap between valid positions;
- largest spatial jump;
- whether FIT and GPX express segment breaks differently.

### Interpretation

Only after observations are recorded should the case compare candidate models and state what the evidence supports.

Do not edit the domain model while recording observations.


---

## Current evidence outcomes

The following outcomes reflect the evidence and controlled attacks completed during Milestone 0. Accepted semantics are formalized in [domain-model.md](domain-model.md) and the ADRs under [decisions/](decisions/).

| Evidence question | Current outcome | Domain impact |
|---|---|---|
| EP-01 — minimum valid CanonicalTrack | SUPPORTED | ordered usable coordinates are sufficient for spatial reconstruction; time and telemetry are optional capabilities |
| EP-02 — GPS interruption / continuity | SUPPORTED | CanonicalTrack uses ordered continuity parts; no geometry is inferred across breaks |
| EP-03 — GPS outliers / observation semantics | SUPPORTED, scope-limited | normalized observations must remain distinct from judgment-based cleaned/usable geometry; anomaly taxonomy remains open |
| EP-04 — FIT vs GPX representation | SUPPORTED | TrackSource and CanonicalTrack remain separate provenance layers |
| EP-05 — TargetSegment lineage | SUPPORTED | TargetSegment requires parent-track lineage with interpolated TrackPosition semantics |
| EP-06 — TargetArea geometry | SUPPORTED | v0.1 supports valid Polygon/MultiPolygon and rejects arbitrary/invalid target geometry |
| EP-07 — spatial boundary semantics | SUPPORTED | four-state relation retained; zero-length point touch is not traversal; positive-length boundary overlap is coverage |
| EP-08 — manual decision lifecycle | REVIEW | algorithmic assessment must remain immutable, but override representation is not yet frozen |

EP-02, EP-05, EP-06, and EP-07 have completed their required synthetic attacks. EP-03 has enough evidence to fix the provenance boundary but not to claim an exhaustive GPS anomaly model.

A cross-cutting completeness question discovered during the target-area gap attacks is also **SUPPORTED**: SpatialAssessment must distinguish core relation from target-coverage reconstruction completeness. ADR-0007 freezes a two-state completeness contract (`complete` / `incomplete`) and requires incomplete results to retain auditable target-relevant uncertainty provenance.

# Evidence questions

## EP-01 — Minimum valid CanonicalTrack

**Edge cases:** EC-07, EC-08, EC-09  
**Evidence class:** REAL PREFERRED  
**Strength:** E2

### Question

What information is minimally required for a track to be spatially valid for target-area reconstruction?

### Candidate models

**A. Temporal minimum**

A spatial track requires ordered coordinates and timestamps.

**B. Spatial minimum**

A spatial track requires ordered coordinates only; timestamps, altitude, and distance are optional capabilities.

### Required real evidence

At minimum:

- one normal FIT activity;
- one normal GPX activity;
- preferably one valid coordinate sequence without timestamps if such a source is available.

### Observe

- position fields;
- timestamp availability;
- altitude availability;
- distance availability;
- point ordering;
- whether spatial geometry remains meaningful when non-spatial fields are absent.

### Synthetic attack

Construct an ordered coordinate track with no timestamps and verify that its intended spatial relation to a target area is unambiguous.

### Decision trigger

If spatial classification and clipping remain well-defined without timestamps or altitude, the v0.1 minimum point contract should not require those fields.

### Stop condition

One representative FIT and one representative GPX have been inspected, and the synthetic no-timestamp case does not expose an ambiguity in spatial reconstruction.

### Outcome

**SUPPORTED.**

The clean paired baseline was reduced to ordered coordinates only by removing timestamps, altitude, distance, speed, and other telemetry. The resulting route geometry, `inside / partial / outside` relations, and clipped segment geometry were unchanged.

A separate two-point coordinate-only route also produced an unambiguous positive-length clip. A single observation, or observations that only produce zero-length geometry, may remain evidence but are insufficient by themselves for positive-length route reconstruction.

Accepted decision: deterministic observation order plus usable spatial coordinates are the minimum spatial contract. Time and other telemetry are optional capabilities. See ADR-0006.

---

## EP-02 — GPS interruption and CanonicalTrack continuity

**Edge cases:** EC-10, EC-21  
**Evidence class:** REAL REQUIRED  
**Strength:** E3

### Question

How should one real-world Activity represent periods where usable GPS observations disappear and later resume?

### Candidate models

**A. Single continuous point series**

All valid observations are connected in sequence.

**B. One CanonicalTrack with multiple continuity parts**

The Activity remains one track, but unobserved gaps split the geometry into separate ordered parts.

**C. Multiple CanonicalTrack objects**

Each observed section becomes a separate canonical track.

### Required real evidence

Seek materially different cases:

- one normal continuous activity as baseline;
- one activity with pause/resume behavior;
- one activity with a genuine GPS interruption or weak-signal recovery if available.

### Observe

- whether timestamps continue while position disappears;
- whether device distance continues;
- pause/resume events;
- FIT record behavior;
- GPX `trkseg` behavior if available;
- time and distance between the last valid point before a gap and first valid point after it;
- whether the source still represents one Activity.

### Synthetic attack

Construct two observed sections separated by a long unobserved interval and a large spatial displacement. Place the target area on the straight line between them.

The model must not claim target-area traversal solely because an implementation connected the two observed sections.

### Decision trigger

If a real Activity can contain a materially unobserved spatial interval where connecting the endpoints would invent a path, the model needs an explicit continuity concept.

### Stop condition

At least one genuine discontinuity is observed, the candidates can be distinguished, and an additional materially different case does not reveal a new continuity shape.

---

## EP-03 — GPS outliers and canonical observation semantics

**Edge cases:** EC-11  
**Evidence class:** REAL REQUIRED  
**Strength:** E3

### Question

Should CanonicalTrack contain normalized source observations, cleaned geometry, or both?

### Candidate models

**A. CanonicalTrack is cleaned geometry**

Implausible observations are corrected or removed before they become canonical.

**B. CanonicalTrack is normalized observation evidence**

Source observations are preserved after format normalization; cleaning produces separate derived geometry or metrics.

### Required real evidence

Seek:

- one normal track;
- one track with an obvious GPS jump or drift;
- preferably one weak-signal trail/urban-canyon activity with less extreme but persistent positional noise.

### Observe

- whether the anomalous point is present in the original source;
- timestamp difference around the anomaly;
- spatial displacement;
- implied raw speed;
- whether another export of the same Activity preserves the anomaly;
- whether removing the point requires a judgment threshold rather than simple parsing.

### Synthetic attack

Construct a single extreme outlier between otherwise plausible points. Verify whether deleting it changes source evidence and whether the cleaning decision can be reproduced from a named algorithm/version.

### Decision trigger

If the anomaly is genuine source evidence and removing it depends on an algorithmic judgment, cleaned geometry must remain distinguishable from normalized observations.

### Speed/pace evidence note

Record the implied speed anomaly. This evidence will later be reused by the planned track metric overlay work; it does not make speed a Milestone 0 core field.

### Stop condition

At least one real anomaly and one normal baseline have been compared, and a second noisy case does not reveal a fundamentally different provenance requirement.

---

## EP-04 — FIT and GPX representations of the same Activity

**Edge cases:** EC-04, EC-10, EC-27  
**Evidence class:** REAL REQUIRED  
**Strength:** E2 to E3

### Question

Do multiple source formats for one Activity preserve enough different information that TrackSource and CanonicalTrack must remain separate layers?

### Required real evidence

Prefer one Activity for which both original FIT and GPX export are available.

### Compare

- point count;
- timestamp precision/coverage;
- altitude;
- recorded distance;
- pause/resume information;
- segment breaks;
- GPS precision;
- available telemetry;
- start/end positions;
- resulting geometry.

### Decision trigger

If the two sources differ in structure or information while referring to the same real-world Activity, the model must retain independent TrackSource provenance and parser/version lineage.

### Synthetic attack

Not normally required if a same-Activity FIT/GPX pair exists. If no pair exists, construct equivalent geometry in two source formats with intentionally different non-spatial fields.

### Stop condition

One same-Activity pair is sufficient if it reveals a meaningful representation difference. If it does not, inspect a second pair before concluding that the distinction is immaterial.

---

## EP-05 — TargetSegment lineage

**Edge cases:** EC-23  
**Evidence class:** REAL REQUIRED plus SYNTHETIC  
**Strength:** E2

### Question

What lineage representation is sufficient to trace a clipped TargetSegment back to CanonicalTrack observations?

### Candidate models

**A. Geometry only**

Store the clipped geometry and parent track ID.

**B. Point-index range**

Store start/end point indices.

**C. Track position references**

Store a position along the parent track, potentially including part index, point index, and interpolation fraction.

### Required real evidence

Use a real track that crosses a target-area boundary between recorded GPS observations.

### Observe

- whether the exact clip boundary is an original track point;
- whether clipping creates an interpolated boundary point;
- whether the track contains multiple continuity parts;
- whether one assessment produces multiple target segments.

### Synthetic attack

Construct cases where:

- a segment starts between two source points;
- a segment ends between two source points;
- a track contains multiple parts;
- the track enters and leaves the target area multiple times.

### Decision trigger

The selected lineage model must reproduce the derived segment from the parent CanonicalTrack without relying on coordinate matching alone.

### Stop condition

One real boundary-crossing case and the four synthetic attacks are representable without special-case fields.

---

## EP-06 — TargetArea geometry contract

**Edge cases:** EC-14  
**Evidence class:** SYNTHETIC SUFFICIENT  
**Strength:** E1

### Question

Which geographic geometry types belong in the v0.1 TargetArea contract?

### Candidate contract

Support:

- Polygon;
- MultiPolygon.

Reject in v0.1:

- Point;
- LineString;
- arbitrary GeometryCollection.

### Synthetic attack

Verify that one semantic target composed of multiple disconnected polygons can still be assessed as one TargetArea.

### Decision trigger

If Polygon and MultiPolygon cover the intended area semantics without introducing ambiguous non-area geometry, freeze them as the supported v0.1 types.

---

## EP-07 — Spatial boundary semantics

**Edge cases:** EC-15, EC-20  
**Evidence class:** SYNTHETIC SUFFICIENT  
**Strength:** E1

### Questions

1. Does a fully inside track generate a TargetSegment covering the full usable track?
2. What counts as entering a target area when a track only touches or follows the boundary?

### Required synthetic cases

- fully inside;
- fully outside;
- clear crossing;
- point-touch only;
- positive-length travel along the boundary.

### Candidate policy

A pure point-touch should not create target-area travel. Positive-length overlap should be handled deterministically and must not depend on accidental geometry-library defaults.

### Decision trigger

The policy must produce stable `inside`, `partial`, `outside`, or `unknown` semantics without introducing a fifth relation solely for touching.

---

## EP-08 — Manual decision versus algorithmic assessment

**Edge cases:** EC-24  
**Evidence class:** DESIGN DECISION plus real workflow validation  
**Strength:** E1

### Question

Does the v0.1 domain need a first-class object for a human decision that differs from an algorithmic SpatialAssessment?

### Workflow to validate

Use one real review scenario in which:

- the algorithm produces a relation;
- a human reviewer intentionally chooses a different task-facing interpretation;
- the reason must remain explainable later.

### Facts that may need preservation

- algorithmic relation;
- algorithm/version;
- manual decision;
- reason;
- actor/provenance;
- decision time;
- effective task-facing result.

### Candidate models

**A. Override fields inside SpatialAssessment**

**B. Separate Decision/Override entity linked to SpatialAssessment**

**C. Keep manual decisions outside the v0.1 core but reserve a compatible extension point**

### Decision trigger

If algorithmic evidence and human interpretation have independent lifecycle/audit requirements, they must not overwrite each other.

---

# Real-world case selection

The first evidence pass should select for **information value**, not quantity.

A typical minimal set is:

| Case | Intended evidence |
|---|---|
| RC-01 | normal continuous road-run FIT baseline |
| RC-02 | normal trail-run FIT baseline |
| RC-03 | same Activity available as FIT and GPX |
| RC-04 | pause/resume behavior |
| RC-05 | GPS interruption or weak-signal recovery |
| RC-06 | obvious GPS drift/jump |
| RC-07 | real crossing of a target-area boundary |
| RC-08 | multiple entries into a target area |

One Activity may satisfy multiple case roles. The target is coverage of evidence questions, not eight distinct activities.

## Public-repository privacy rule

Raw private activity tracks should not be committed merely to support this design review.

Potentially sensitive data includes:

- precise home/work start locations;
- habitual route patterns;
- exact activity times;
- private platform identifiers;
- full raw FIT/GPX files.

Real evidence should be analyzed in a private/local workspace. Public repository records should contain only the minimum anonymized structural facts required to justify a domain decision.

Synthetic or sufficiently anonymized fixtures should be used for later public automated tests.

---

# Real-world observation record

Each real case should use the same structure in `docs/real-world-cases.md`:

```text
Case ID
Why selected
Source format(s)
Anonymized source reference

Observed structure
- point count
- position record count
- timestamp continuity
- distance continuity
- pause/resume events
- segment/part breaks
- largest relevant time gap
- largest relevant spatial jump

Observed facts
- facts only

Affected evidence questions
- EP-..

Candidate comparison
- Candidate A explains...
- Candidate B explains...

Contradictions
- ...

Evidence strength
- weak / moderate / strong

Decision impact
- supports / contradicts / inconclusive
```

Do not put interpretation inside `Observed facts`.

---

# Execution order

Resolve evidence questions in this order because they have the greatest chance of changing the core contract:

1. **EP-02 — continuity / multipart behavior**
2. **EP-03 — outliers and canonical observation semantics**
3. **EP-04 — FIT versus GPX representation**
4. **EP-05 — TargetSegment lineage**
5. **EP-01 — minimum CanonicalTrack**
6. **EP-06 — TargetArea geometry contract**
7. **EP-07 — spatial boundary semantics**
8. **EP-08 — manual decision lifecycle**

Synthetic-only questions may be resolved in parallel after the real-data questions no longer threaten the underlying track model.

# Milestone 0 convergence rule

Milestone 0 may proceed to domain-contract freeze only when:

- there are **zero FAIL** cases;
- there are **zero blocking REVIEW** cases;
- unresolved future concerns are explicitly marked `DEFERRED`;
- accepted decisions are reflected in `docs/domain-model.md`;
- material architectural choices have an ADR;
- the full edge-case matrix has been re-reviewed against the revised model.

The goal is not zero uncertainty about every future feature. The goal is a v0.1 contract that is evidence-backed, internally consistent, and does not force foreseeable source/platform behavior into ad-hoc exceptions.
