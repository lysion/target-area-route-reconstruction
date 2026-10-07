# Project Roadmap

This roadmap is the governing development plan for **Target Area Route Reconstruction**.

The project follows four operating principles:

1. **Contract first** — stabilize the domain model before implementation.
2. **Test first** — define edge cases and expected behavior before adding core logic.
3. **Repository first** — repository files, schemas, tests, ADRs, and commits are the source of truth; chat history is not.
4. **Thin skill, deterministic core** — agent instructions orchestrate; parsing, geometry, validation, persistence, and exports are implemented as deterministic code.

## Status vocabulary

- `NOT STARTED` — no implementation work should begin yet.
- `ACTIVE` — current milestone.
- `BLOCKED` — cannot proceed until a documented blocker is resolved.
- `DONE` — exit criteria are satisfied and committed.
- `DEFERRED` — intentionally outside the current release path.

A later milestone should not begin until the current milestone's exit criteria are satisfied, unless the roadmap is explicitly revised.

---

## Milestone 0 — Domain Contract

**Status:** DONE  
**Target:** design baseline for v0.1

### Goal

Freeze the minimum domain model required to represent target-area historical route reconstruction without coupling the model to COROS, FIT, a specific map engine, or an acquisition quota.

### Candidate core entities

- `Activity`
- `TrackSource`
- `CanonicalTrack`
- `TargetArea`
- `SpatialAssessment`
- `TargetSegment`

### Work

- define entity responsibilities, identity, lifecycle, and relationships;
- define which facts are source data and which are derived data;
- define provenance and versioning requirements;
- test the model against edge cases;
- execute the evidence plan against representative real-world and synthetic cases;
- separate observed facts from interpretation before accepting domain decisions;
- record material architectural decisions as ADRs.

### Required edge cases

At minimum, the model must express:

- a track fully inside the target area;
- a track entering and leaving the target area;
- a track starting inside but mostly outside;
- a track entirely outside;
- an activity with metadata but no track;
- a valid track without timestamps;
- a source file without usable GPS;
- multiple track sources for one activity;
- one track assessed against multiple target-area versions;
- multiple disjoint target segments from one track;
- duplicate source-file ingestion;
- parser failure without misclassification as `outside`;
- algorithmic assessment plus an explicit manual override without destroying the algorithmic result.

### Deliverables

- `docs/edge-cases.md`
- `docs/evidence-plan.md`
- `docs/real-world-cases.md` as the anonymized evidence record
- `docs/domain-model.md`
- initial ADRs under `docs/decisions/`

### Exit criteria

Milestone 0 is DONE only when:

- all required edge cases can be represented without ad-hoc fields;
- there are zero `FAIL` cases and zero blocking `REVIEW` cases;
- unresolved future concerns are explicitly marked `DEFERRED`;
- core entities have stable identity and ownership boundaries;
- the model is independent of source platform and track file format;
- target-area version changes do not require mutation of raw track evidence;
- accepted decisions are reflected in `docs/domain-model.md`;
- no unresolved model ambiguity blocks schema definition.

---

## Milestone 1 — Schemas and Fixtures

**Status:** DONE — adversarial remediation and fresh re-exit review passed
**Target:** machine-verifiable v0.1 contracts

### Goal

Encode the frozen domain contract into schemas and reproducible test fixtures before writing the deterministic analysis core.

### Work

- create JSON Schemas for frozen entities;
- define canonical enums and nullability rules;
- create synthetic FIT/GPX/track fixtures for edge cases;
- define expected classification and clipping outputs;
- add optional temporal/metric fixtures for constant speed, acceleration/deceleration, pause, GPS jump, discontinuity, and missing timestamps;
- validate all fixtures against schemas.

### Deliverables

- `schemas/activity.schema.json`
- `schemas/track-source.schema.json`
- `schemas/canonical-track.schema.json`
- `schemas/target-area.schema.json`
- `schemas/spatial-assessment.schema.json`
- `schemas/target-segment.schema.json`
- `tests/fixtures/`
- fixture expectation manifest

### Exit criteria

- schemas validate all intended valid fixtures;
- invalid fixtures fail for documented reasons;
- all Milestone 0 edge cases have reproducible fixtures or explicit non-file test representations;
- no schema depends on COROS-specific fields.

The independent-audit re-exit additionally requires ordered interval/multiplicity validation, reason-specific negatives, mandatory Layer A for linked components, mutation-sensitive continuity tests, a documented numerical policy and quality hand-off, strict JSON, independent raw format checks, and a fresh review with green branch CI. Historical PASS records remain preserved.

---

## Milestone 2 — Deterministic Core

**Status:** ACTIVE — M2A and M2B are DONE; M2C is the sole immediate implementation checkpoint
**Release target:** v0.1.0

**M2A checkpoint:** DONE after independent review and merge of PR #2. Deterministic local FIT/GPX ingestion now normalizes preserved source evidence into the frozen `CanonicalTrack` shape while retaining source order, continuity boundaries, repeated observations, and missing-position diagnostics. See [implementation and acceptance record](docs/milestone2a-canonical-ingestion.md).

**M2B checkpoint:** DONE after independent review and merge of PR #3. Track quality now produces an immutable supporting `QualityProjection`, explicit source/quality gaps, optional independently verified constraints, and a deterministic verifier while preserving original parent indices. See [implementation record](docs/milestone2b-quality-projection.md). M2 remains ACTIVE; M2C is ACTIVE.

### Goal

Implement the smallest reliable local pipeline:

`FIT/GPX -> CanonicalTrack -> validation -> relation/completeness proof -> TargetSegment -> SpatialAssessment -> GeoJSON/basic map`

The relation/completeness proof is a non-identity-bearing supporting result. It does not add a seventh core entity. The frozen `SpatialAssessment` entity is assembled only after required `TargetSegment` references exist.

When valid temporal evidence exists, the basic map may also render an optional speed/pace metric overlay.

### Work

- FIT ingestion;
- GPX ingestion;
- normalization into `CanonicalTrack`;
- track-quality validation;
- implement the supporting quality result and gap-proof verifier in [the quality-layer interface](docs/quality-layer-interface.md), preserving normalized observations and parent indices;
- spatial relation calculation;
- extraction of target-area segments;
- GeoJSON export;
- basic interactive map export;
- derived segment speed/pace calculation when valid temporal evidence is available;
- quality-aware speed/pace coloring on the map;
- unit and integration tests.

### Execution checkpoints

These checkpoints sequence the existing Milestone 2 work only. They do not expand the v0.1 scope, change the six frozen core entities, or introduce new domain semantics. If the sequencing or scope needs to change, update this roadmap before implementation.

#### M2A — Canonical ingestion

**Status:** DONE

- FIT ingestion;
- GPX ingestion;
- normalization into the frozen `CanonicalTrack`;
- deterministic source/normalization diagnostics;
- source continuity and parent-position preservation.

M2A stops before quality classification, spatial assessment, derived speed/pace, GeoJSON, and map output.

#### M2B — Track quality, QualityProjection, and gap-proof verifier

**Status:** DONE

Implement the quality-layer hand-off already defined in [the quality-layer interface](docs/quality-layer-interface.md):

- deterministic track-quality validation;
- an immutable supporting `QualityProjection` value/result with exact parent `CanonicalTrack` identity and algorithm/version/parameters;
- ordered `usable_intervals`;
- ordered `excluded_intervals` with stable reason codes and evidence references;
- explicit `gaps` for source discontinuities and quality-excluded geometry;
- optional `gap_constraints` only when independently justified by supporting evidence;
- a deterministic verifier that rejects out-of-bounds, overlapping, cross-part, stale, or unsupported quality/gap claims;
- preservation of original normalized observations and parent indices;
- mutation-sensitive tests proving that rejected or missing geometry cannot be silently reconnected.

M2B may identify and bound uncertainty. It must not reconstruct a unique missing path, infer TargetArea relation/completeness, or generate TargetSegments.

The [M2B implementation record](docs/milestone2b-quality-projection.md) documents the accepted explicit-policy algorithm, immutable supporting values, source/quality gaps, domain-only proof method and adversarial verifier. Independent acceptance passed before PR #3 was merged.

#### M2C — Spatial relation and completeness proof

**Status:** ACTIVE

M2C produces a deterministic, non-identity-bearing supporting result for downstream M2D. It does **not** create the frozen `SpatialAssessment` entity and does not add a seventh core entity.

- accept a `QualityProjection` only after `verify_quality(...)` returns `valid` against the exact M2A evidence snapshot and expected quality policy; an unverified or stale projection is not spatial authority;
- determine whether the parent track has usable positive-length route geometry and is assessable under ADR-0004;
- if no usable positive-length route geometry exists, return an explicit non-assessable supporting result and create no relation and no `SpatialAssessment`;
- for assessable tracks, prove TargetArea relation under the frozen `inside / partial / outside / unknown` semantics;
- calculate target-relative coverage completeness under the existing contract;
- preserve established inside/outside evidence even when unresolved gaps remain;
- fail closed when a gap can still change the target-relative conclusion;
- retain ordered parent-interval/evidence support sufficient for M2D to extract exhaustive `TargetSegment` results without re-deriving or inventing spatial facts;
- treat `usable` as quality-admitted under the explicit algorithm/policy, not as proof that the GPS geometry is the unique or true route;
- explicitly test leading and trailing gaps;
- keep all target-relative conclusions traceable to the exact parent CanonicalTrack revision, verified quality result, target revision, algorithm/version and parameters.

The M2C supporting result may carry relation/completeness proof material and original-parent interval evidence, but it must not assign `TargetSegment` identity/revision, ordinals, final segment geometry, or `target_segment_refs`. Those belong to M2D.

**ADR-0004 assessability rule:** `unknown` is not a substitute for an unassessable track. When no usable positive-length route geometry exists, no `SpatialAssessment` is created. `unknown` applies only when an assessable track exists but unresolved spatial evidence can still change the relation.

**Open M2 gap-bound obligation:** the accepted M2B implementation verifies only the tautological complete CRS84-domain bound. It does not provide a useful local spatial bound for a short GPS gap. M2C must not reinterpret that domain bound as local proof. Any v0.1 acceptance claim that depends on proving a gap wholly inside a local target or disjoint from a local target requires an independently justified local gap-bound method plus verifier support first; until then that specific conclusion must remain unresolved/fail closed.

M2C must not invent new gap evidence, infer a unique missing path, silently interpolate missing geometry, bypass M2B verification, generate `TargetSegment`, or assemble `SpatialAssessment`.

#### M2D — Target-area segment extraction and SpatialAssessment assembly

**Status:** NOT STARTED

- consume only an assessable, verified M2C supporting result;
- extract traceable `TargetSegment` results from the target-relative parent intervals proved by M2C;
- preserve original parent `CanonicalTrack` lineage and TrackPositions;
- enforce maximality within each continuous usable interval;
- preserve repeated visits as distinct occurrences;
- never span a source continuity break, excluded interval, or unresolved gap;
- verify TargetSegment coverage/exhaustiveness against the M2C proof result;
- after required TargetSegments exist, assemble the frozen `SpatialAssessment` entity with exact CanonicalTrack, TargetArea, algorithm and segment references;
- enforce the frozen schema requirement that `inside` and `partial` assessments reference at least one `TargetSegment`, while `outside` references none;
- for an M2C non-assessable result, create neither `TargetSegment` nor `SpatialAssessment`.

M2D must not reclassify relation/completeness by inventing new spatial evidence. If M2C proof material is insufficient to construct schema-valid, exhaustive segments and assessment references, fail closed rather than fabricating references.

#### M2E — GeoJSON and basic interactive map

**Status:** NOT STARTED

- export accepted spatial results to GeoJSON;
- provide a basic interactive map;
- distinguish confirmed geometry, target segments, and quality/uncertainty state where represented;
- keep rendering downstream of deterministic analysis rather than creating new inference.

#### M2F — Valid temporal metrics and quality-aware map coloring

**Status:** NOT STARTED

- derive segment speed/pace only where temporal evidence is valid;
- keep speed/pace unavailable across missing or non-increasing timestamps, continuity breaks, excluded geometry, or unresolved gaps;
- add quality-aware speed/pace coloring to the basic map;
- preserve spatial evidence even when temporal metrics are unavailable.

Unit and integration testing remain cross-cutting requirements throughout M2, and the Milestone 2 exit criteria below remain authoritative for the complete release slice.

### Cross-cutting v0.1 obligations

These obligations are not separate checkpoints, but they must be closed before Milestone 2 can be marked DONE and v0.1.0 can be released.

- **Installed-wheel CI gate:** CI must build the wheel, install it with runtime dependencies into an isolated environment outside the source checkout, and smoke-test at least FIT ingestion, GPX ingestion with the packaged `spec/gpx-1.1.xsd`, M2B quality projection, and quality verification. Editable-checkout tests alone are insufficient release evidence.
- **Source-format support matrix:** document the exact v0.1 FIT/GPX support boundary. At minimum distinguish supported GPX track input from unsupported route/waypoint semantics, and document chained FIT plus any profile/developer/compressed-message combinations that remain outside project-level acceptance coverage. “FIT/GPX supported” must not overstate the tested subset.
- **Explicit quality-policy ownership:** the deterministic core must not acquire an implicit human-speed or GPS-quality threshold. Quality policy remains explicit, versioned/caller-owned unless a later roadmap revision introduces a separately named and validated reference policy.
- **Quality semantics:** `usable` means admitted by the declared quality algorithm and policy; it is not certification that the geometry is error-free, physically unique, or the true route.
- **Gap semantics:** a verified spatial bound constrains uncertainty but is not reconstructed geometry. v0.1 does not create an inferred centerline or “most likely” path for a gap.
- **Release documentation:** limitations that remain intentionally unsupported must be visible in the v0.1 support/limitations documentation rather than existing only in implementation notes.

### Explicit non-goals

- COROS/Garmin/Strava adapters;
- remote track acquisition;
- acquisition quota optimization;
- route-network clustering;
- heatmaps;
- training-performance or physiological analysis beyond local track speed/pace visualization;
- route recommendation;
- inferred/estimated missing-route centerlines or unique gap reconstruction in v0.1.

### Exit criteria

- deterministic tests pass for inside/partial/outside/unknown;
- partial tracks produce traceable target segments;
- raw input files are never modified;
- the same input produces stable output;
- FIT and GPX representing equivalent geometry normalize compatibly;
- missing timestamps do not invalidate otherwise valid spatial reconstruction;
- speed/pace overlays are only produced from valid temporal intervals and do not bridge known discontinuities;
- downstream spatial code consumes only independently verified M2B quality claims bound to the exact evidence snapshot and policy;
- no-usable-positive-length-geometry cases are explicitly non-assessable and create no `SpatialAssessment`; unresolved leading/trailing-gap cases fail closed rather than becoming `outside`;
- the v0.1 source-format support matrix accurately states supported and explicitly unsupported FIT/GPX cases;
- CI proves the installed wheel works outside the repository checkout, including packaged GPX XSD access and representative ingestion/quality smoke paths;
- v0.1 documentation preserves the distinction between observed geometry, quality-admitted geometry, bounded unresolved gaps, and unsupported inferred geometry.

---

## Milestone 3 — Persistent Runtime

**Status:** NOT STARTED  
**Release target:** v0.2.0

### Goal

Make long-running reconstruction tasks resumable, auditable, and idempotent.

### Work

- introduce persistent state, initially SQLite unless evidence supports another choice;
- persist activities, durable raw TrackSource evidence, parse state, assessments, and provenance;
- content hashing and duplicate detection;
- preserve a durable evidence chain from raw TrackSource bytes/content hash -> exact TrackSource revision -> CanonicalTrack revision -> QualityProjection/evidence fingerprint -> downstream derived artifacts;
- on reload/reuse, verify stored content hashes and revision bindings so a self-consistent reconstructed snapshot cannot silently substitute for the preserved source evidence;
- cache-first behavior;
- resume after interruption;
- explicit failure states;
- manual overrides as separate auditable evidence;
- if derived metrics are persisted, retain algorithm/version, source-track version, parameters, and quality provenance.

M3 provides integrity/custody of evidence after it enters the system. It does not claim universal cryptographic authenticity of the upstream provider or prove that a user-imported file was genuine before ingestion.

### Exit criteria

- repeated ingestion does not duplicate facts;
- interrupted work resumes without reprocessing completed inputs;
- cached raw sources are preferred over reacquisition;
- source, parser, algorithm, and target-area versions are traceable;
- every persisted CanonicalTrack and derived quality/spatial artifact can be traced to the exact durable TrackSource revision and content hash used to produce it;
- silent replacement/tampering of persisted raw evidence or substitution of a merely self-consistent synthetic snapshot is detected rather than accepted as the original custody chain.

---

## Milestone 4 — Agent Skill

**Status:** NOT STARTED  
**Release target:** v0.3.0

### Goal

Package the stable deterministic workflow as a reusable agent skill.

### Design rule

`SKILL.md` remains thin. It owns orchestration, not parsing or GIS algorithms.

### Work

- final `SKILL.md`;
- progressive-disclosure references;
- tool/command selection rules;
- preflight logic;
- completion criteria;
- agent evals distinct from code tests.

### Agent evals must verify

- cached evidence is checked before remote acquisition;
- metadata is not treated as full-track proof;
- invalid or missing tracks are not silently classified as outside;
- raw evidence is not overwritten;
- the agent selects deterministic scripts for deterministic work;
- task completion follows the requested objective rather than exhausting available data.

### Exit criteria

- a fresh agent can execute the local-file workflow using only repository instructions;
- evals reliably catch known failure modes;
- Skill instructions do not duplicate implementation details maintained in code.

---

## Milestone 5 — Source Adapter Layer

**Status:** NOT STARTED  
**Release target:** v0.4.0

### Goal

Support multiple activity/track sources without changing the core domain or spatial engine.

### Adapter contract

Adapters may implement:

- activity discovery;
- track-source resolution;
- track acquisition;
- source metadata mapping;
- acquisition provenance, including whether evidence was user-imported or obtained through a provider-authenticated path;
- provider/native identifiers and integrity/authenticity signals when the upstream source actually exposes them.

Adapters must not claim provider authenticity when the source supplies no mechanically verifiable authenticity evidence.

### Order

1. local-file adapter as the reference implementation;
2. COROS adapter;
3. additional adapters only when a real use case justifies them.

### Exit criteria

- adding a source adapter does not require changes to `CanonicalTrack` or spatial-classification contracts;
- source-specific fields remain outside the portable core model;
- adapter failures are represented explicitly;
- acquired evidence records distinguish import/acquisition provenance, and any provider-authenticity claim is limited to evidence actually supplied or verifiable through that provider.

---

## Milestone 6 — Resource-Aware Acquisition

**Status:** NOT STARTED  
**Release target:** v0.5.0

### Goal

Optimize missing-track acquisition when access is constrained by quota, cost, rate limits, or latency.

### Work

- represent resource constraints as task/runtime policy, not domain identity;
- candidate prioritization;
- small adaptive batches;
- re-ranking after newly acquired evidence;
- stop when marginal information value is low or the task objective is satisfied.

### Exit criteria

- unrestricted acquisition still works without prioritization logic;
- constrained acquisition can reduce unnecessary remote retrievals;
- a successful acquisition is not recorded until durable source evidence exists.

---

## Milestone 7 — Historical Route Network

**Status:** NOT STARTED  
**Release target:** v0.6.0

### Goal

Move from individual target-area segments to a reusable historical route-network representation.

### Work

- route/segment similarity;
- repeated coverage;
- temporal coverage;
- route families;
- optional heat/frequency representations;
- optional aggregation of speed/pace distributions across repeated route segments after route-segment identity is stable.

### Constraint

Do not freeze a network schema before real target-segment datasets reveal the required semantics.

### Exit criteria

- network results are reproducible from persisted target segments;
- network derivation never mutates source or canonical tracks;
- coverage statistics are traceable back to contributing activities.

---

## Milestone 8 — v1.0 Hardening

**Status:** NOT STARTED  
**Release target:** v1.0.0

### Goal

Prove that the project is genuinely reusable rather than a single-user or single-region workflow.

### Work

- run at least two materially different real-world benchmarks;
- stabilize public APIs and schemas;
- compatibility policy and migrations;
- CI for schemas, tests, linting, and skill validation;
- installation and usage documentation;
- contribution guidelines;
- release notes and semantic versioning;
- security/privacy review for activity-location data.

### Exit criteria

- the same core works across multiple data sources or usage environments without domain-model redesign;
- public contracts are documented and versioned;
- fresh-user installation and example workflow pass end-to-end.

---

## Change-control policy

The roadmap is intentionally strict but not immutable.

A material change must be documented when it changes any of the following:

- milestone order;
- v0.1 scope;
- frozen domain entities or contracts;
- public schema semantics;
- architectural boundaries;
- completion criteria.

When such a change is accepted:

1. update this roadmap in the same development cycle;
2. add or update an ADR when the change is architectural;
3. update README scope/status when externally visible behavior changes;
4. update affected tests/evals before considering the change complete.

Minor implementation details that do not change contracts do not require a roadmap revision.

No project decision should rely solely on chat history.

---

## Current execution point

**Current milestone:** Milestone 2 — Deterministic Core. M2A and M2B are DONE after independent review and merge; M2C is the sole immediate implementation checkpoint.

**Milestone 0 outcome: DONE**

The v0.1 domain contract is frozen.

Milestone 0 completed:

- evidence-backed domain model in `docs/domain-model.md`;
- ADR-0001 through ADR-0010;
- five anonymized real-world evidence cases;
- controlled attacks for continuity, clipping, multiple entry, MultiPolygon, holes, boundary semantics, gap uncertainty, lineage, and coverage completeness;
- cross-source Activity identity policy;
- ManualDecision audit-layer lifecycle;
- full EC-01 through EC-29 regression: 26 PASS, 0 REVIEW, 0 FAIL, 3 explicitly bounded DEFERRED;
- final contract freeze review in `docs/contract-freeze-review.md`;
- explicit canonical spatial-reference compatibility requirement;
- explicit boundary between normalized observations and optional derived quality/usable geometry.

**Milestone 1 objective:**

Encode the frozen domain contract into machine-verifiable schemas and reproducible fixtures without changing domain semantics.

**Milestone 1 historical outcome: PASS, subsequently reopened for remediation**

Milestone 1 completed:

- defined shared schema conventions in `docs/schema-conventions.md`;
- selected JSON Schema Draft 2020-12;
- fixed v0.1 serialization conventions for IDs/revisions, nullability, enums, units, timestamps, extensions, validation layers, and schema versioning;
- fixed canonical geometry serialization to OGC:CRS84 with `[longitude, latitude]` positions;
- fixed zero-based TrackPosition serialization as `part_index / observation_index / fraction_to_next`;
- added reusable definitions in `schemas/common.schema.json`;
- added `schemas/README.md` as the schema workspace guide;
- implemented `schemas/canonical-track.schema.json` with ordered ContinuityParts, canonical observations, source revision provenance, optional temporal/telemetry capabilities, and explicit no-edge part boundaries;
- implemented `schemas/target-area.schema.json` with versioned Polygon/MultiPolygon geometry, canonical spatial reference, and boundary provenance;
- implemented `schemas/spatial-assessment.schema.json` with relation/completeness invariants and CoverageUncertainty;
- implemented `schemas/target-segment.schema.json` with revision lineage, TrackPosition endpoints, ordinal, and canonical LineString geometry;
- implemented `schemas/track-source.schema.json` with Activity ownership, source namespace/native provenance, source-agnostic representation metadata, and optional content identity;
- implemented intentionally minimal `schemas/activity.schema.json` as the stable project-local real-world event identity anchor;
- completed all six frozen core entity schemas;
- expanded valid/invalid fixtures to Activity and TrackSource; fixture manifest now distinguishes schema validity, semantic validity, and CanonicalTrack assessability;
- implemented `scripts/validate_schema_fixtures.py` as the executable JSON Schema Draft 2020-12 fixture runner with repository-relative `$ref` resolution, schema self-validation, format checking, manifest expectation comparison, and deterministic exit codes;
- added `requirements-dev.txt` and `.github/workflows/schema-validation.yml` for push/PR contract validation;
- implemented `scripts/validate_semantic_fixtures.py` as an independent semantic-validation layer using Shapely/GEOS for topology and deterministic cross-object/lineage checks;
- added `tests/fixtures/semantic-scenarios.json` with linked Activity → TrackSource → CanonicalTrack → TargetArea → SpatialAssessment → TargetSegment scenarios;
- converted EC-14 through EC-23 into linked semantic coverage: fully inside/outside, single/repeated entry, start-inside departure, point touch, positive-length boundary overlap, relevant continuity gap, MultiPolygon, polygon hole, multiple TargetSegments, and lineage;
- added EC-29 linked `partial-incomplete-gap` coverage so a determined partial relation can coexist with unresolved additional target coverage;
- added negative cross-object validation for geometry/lineage mismatch, out-of-bounds TrackPosition, wrong CanonicalTrack revision, wrong TargetArea revision, reversed TargetSegment reference order, and schema-level spatial-reference mismatch;
- added `tests/nonfile-contract-cases.json` for lifecycle/runtime/reconciliation cases that cannot honestly be represented as standalone core entity fixtures in Milestone 1;
- added `tests/edge-case-coverage.json` mapping all EC-01 through EC-29 to fixtures, linked semantic scenarios, or explicit non-file contract cases;
- added `scripts/validate_edge_case_coverage.py` and CI coverage-map validation;
- expanded the schema fixture manifest to 113 entries and linked semantic scenarios to 16;
- added `schemas/common-conformance.schema.json` plus 14 independent valid/invalid probes for shared ID/reference/CRS/coordinate/time/TrackPosition/hash definitions;
- ran the complete contract-validation workflow green on commit `74867ba37b6b48ecd7f70a588e3a7e86c2f569b7`: Layer A 113/113, Layer B 33/33, edge-case coverage 29/29; recorded in `docs/milestone1-validation-run.md`;
- recorded complete coverage in `docs/milestone1-edge-case-coverage.md` and linked spatial detail in `docs/milestone1-linked-scenario-coverage.md`;
- added a synthetic, privacy-safe raw source baseline under `tests/source-fixtures/`, including equivalent FIT/GPX inputs, no-timestamp GPX, explicit GPX discontinuity, malformed GPX, and valid no-position FIT;
- added `tests/source-fixtures/manifest.json` with SHA-256 integrity, source-structure expectations, future normalization expectations, and GPX/FIT equivalence requirements;
- added deterministic fixture generation and source-baseline validation scripts;
- ran the final Milestone 1 contract workflow green: 113/113 schema expectations, 33/33 semantic expectations, 29/29 edge cases mapped, 6/6 raw source fixtures verified, and 1 FIT/GPX equivalence group verified;
- closed the Milestone 1 exit review in `docs/milestone1-exit-review.md`.

**Milestone 1 historical exit review:** PASS. Its sufficiency was invalidated by an independent adversarial audit of commit `141dc092f5a3c7845066156cafd26b3879e99137`; see `docs/milestone1-remediation.md`.

**Milestone 1 remediation outcome:** DONE after [fresh re-exit review](docs/milestone1-re-exit-review.md) and [branch CI](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37573668670). The frozen v0.1 contract remains unchanged. The strengthened gate verifies 260 schema fixtures, 56 semantic expectations, 29 owned EC representations, 12 raw files/two equivalence groups and 25 unit/integration tests, including adversarial and mutation witnesses. This supersedes the sufficiency of the historical PASS above.

**Milestone 2 current execution:**

- **M2A — DONE:** deterministic FIT/GPX canonical ingestion is merged. Raw evidence remains immutable; source ordering, continuity breaks, repeated observations, and parent-position lineage are preserved.
- **M2B — DONE:** deterministic track-quality validation, supporting `QualityProjection`, explicit source/quality gaps, domain-only gap proof support, and the independent quality/gap verifier are merged after independent acceptance.
- **M2C — ACTIVE:** implement a non-identity-bearing spatial relation/completeness proof result only from independently verified M2B claims. No usable positive-length route geometry means non-assessable and no SpatialAssessment. The current domain-only bound is not a useful local gap proof; local-bound-dependent conclusions remain fail-closed until an independently justified local proof method exists.
- **M2D — NOT STARTED:** extract exhaustive TargetSegments from the accepted M2C proof result, then assemble the frozen SpatialAssessment with valid target-segment references. Non-assessable M2C results produce neither entity.
- **M2E–M2F — NOT STARTED:** proceed only after M2D: GeoJSON/basic map, then valid temporal metrics and quality-aware coloring.
- **Cross-cutting before M2 DONE:** installed-wheel/outside-checkout CI smoke, an explicit v0.1 FIT/GPX support matrix, explicit quality-policy ownership, and release documentation for quality/gap limitations.

Any schema need that would change a frozen invariant must trigger a new/superseding ADR rather than an implementation shortcut. Any proposed change to this checkpoint order or Milestone 2 scope must update this roadmap before implementation. M3 owns durable evidence custody/integrity after ingestion; M5 owns source-adapter acquisition provenance/authenticity only where mechanically supported.
