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

**Status:** ACTIVE — M2A merged; M2B is the sole immediate implementation checkpoint
**Release target:** v0.1.0

**M2A checkpoint:** DONE after independent review and merge of PR #2. Deterministic local FIT/GPX ingestion now normalizes preserved source evidence into the frozen `CanonicalTrack` shape while retaining source order, continuity boundaries, repeated observations, and missing-position diagnostics. See [implementation and acceptance record](docs/milestone2a-canonical-ingestion.md). M2 remains ACTIVE.

### Goal

Implement the smallest reliable local pipeline:

`FIT/GPX -> CanonicalTrack -> validation -> TargetArea assessment -> TargetSegment -> GeoJSON/basic map`

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

**Status:** ACTIVE

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

The [M2B implementation record](docs/milestone2b-quality-projection.md) documents the current explicit-policy algorithm, immutable supporting values, source/quality gaps, domain-only proof method and adversarial verifier. Status remains ACTIVE until independent acceptance.

#### M2C — Spatial relation calculation

**Status:** NOT STARTED

- consume the M2B quality result and verified gap constraints;
- calculate TargetArea relation under the frozen `inside / partial / outside / unknown` semantics;
- calculate coverage completeness under the existing target-relative contract;
- preserve established inside/outside evidence even when unresolved gaps remain;
- fail closed when a gap can still change the target-relative conclusion.

M2C must not invent new gap evidence or silently interpolate missing geometry.

#### M2D — Target-area segment extraction

**Status:** NOT STARTED

- extract traceable `TargetSegment` results from spatially admitted usable geometry;
- preserve original parent `CanonicalTrack` lineage and TrackPositions;
- enforce maximality within each continuous usable interval;
- preserve repeated visits as distinct occurrences;
- never span a source continuity break, excluded interval, or unresolved gap.

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

**Current milestone:** Milestone 2 — Deterministic Core. M2A is DONE after independent review and merge; M2B is the sole immediate implementation checkpoint.

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
- **M2B — ACTIVE:** implement track-quality validation, the supporting `QualityProjection`, explicit gaps, optional independently justified gap constraints, and the deterministic quality/gap verifier.
- **M2C–M2F — NOT STARTED:** proceed only in the checkpoint order defined above: spatial relation calculation, TargetSegment extraction, GeoJSON/basic map, then valid temporal metrics and quality-aware coloring.

Any schema need that would change a frozen invariant must trigger a new/superseding ADR rather than an implementation shortcut. Any proposed change to this checkpoint order or Milestone 2 scope must update this roadmap before implementation.
