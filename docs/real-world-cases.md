# Real-World Evidence Cases

This document records anonymized observations from representative real activity data used to resolve the evidence questions in `docs/evidence-plan.md`.

It is intentionally **not** a raw-track archive.

## Privacy rule

Do not commit private FIT/GPX files or unnecessary precise location/time data merely to support the design review.

Public records contain only the minimum structural facts needed to justify domain-model decisions. Exact coordinates, exact timestamps, platform identifiers, and raw source excerpts are omitted.

## Observation rule

Separate facts from interpretation.

- **Observed facts** describe only what the source contains or what can be deterministically measured.
- **Interpretation** compares candidate models only after the observations are recorded.

No raw activity file from this evidence pass is committed to the public repository.

## Current status

Five anonymized real cases were inspected locally. Four form the primary evidence set and one is supporting replication.

The evidence set covers:

- a complex trail activity with both FIT and GPX representations;
- a trail activity with extreme position unavailability and recovery convergence;
- a long trail activity with many position gaps but no meaningful timer-pause structure;
- a clean continuous road-run FIT/GPX baseline;
- an additional trail case replicating gap-recovery convergence.

Controlled spatial attacks were then constructed from the clean baseline and from deliberately hidden portions of known real geometry. Those synthetic attacks are summarized in the relevant ADRs and are not raw-track evidence.

---

## RC-01 — Complex trail activity with paired FIT and GPX

**Why selected**

Primary evidence for EP-02 and EP-04: continuity behavior, timer behavior, and representation differences between FIT and GPX.

**Source format(s)**

- FIT
- GPX
- anonymized local evidence reference only

**Observed structure**

- FIT records: 37,798
- FIT records with usable position: 34,291
- FIT records without usable position: 3,507
- internal position discontinuities: 230
- GPX track segments: 231
- timer start events: 64
- timer stop-type events: 64

**Observed facts**

- GPX segment boundaries correspond closely to FIT position-continuity breaks.
- Only about 51 internal position gaps overlap timer-paused intervals; about 179 do not.
- During some non-pause gaps, timestamp, device distance, speed, and heart-rate records continue while position is unavailable.
- Shared FIT/GPX position timestamps are geometrically close but the two representations are not point-for-point identical.
- Device speed telemetry is preserved across many shared FIT/GPX timestamps.

**Affected evidence questions**

- EP-02
- EP-04
- EP-03 supporting evidence

**Candidate comparison**

- A single unconditional point series invents geometry across unobserved intervals.
- Multiple CanonicalTrack identities per gap confuse spatial continuity with track identity.
- One logical CanonicalTrack with ordered continuity parts explains the source structure without inventing paths.

**Contradictions / limitations**

The case contains both timer pauses and non-pause gaps, so it cannot by itself isolate all continuity mechanisms.

**Evidence strength**

Strong.

**Decision impact**

Supports explicit continuity parts and TrackSource/CanonicalTrack separation.

**Public-data note**

Coordinates, precise times, activity identifier, and raw track files are omitted.

---

## RC-02 — Trail activity with extreme position loss and recovery convergence

**Why selected**

Primary abnormal case for EP-03 and additional continuity evidence for EP-02.

**Source format(s)**

- FIT
- anonymized local evidence reference only

**Observed structure**

- records: 8,423
- records with usable position: 3,817
- records without usable position: 4,606
- internal position gaps: 45
- timestamp coverage: effectively continuous
- distance/speed/heart-rate coverage: effectively continuous
- no meaningful mid-activity timer pause structure

**Observed facts**

- More than half of records lack usable position while other telemetry continues.
- Several long position gaps occur without timer pauses.
- After some gaps, the first restored position observations move geometrically much faster than contemporaneous device speed.
- The source therefore contains position observations that are syntactically valid but not automatically equivalent to trusted cleaned geometry.
- A platform-level adjusted-pace value was grossly inconsistent with the source speed telemetry, illustrating the need to separate source facts from higher-level derived/display metrics.

**Affected evidence questions**

- EP-02
- EP-03

**Candidate comparison**

- Treating CanonicalTrack as cleaned geometry would hide the original abnormal observations.
- Preserving normalized observations and deriving quality-controlled geometry separately retains auditability.

**Contradictions / limitations**

This case is dominated by position unavailability and recovery behavior; it does not establish an exhaustive taxonomy of isolated spike or persistent drift anomalies.

**Evidence strength**

Strong for provenance separation; incomplete for anomaly taxonomy.

**Decision impact**

Supports preserving normalized observations separately from quality-controlled derived geometry.

**Public-data note**

Coordinates, precise times, activity identifier, and raw FIT are omitted.

---

## RC-03 — Long trail activity with non-pause position gaps

**Why selected**

Independent EP-02 case intended to separate spatial continuity from timer pause behavior.

**Source format(s)**

- FIT
- anonymized local evidence reference only

**Observed structure**

- records: 45,537
- records with usable position: 40,621
- records without usable position: 4,916
- internal position gaps: 216
- timer structure: activity start and final end only; no meaningful mid-activity pause/resume sequence

**Observed facts**

- Hundreds of position gaps occur without corresponding timer pauses.
- Many gaps have little endpoint displacement and device distance change, including long near-stationary intervals.
- Timestamp, distance, speed, and heart-rate records continue through the activity.
- The source still represents one Activity.

**Affected evidence questions**

- EP-02

**Candidate comparison**

- Timer state cannot define spatial continuity.
- Splitting each gap into a new CanonicalTrack would create hundreds of track identities from one source activity.
- Continuity parts preserve one logical track while representing missing spatial observation.

**Contradictions / limitations**

Most gaps in this case are near-stationary, so it complements rather than replaces the moving-gap evidence in RC-01.

**Evidence strength**

Strong.

**Decision impact**

Supports continuity as an independent track property.

**Public-data note**

Coordinates, precise times, activity identifier, and raw FIT are omitted.

---

## RC-04 — Clean continuous road-run baseline with paired FIT and GPX

**Why selected**

Clean control for EP-02 and EP-04 and the real geometry used for controlled TargetArea / TargetSegment attacks under EP-05 through EP-07.

**Source format(s)**

- FIT
- GPX
- anonymized local evidence reference only

**Observed structure**

- FIT records: 2,299
- FIT usable positions: 2,297
- internal position gaps: 0
- GPX tracks: 1
- GPX track segments: 1
- position sampling: approximately one second
- no mid-activity timer pause

**Observed facts**

- A normal activity can remain spatially continuous without artificial GPX segmentation.
- FIT and GPX point counts differ slightly even in a clean case.
- Shared telemetry such as distance, device speed, heart rate, cadence, and altitude is highly consistent where both representations contain it.
- Shared positions are close but not byte/coordinate-value identical.
- The clean geometry supports deterministic controlled clipping without continuity or quality confounders.

**Affected evidence questions**

- EP-02
- EP-04
- EP-05
- EP-06
- EP-07

**Controlled uses**

The real geometry was used to construct:

- single entry/exit clipping;
- repeated target entry;
- point-touch;
- positive-length boundary overlap;
- polygon-vertex crossing;
- MultiPolygon;
- polygon hole;
- target-version change;
- deliberate hidden-path gaps with known ground truth.

**Evidence strength**

Strong baseline.

**Decision impact**

Supports normal continuity baseline, format/provenance separation, TargetSegment lineage, TargetArea contract, and boundary semantics.

**Public-data note**

Coordinates, precise times, activity identifier, and raw FIT/GPX are omitted.

---

## RC-05 — Additional trail recovery-convergence replication

**Why selected**

Exploratory EP-03 candidate intended to find an anomaly independent of gap recovery.

**Source format(s)**

- FIT
- anonymized local evidence reference only

**Observed structure**

- records: 8,846
- records with usable position: 7,372
- records without usable position: 1,474
- internal position gaps: 78

**Observed facts**

- Most prominent geometry/device-speed inconsistencies occur immediately after position gaps.
- No clear independent isolated teleport or persistent continuous drift was found in otherwise continuous portions.
- The case independently replicates recovery-convergence behavior seen in RC-02.

**Affected evidence questions**

- EP-03
- EP-02 supporting evidence

**Contradictions / limitations**

The intended independent anomaly morphology was not found.

**Evidence strength**

Moderate supporting evidence.

**Decision impact**

Strengthens the requirement to separate normalized observations from trusted derived geometry, but does not close an exhaustive anomaly taxonomy.

**Public-data note**

Coordinates, precise times, activity identifier, and raw FIT are omitted.

---

## Case index

| Case | Evidence question(s) | Source | Result | Status |
|---|---|---|---|---|
| RC-01 | EP-02, EP-04 | FIT + GPX | continuity breaks differ from timer pause; paired formats differ materially | recorded |
| RC-02 | EP-02, EP-03 | FIT | extreme position loss and recovery convergence | recorded |
| RC-03 | EP-02 | FIT | many non-pause gaps in one Activity | recorded |
| RC-04 | EP-02, EP-04, EP-05, EP-06, EP-07 | FIT + GPX | clean baseline and controlled spatial-attack source | recorded |
| RC-05 | EP-03 | FIT | recovery-convergence replication; no independent teleport/drift found | recorded |
