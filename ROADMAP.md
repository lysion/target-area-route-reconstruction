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

**Status:** ACTIVE  
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

**Status:** NOT STARTED  
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

---

## Milestone 2 — Deterministic Core

**Status:** NOT STARTED  
**Release target:** v0.1.0

### Goal

Implement the smallest reliable local pipeline:

`FIT/GPX -> CanonicalTrack -> validation -> TargetArea assessment -> TargetSegment -> GeoJSON/basic map`

When valid temporal evidence exists, the basic map may also render an optional speed/pace metric overlay.

### Work

- FIT ingestion;
- GPX ingestion;
- normalization into `CanonicalTrack`;
- track-quality validation;
- spatial relation calculation;
- extraction of target-area segments;
- GeoJSON export;
- basic interactive map export;
- derived segment speed/pace calculation when valid temporal evidence is available;
- quality-aware speed/pace coloring on the map;
- unit and integration tests.

### Explicit non-goals

- COROS/Garmin/Strava adapters;
- remote track acquisition;
- acquisition quota optimization;
- route-network clustering;
- heatmaps;
- training-performance or physiological analysis beyond local track speed/pace visualization;
- route recommendation.

### Exit criteria

- deterministic tests pass for inside/partial/outside/unknown;
- partial tracks produce traceable target segments;
- raw input files are never modified;
- the same input produces stable output;
- FIT and GPX representing equivalent geometry normalize compatibly;
- missing timestamps do not invalidate otherwise valid spatial reconstruction;
- speed/pace overlays are only produced from valid temporal intervals and do not bridge known discontinuities.

---

## Milestone 3 — Persistent Runtime

**Status:** NOT STARTED  
**Release target:** v0.2.0

### Goal

Make long-running reconstruction tasks resumable, auditable, and idempotent.

### Work

- introduce persistent state, initially SQLite unless evidence supports another choice;
- persist activities, track sources, parse state, assessments, and provenance;
- content hashing and duplicate detection;
- cache-first behavior;
- resume after interruption;
- explicit failure states;
- manual overrides as separate auditable evidence;
- if derived metrics are persisted, retain algorithm/version, source-track version, parameters, and quality provenance.

### Exit criteria

- repeated ingestion does not duplicate facts;
- interrupted work resumes without reprocessing completed inputs;
- cached raw sources are preferred over reacquisition;
- source, parser, algorithm, and target-area versions are traceable.

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
- source metadata mapping.

### Order

1. local-file adapter as the reference implementation;
2. COROS adapter;
3. additional adapters only when a real use case justifies them.

### Exit criteria

- adding a source adapter does not require changes to `CanonicalTrack` or spatial-classification contracts;
- source-specific fields remain outside the portable core model;
- adapter failures are represented explicitly.

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

**Current milestone:** Milestone 0 — Domain Contract

**Completed in this milestone:**

- created and exercised `docs/edge-cases.md` as the design-time stress matrix;
- created `docs/evidence-plan.md` and completed representative evidence for EP-02 through EP-07 where required;
- recorded five anonymized real-world evidence cases in `docs/real-world-cases.md`;
- completed controlled attacks for continuity, target clipping, repeated entry, MultiPolygon, polygon holes, point touch, positive-length boundary overlap, target-version changes, and target-relevant unobserved gaps;
- accepted continuity-part semantics and prohibited inferred geometry across continuity breaks;
- accepted TrackSource / CanonicalTrack provenance separation and preservation of normalized observations from judgment-based cleaned geometry;
- accepted the v0.1 Polygon/MultiPolygon TargetArea contract;
- accepted four-state evidence-aware spatial relation semantics;
- accepted TargetSegment multiplicity, maximality, ordering, and parent-track lineage requirements;
- added `docs/domain-model.md` and nine initial ADRs under `docs/decisions/`;
- closed EP-01: ordered usable coordinates are the minimum spatial contract; timestamps and telemetry are optional capabilities;
- froze target-coverage completeness as a second SpatialAssessment dimension (`complete` / `incomplete`) with auditable unresolved uncertainty provenance;
- resolved cross-source Activity identity: similarity never implies identity, and future reconciliation remains explicit/auditable outside the v0.1 spatial core;
- closed EP-08: ManualDecision is a first-class audit/runtime overlay that never mutates algorithmic SpatialAssessment;
- retained planned speed/pace metric overlays as a later derived capability rather than a Milestone 0 core field.

**Remaining Milestone 0 work:**

1. re-run the full edge-case matrix against `docs/domain-model.md` and ADR-0001 through ADR-0009;
2. verify zero blocking `FAIL` and zero blocking `REVIEW` cases;
3. verify every `DEFERRED` case has an explicit later-milestone boundary;
4. freeze the v0.1 domain contract before creating JSON Schemas.

Work on Milestone 1 or later remains deferred until these exit criteria are met.
