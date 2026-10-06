# Domain Model

This document is the current Milestone 0 domain contract for **Target Area Route Reconstruction**.

It records evidence-backed domain semantics. It intentionally does not freeze JSON field names, storage layout, geometry-library APIs, quality thresholds, or runtime policy unless those details are required by the domain itself.

## Status

**Milestone:** 0 — Domain Contract  
**Contract status:** draft with accepted spatial decisions  
**Evidence basis:** EP-01, EP-02, EP-04, EP-05, EP-06, and EP-07 are supported; EP-03 supports source-observation preservation and separation from cleaned/usable geometry, while anomaly taxonomy remains open.

No blocking domain-design question remains. Milestone 0 still requires a full edge-case regression and contract-freeze review before it can be marked DONE.

## Core principles

1. Raw source evidence is immutable.
2. Source evidence, normalized observations, quality-controlled geometry, and spatial results are distinct layers.
3. Missing spatial observations never become invented geometry.
4. Spatial relation is a relation between a CanonicalTrack and a versioned TargetArea.
5. Spatial certainty must not exceed the available evidence.
6. Target-derived data remains traceable to its parent CanonicalTrack.
7. TargetArea version changes never mutate source or canonical track evidence.
8. Source platform, source format, acquisition quota, and task-completion policy do not define core domain identity.
9. Spatial relation certainty and target-coverage completeness are distinct dimensions.

## Core entities

The v0.1 core continues to use six entities:

- Activity
- TrackSource
- CanonicalTrack
- TargetArea
- SpatialAssessment
- TargetSegment

Supporting value concepts such as continuity part and TrackPosition are part of the contract but are not independent aggregate roots.

---

## Activity

### Responsibility

Activity represents a real-world recorded activity event.

It is not a file, source-platform object, geometry, or spatial assessment.

### Invariants

- An Activity may exist with zero TrackSource objects.
- An Activity may have multiple TrackSource objects.
- Re-ingesting the same evidence must not create a second real-world Activity merely because processing happened twice.
- Similar metadata from different external sources does not by itself prove that two records are the same Activity.
- Spatial relation is not stored on Activity.

### Identity boundary

Activity has a stable project-local identity.

Source-native identifiers are source-scoped provenance and are not globally valid Activity identifiers.

v0.1 must not perform implicit cross-source merging from approximate time, distance, duration, activity type, route geometry, or any weighted similarity across those fields.

When two TrackSources are explicitly known to describe the same real-world event, they may belong to one Activity. When sameness has not been explicitly established, they remain separate Activities.

Cross-source reconciliation is an explicit auditable adapter/runtime process outside the v0.1 spatial core. Similarity may propose a future reconciliation candidate but cannot itself mutate Activity identity. No reconciliation entity is added to the v0.1 core.

---

## TrackSource

### Responsibility

TrackSource represents an original source of track evidence and its provenance.

A TrackSource is not required by the domain to be a filesystem file. Local FIT and GPX files are the v0.1 reference sources, but future API point streams or other source representations must fit the same abstraction.

### Invariants

- TrackSource is distinct from CanonicalTrack.
- Source content or source observations are immutable once recorded as evidence.
- Acquisition success and parse success are separate lifecycle facts.
- A corrupted but durably available source remains a TrackSource even when no CanonicalTrack can be produced.
- Multiple TrackSource objects may belong to one Activity.
- Source format, origin, content identity, and provenance remain source-specific facts.

### Provenance

A CanonicalTrack derived from a TrackSource must retain enough provenance to identify:

- the source evidence;
- the parser / normalizer identity and version;
- relevant normalization version or parameters.

A later parser version may produce a new canonical result without rewriting the original TrackSource.

---

## CanonicalTrack

### Responsibility

CanonicalTrack is the format-independent normalized spatial evidence used by the deterministic core.

It preserves normalized observations and explicit spatial continuity. It must not silently replace source evidence with cleaned geometry.

### Continuity

A logical CanonicalTrack may contain one or more ordered **continuity parts**.

A continuity part represents an interval in which adjacent observations may participate in the track geometry under the canonical interpolation rules.

Between two continuity parts:

- no spatial edge exists;
- no route length is inferred;
- no TargetArea intersection is inferred;
- no TargetSegment is generated across the break;
- no route-network connectivity may be created across the break.

A break means only that spatial observation continuity is unavailable. It does not encode a mandatory cause such as timer pause, GNSS loss, low-speed filtering, or user behavior.

### Identity and continuity are separate

A position gap does not create a new Activity and does not automatically create a new CanonicalTrack.

Timer state, moving time, device speed, or other telemetry may be evidence relevant to quality analysis but cannot substitute for the continuity contract.

### Observations and cleaned geometry

Real evidence shows that a valid position field can still be temporarily unreliable, especially after a period with unavailable position observations.

Therefore:

- normalized observations must remain reproducible from TrackSource;
- quality flags or cleaning decisions must not erase those observations;
- any cleaned or usable geometry is derived evidence and must retain algorithm/version provenance.

The exact v0.1 representation of quality-controlled geometry remains deferred to schema design after EP-03 is fully closed.

### Minimum spatial contract

EP-01 is accepted.

The minimum canonical observation required by the spatial core is:

- a usable spatial coordinate in the canonical spatial reference;
- deterministic order within its continuity part.

Timestamp, altitude, distance, device speed, heart rate, cadence, and other telemetry are optional capabilities. Their absence does not invalidate otherwise usable spatial reconstruction.

Observation order is mandatory. A coordinate set with no deterministic sequence is not sufficient route evidence.

For positive-length route geometry, a continuity part must contain enough usable ordered observations to produce valid non-zero-length line geometry. In practice this requires at least two non-coincident usable positions.

Singleton or zero-length observations may remain preserved as canonical evidence, but they do not by themselves establish target traversal or produce TargetSegments.

---

## TargetArea

### Responsibility

TargetArea represents the geographic target against which tracks are assessed.

### Geometry contract

v0.1 supports:

- valid Polygon;
- valid MultiPolygon;
- standard polygon interior rings / holes.

v0.1 rejects at the core-contract boundary:

- Point;
- LineString;
- GeometryCollection;
- empty geometry;
- invalid or self-intersecting polygon geometry.

The deterministic core must fail closed rather than silently repairing invalid target geometry.

### Versioning

TargetArea has stable semantic identity plus a versioned geometry/provenance definition.

A boundary revision creates a new TargetArea version for assessment purposes. It does not mutate:

- Activity;
- TrackSource;
- CanonicalTrack;
- historical assessments against earlier versions.

---

## SpatialAssessment

### Responsibility

SpatialAssessment represents the result of assessing one CanonicalTrack against one specific TargetArea version.

Conceptually:

~~~text
CanonicalTrack × TargetArea@version
              ↓
       SpatialAssessment
~~~

Multiple entries, MultiPolygon components, and holes do not create multiple assessments for the same track-area-version pair.

### Relation

The v0.1 core relation remains four-state:

- inside
- partial
- outside
- unknown

No fifth touching or boundary relation is required by current evidence.

### Evidence semantics

Relation is determined from reliable positive-length spatial coverage plus evidence sufficiency. It is not a direct mapping from library predicates such as intersects, touches, crosses, or within.

#### inside

The reliable usable track geometry is covered by TargetArea and there is no relevant unresolved uncertainty that could place part of the track outside.

#### partial

There is reliable positive-length track coverage within TargetArea and reliable positive-length track coverage outside TargetArea.

Once both facts are established, an unrelated uncertainty elsewhere does not invalidate the partial relation.

#### outside

There is no reliable positive-length track coverage within TargetArea, zero-length boundary contact alone does not count as target traversal, and no relevant unresolved uncertainty could change the result.

#### unknown

Available reliable spatial evidence is insufficient to establish inside, partial, or outside, and an unresolved spatial interval could materially change the relation.

### Boundary semantics

TargetArea is treated as a closed geographic set for positive-length coverage.

- A zero-length point touch does not create a TargetSegment and does not by itself change outside to partial.
- A positive-length overlap with the boundary is valid target-area coverage.
- A crossing that happens exactly at a polygon vertex requires no special relation state.

### Unobserved gaps

The straight chord between the last observation before a continuity break and the first observation after it is never evidence geometry.

It may be used for diagnostics or uncertainty analysis but cannot be used to:

- claim target traversal;
- claim non-traversal;
- calculate target length;
- create TargetSegments;
- create route-network connectivity.

A continuity break affects a SpatialAssessment only when it is relevant to that TargetArea.

Reliable constraints may prove that a gap cannot affect an area, but the specific reachability algorithm, telemetry fields, and thresholds are not frozen in Milestone 0.

### Target-coverage completeness

A determined relation does not necessarily mean the target-area route reconstruction is exhaustive.

SpatialAssessment therefore has a second first-class domain dimension: **target-coverage completeness**.

The semantic values are:

- `complete`
- `incomplete`

A representative schema field name is `coverage_completeness`; exact serialization is deferred to Milestone 1.

#### complete

Target-area reconstruction is complete when no unresolved target-relevant uncertainty could change the existence, number, extent, continuity, geometry, or lineage of positive-length TargetArea-covered route portions.

Completeness is target-relative. A CanonicalTrack may contain uncertainty elsewhere and still be complete for a specific TargetArea when that uncertainty cannot affect target coverage.

#### incomplete

Target-area reconstruction is incomplete when at least one unresolved target-relevant uncertainty could change the reconstructed TargetArea coverage, even if the relation itself is already determined.

Known TargetSegments remain valid evidence-backed results, but they must not be presented as an exhaustive set.

#### Relation/completeness invariants

Under the current v0.1 semantics:

- `unknown` implies `incomplete`;
- `outside` implies `complete`;
- `inside` may be `complete` or `incomplete`;
- `partial` may be `complete` or `incomplete`.

Examples:

- clean observed entry/exit with no relevant uncertainty → `partial + complete`;
- observed inside/outside already proves partial, but another relevant gap could hide additional target coverage → `partial + incomplete`;
- all route evidence is guaranteed to remain inside, but an internal unobserved interval prevents exact route reconstruction → `inside + incomplete`;
- observed outside plus all gaps proven unable to reach the area → `outside + complete`;
- observed outside plus a gap that could enter the area → `unknown + incomplete`.

#### Uncertainty auditability

Every incomplete assessment must retain or reference enough structured unresolved uncertainty information to explain why completeness is not established.

At minimum the information must be traceable to:

- the affected CanonicalTrack interval, continuity break, or quality issue;
- why that uncertainty is relevant to the TargetArea;
- the provenance of the evidence/algorithm that left it unresolved.

This supporting uncertainty record is not a new core entity. Its exact Milestone 1 schema remains open.

### Provenance

SpatialAssessment must retain the algorithm/version and TargetArea version used to derive it.

---

## Manual review and effective task-facing classification

Human interpretation has an independent lifecycle from algorithmic spatial evidence.

A first-class **ManualDecision** audit-layer record may reference an exact SpatialAssessment version and choose a different task-facing relation for a defined task or decision scope.

ManualDecision is not one of the six spatial-core entities. It belongs to the review/runtime extension layer.

A ManualDecision must preserve at least:

- stable decision identity;
- referenced SpatialAssessment identity/version;
- decision scope or task context;
- chosen task-facing relation;
- reason/rationale;
- actor or decision-source provenance;
- decision time;
- superseding or revocation provenance when later changed.

ManualDecision never rewrites SpatialAssessment, coverage completeness, TargetSegments, CanonicalTrack, or source evidence.

The effective task-facing classification is a derived projection of the immutable algorithmic assessment plus an applicable ManualDecision. It must expose both the original algorithmic result and the decision provenance.

Manual decisions are append-only audit facts. Replacement or revocation preserves the previous decision rather than destructively editing it.

New spatial evidence is not a manual override: it must enter the evidence pipeline and produce a new algorithmic assessment.

---

## TargetSegment

### Responsibility

TargetSegment represents one maximal continuous positive-length portion of a parent CanonicalTrack that is covered by a TargetArea.

A TargetSegment is derived data.

### Multiplicity

One SpatialAssessment may produce zero, one, or many TargetSegments.

Multiple segments can result from:

- repeated entry and exit;
- separate MultiPolygon components;
- polygon holes;
- continuity breaks;
- other geometry that separates maximal covered intervals.

A geometry-library MultiLineString result is not automatically one domain TargetSegment.

### Lineage

Each TargetSegment must retain lineage to its parent CanonicalTrack.

The lineage contract must support exact positions between adjacent canonical observations because polygon clipping commonly creates boundary points that do not coincide with recorded GPS points.

The required semantic concept is **TrackPosition**.

A TrackPosition must be able to identify:

- the parent continuity part;
- a location relative to an observation / edge in that part;
- an interpolation fraction when the position lies between adjacent observations.

A representative form is:

~~~text
part_index
point_index
fraction_to_next
~~~

This is illustrative only. Field names, index base, numeric precision, and serialization are deferred to schema design.

### Ordering

TargetSegments are ordered by their positions on the parent CanonicalTrack, not by geometry coordinates, length, polygon component, or map order.

### Fully inside tracks

The same maximal-continuous-segment rule applies when a track is fully covered by the TargetArea.

A single continuous fully covered part produces a full-length TargetSegment. Multiple continuity parts remain separate TargetSegments because no geometry exists across their breaks.

---

## Supporting value concepts

### ContinuityPart

An ordered set of canonical observations for which the model permits adjacent observations to form track geometry.

It is owned by CanonicalTrack.

### TrackPosition

A reproducible position on a CanonicalTrack continuity part, including positions interpolated between adjacent observations.

It is used for TargetSegment lineage and may later support metric overlays and other derived intervals.

### CoverageUncertainty

A structured, target-relative explanation of unresolved evidence that prevents a SpatialAssessment from being `complete`.

It is owned by SpatialAssessment and must be traceable to the affected CanonicalTrack interval, continuity break, or quality issue, together with the reason it is relevant to the TargetArea and the provenance of the unresolved judgment.

CoverageUncertainty is a supporting value concept, not an independent core entity.

ContinuityPart, TrackPosition, and CoverageUncertainty are not independent aggregate roots.

---

## Source facts and derived facts

### Source / evidence layer

Examples:

- Activity source references;
- TrackSource bytes or source point stream;
- source timestamps;
- source positions;
- device telemetry;
- source pause/timer events.

These facts are not rewritten by spatial algorithms.

### Canonical evidence layer

Examples:

- normalized observation order;
- normalized positions;
- explicit continuity parts;
- parser/normalizer provenance.

Canonicalization may normalize representation but must preserve provenance to source evidence.

### Derived quality layer

Examples:

- suspicious-position flags;
- cleaned or usable geometry;
- quality intervals;
- diagnostic inferred speed.

These require named algorithm/version provenance.

### Target-derived layer

Examples:

- SpatialAssessment;
- TargetSegment;
- target intersection length;
- target-specific unresolved uncertainty.

These are recomputed when TargetArea version or spatial algorithm version changes.

---

## Cardinalities

The domain must support at least:

~~~text
Activity
  0..N TrackSource

TrackSource
  0..N CanonicalTrack derivations/versions

CanonicalTrack
  1..N continuity parts when spatially valid

CanonicalTrack × TargetArea@version
  0..1 current algorithmic SpatialAssessment per algorithm/version

SpatialAssessment
  0..N TargetSegment
~~~

The runtime may retain multiple historical CanonicalTrack or SpatialAssessment versions for auditability.

---

## Rejected domain shortcuts

Current evidence rejects the following shortcuts:

1. Treat every Activity as one unconditional LineString.
2. Connect continuity breaks with straight segments.
3. Split one logical track into new track identities solely because GPS position disappears.
4. Treat GPX and FIT as interchangeable copies of the same source evidence.
5. Treat any valid position field as automatically trusted cleaned geometry.
6. Infer SpatialAssessment directly from start position or activity metadata.
7. Map intersects/touches/crosses directly to domain relations.
8. Treat a point boundary touch as target traversal.
9. Treat a MultiLineString intersection as one TargetSegment.
10. Store TargetSegment geometry without parent-track lineage.
11. Treat any gap anywhere in a track as making every area assessment unknown.
12. Mutate canonical track evidence when TargetArea changes.
13. Treat a determined relation as proof that all TargetSegments are known.
14. Use a numeric confidence score as a substitute for deterministic completeness semantics.
15. Merge cross-source Activities solely from approximate similarity.
16. Overwrite algorithmic SpatialAssessment fields with a manual decision.

---

## Accepted decisions and ADR mapping

- ADR-0001 — CanonicalTrack continuity parts and no inferred geometry across gaps
- ADR-0002 — Preserve source evidence and separate normalized observations from cleaned geometry
- ADR-0003 — Versioned Polygon/MultiPolygon TargetArea contract
- ADR-0004 — Four-state spatial relation with evidence-aware uncertainty
- ADR-0005 — TargetSegment multiplicity, maximality, ordering, and lineage
- ADR-0006 — Minimum spatial CanonicalTrack contract
- ADR-0007 — SpatialAssessment target-coverage completeness
- ADR-0008 — Cross-source Activity identity is explicit, never similarity-implied
- ADR-0009 — Manual decisions are auditable overlays, not mutations of SpatialAssessment

---

## Remaining Milestone 0 work

No blocking domain-design decision remains.

Before Milestone 0 can be marked DONE:

1. re-run the complete edge-case matrix against this contract;
2. verify zero blocking `FAIL` and zero blocking `REVIEW` cases;
3. verify all deferred concerns have an explicit milestone/extension boundary;
4. freeze the v0.1 domain contract before starting JSON Schema work.

### Explicitly deferred implementation details

The following do not block the domain contract:

- exact quality-controlled/usable-geometry schema and anomaly thresholds;
- continuity-break detection thresholds;
- target-gap reachability algorithms;
- exact TrackPosition field names and numeric serialization;
- CoverageUncertainty schema details;
- cross-source reconciliation object/persistence model for future adapters;
- ManualDecision persistence and multi-decision precedence policy for the runtime layer.

---

## Change rule

Once Milestone 0 is frozen, any later change that alters the semantics in this document requires:

1. a new or superseding ADR;
2. corresponding edge-case / fixture updates;
3. a roadmap update when milestone scope or public contracts change.

Implementation convenience alone is not sufficient reason to weaken an accepted domain invariant.
