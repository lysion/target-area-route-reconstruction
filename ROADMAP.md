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

**Status:** DONE — fresh [post-Codex re-exit PASS_WITH_LIMITATIONS](docs/milestone2-codex-reexit-review.md). Earlier M2 PASS at `7059953c` was invalidated by independently reproduced P1 F1/F2; versioned fixes merged in PR #18 (`5b52738d`) and exact merged-main CI [37847574877](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37847574877) SUCCESS. No v0.1.0 tag/publication; M3 NOT STARTED.
**Release target:** v0.1.0

**M2A checkpoint:** DONE after independent review and merge of PR #2. Deterministic local FIT/GPX ingestion now normalizes preserved source evidence into the frozen `CanonicalTrack` shape while retaining source order, continuity boundaries, repeated observations, and missing-position diagnostics. See [implementation and acceptance record](docs/milestone2a-canonical-ingestion.md).

**M2B checkpoint:** DONE after independent review and merge of PR #3. Track quality now produces an immutable supporting `QualityProjection`, explicit source/quality gaps, optional independently verified constraints, and a deterministic verifier while preserving original parent indices. See [implementation record](docs/milestone2b-quality-projection.md). The original 2026-10-08 M2D acceptance was reopened by independent Codex F1 and subsequently reverified after M2B QualityAlgorithm `0.1.1` rejects noncanonical adjoining admissible intervals. See [post-Codex re-exit](docs/milestone2-codex-reexit-review.md).

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

**Status:** DONE — reopened after original PR #3 historical acceptance, independently challenged by Codex F1, repaired in PR #18: `QualityAlgorithm 0.1.1` independently verifies canonical maximal admitted runs (error `USABLE_INTERVAL_NOT_MAXIMAL`); source/installed-wheel regressions and [fresh M2 re-exit](docs/milestone2-codex-reexit-review.md) PASS.

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

**Status:** DONE

M2C is DONE after independent review and merge of PR #4. It produces a deterministic, non-identity-bearing supporting result for downstream M2D. It does **not** create the frozen `SpatialAssessment` entity and does not add a seventh core entity.

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

**Status:** DONE — reverified through stronger M2B 0.1.1 verified partition admission, Codex F1 split-interval adversarial tests and wheel smoke; earlier independent PR #8 re-review PASS is historical; PR #8 merged (`3e99364459188e24efd3bd901cc2cb9ad3d5dd1a`), ADR-0012 accepted

The implementation preflight on `632e9c7` reproduced valid assessable M2C proofs with an absent leading/trailing endpoint. Frozen `trackRange` requires two concrete parent TrackPositions; no accepted anchor convention represents the absent extent. See [minimal reproducer and blocker record](docs/milestone2d-target-segments.md) and [ADR-0011](docs/decisions/0011-open-ended-coverage-uncertainty.md). ADR-0011 was accepted as a pre-release v0.1.0 erratum in PR #7, and the amended schema and regressions are merged. This paragraph preserves the original blocker history; ADR-0011 unblocked implementation, which was completed and independently accepted in PR #8.

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

PR #8 accepted admission hardening and the versioned canonical-snapshot policy are recorded in [the implementation record](docs/milestone2d-implementation.md) and [ADR-0012](docs/decisions/0012-m2d-canonical-assembly-snapshots.md). The [support-boundary matrix](docs/v0.1-support-boundaries.md) separates required admission checks from later work. M2D independent acceptance is complete; M2E may proceed without expanding frozen spatial authority.

M2D must not reclassify relation/completeness by inventing new spatial evidence. If M2C proof material is insufficient to construct schema-valid, exhaustive segments and assessment references, fail closed rather than fabricating references.

#### M2E — GeoJSON and basic interactive map

**Status:** DONE — independently audited PR #11 merged (`802cc18bad88b8edb7051051c77614d60f1fa164`); final-head CI [37775412882](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37775412882) SUCCESS

- export accepted spatial results to GeoJSON;
- provide a basic interactive map;
- distinguish confirmed geometry, target segments, and quality/uncertainty state where represented;
- keep rendering downstream of deterministic analysis rather than creating new inference.

M2E acceptance: GeoJSON projection requires independently valid exact M2C proof and M2D canonical snapshot. The offline SVG map distinguishes TargetArea, ordered original observed TargetSegments, optional observed outside fragments and actual gap endpoints without ever drawing a gap chord. Unknown/incomplete/non-assessable are represented separately. Final-head CI passed 245 unit tests, explicit Node.js map interactions and isolated-wheel FIT/GPX→M2E end-to-end smoke; independent [PR #11 review](https://github.com/lysion/target-area-route-reconstruction/pull/11#pullrequestreview-5456393871) returned PASS. At the time of M2E acceptance, M2F had not started; M2E itself does not infer routes.

#### M2F — Valid temporal metrics and quality-aware map coloring

**Status:** DONE — original PR #13 accepted version 0.1.0, later reopened by independent Codex F2, repaired by PR #18 with `temporal-overlay 0.1.1` source-diagnostic propagation, live Node map and wheel regression plus [fresh re-exit](docs/milestone2-codex-reexit-review.md); original independently re-reviewed PR #13 merged (`a2ab7fe871806982d2e69bf87240b4842dbe4a06`); final-head CI [37779156527](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37779156527) SUCCESS

- derive segment speed/pace only where temporal evidence is valid;
- keep speed/pace unavailable across missing or non-increasing timestamps, continuity breaks, excluded geometry, or unresolved gaps;
- add quality-aware speed/pace coloring to the basic map;
- preserve spatial evidence even when temporal metrics are unavailable.

M2F **original v0.1.0 historical accepted behavior** tied derived metric to exact admitted TrackPosition parent edges and UTC times, with neutral invalid time and numeric bins, but INCORRECTLY equated `explicit speed rule enabled` with `parent edge passed`. Superseding v0.1.1 now carries exact per-parent-edge M2B decision and reason: numeric indeterminate blue short-dashed, rule disabled blue long-dashed, parent-edge explicitly passed blue solid, unavailable metric gray dashed; legend discloses proportional clip elapsed-time assumptions and non-equivalence of parent vs clipped velocity. Numeric validity is NOT a motion-truth guarantee. See [fresh re-exit](docs/milestone2-codex-reexit-review.md). Final-head CI passed 265 Python tests, mandatory Node JS display interactions and 4 installed-wheel FIT/GPX→M2F cases including no-timestamps GPX. Initial independent [CHANGES REQUIRED](https://github.com/lysion/target-area-route-reconstruction/pull/13#pullrequestreview-5456683052) was resolved, and exact-head [PASS re-review](https://github.com/lysion/target-area-route-reconstruction/pull/13#pullrequestreview-5456795395) accepted the scoped M2F capability. No core schema, M2A–M2D authority or M2E geometry semantics changed.

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

**Status:** NOT STARTED — mandatory [immutable evidence-custody / verifiable-reload contract](docs/milestone3-evidence-custody-contract.md) and [F3–F6 owned action gates](docs/post-m2-f3-f6-action-plan.md) documented; design requirements are **not** implemented persistence.
**Release target:** v0.2.0

### Goal

Make long-running reconstruction tasks resumable, auditable, and idempotent. **The first requirement is a trustworthy, independently anchored binding of immutable original bytes to the complete derived evidence graph; merely writing six entity JSON objects into SQLite is not an acceptable M3 result.**

### Design entry gate (required before tables or runtime caches)

- **Use the selected concrete M3 trust root:** Linux split-principal Ed25519 signer, independently protected hash-chained append-only log and independently pinned monotone checkpoint. Worker has no signing key, cannot edit/rollback log/checkpoint; signer verifies before committing and cannot undo prior commits; verifier reads externally trusted checkpoint. See explicit actor/capability matrix and rollback tests. Mutable SQLite digests alone are insufficient.
- Bind **the complete frozen TrackSource revision** (`id,revision_id,schema_version,activity,origin,representation,extensions`) plus original bytes to a signed `SourceAdmission`; source id/revision cannot be reassigned to another Activity, origin, representation or content. Identical blobs across distinct immutable TrackSources do not imply Activity identity; later reconciliation must be independently audited.
- Define **complete immutable snapshot graph AND externally signed graph-root commitment**: source receipt → full M2A IngestionResult/diagnostics/observation_sources → M2B policy/diagnostics → M2C proof/TargetArea content → M2D ordered segments/assessment → optional M2E/M2F outputs. Sign a separate append-only `GraphCommit` containing the **entire closed DAG/manifest SHA-256**, exact target/policy request selectors and the complete execution-artifact digest set; a self-consistent coordinated rewrite of all derived nodes must fail against that separately trusted signed manifest.
- Freeze **reload-before-reuse against an expected signed GraphCommit** and protected log-head checkpoint: compare full TrackSource Activity/origin/representation + immutable raw bytes, re-ingest using **the exact attested parser/normalizer/verifier wheel/native-binary hashes** (not only version names), validate whole signed DAG manifest and M2B/M2C/M2D independently. Rebuilt or swapped same-version executables must fail or report `historical_unverified`; multiple valid graphs for one raw source require explicit selection, not silent auto-choice.
- Agree atomic staging/transaction and manual-override boundaries, idempotency/conflict rules and deterministic migration behavior. New algorithm versions create new snapshots; old evidence is not rewritten.

**Normative design and C01–C22 adversarial acceptance matrix:** [Milestone 3 immutable source / graph-commit custody and reload contract](docs/milestone3-evidence-custody-contract.md).

### Work (implementation required; not yet delivered)

- **M3A / raw custody:** persist original bytes and **complete TrackSource + Activity** snapshot in a signed append-only SourceAdmission; enforce separate signer/key, protected chain/checkpoint, source-revision conflicts, deterministic negative outcomes and signer/rollback permissions. Validate C01–C05/C17/C19/C20.
- **M3B / immutable derivation graph:** persist complete M2A–M2F typed snapshots and evidence outcome; publish a separately **signed full-DAG GraphCommit manifest digest** with exact TargetArea/policy and **actual executable/library artifact SHA-256s**, not mutable self-hashes. Reload against an **expected signed graph** by raw re-ingestion and independent stage verifiers; reject whole-DAG co-forgery, Activity reassignment, same-version binary substitution and ambiguous cached graph selection (C02/C06–C08/C14/C16–C18/C21).
- **M3C / runtime lifecycle:** SQLite or justified alternative, idempotent imports, exact cache/reuse closure, no implicit Activity cross-source merge, interrupted resume, concurrent identity conflict, atomic assessment/segment publication, explicit failure/quarantine states and independently auditable manual overrides.
- **M3D / reliability:** implement [F5 strict JSON parity](docs/post-m2-f3-f6-action-plan.md) before persisted JSON admission; enforce [F6 quantified benchmark](docs/post-m2-f3-f6-action-plan.md): 2 warm-ups + 7 measured medians each at 200/400/800/1600 parts, doubling ratio ≤2.8 for both producer and verifier, ≤1.0s/512MiB benchmark limits and 7 explicit configurable default/maximum resource budgets, clean failures and C12/C13/C22 before claiming batch scalability.
- **F3 preservation:** preserve raw FIT timer events/sparse Record gaps as source evidence and **document that v0.1 continuity and `complete` are not true-route certification**. Do **not** silently introduce pause/time-gap inferred geometry; assign optional event-aware/sparse-interval policy design to M5 or a separately versioned quality algorithm.
- **F4 derivation provenance:** on persisted M2F store `duration_basis`, proportional clip allocation method, exact original edge, `speed_screen_result/reason`, full-parent cap scope, metric null reason and temporal algorithm/version; never relabel allocated border-crossing time or clip speed as device-observed fact.

M3 guarantees integrity/custody **after evidence enters the system**, not the authenticity of an external provider or user-uploaded file before admission, nor security against a party who can rewrite both bytes and a separately trusted immutable receipt.

### Exit criteria (all required; do not substitute green M2 CI)

- Exact immutable raw bytes and **signed complete TrackSource revision** (including immutable Activity/origin/representation) survive process restart in SourceAdmission; **same id/revision with different content OR Activity/provenance fails**, two refs may share a blob, later Activity reconciliation is separately signed, and protected signer/checkpoint policies resist worker tampering and rollback.
- Complete source, parser, normalizer, quality-policy/diagnostics, spatial proof, target revision/content, ordered segments/snapshots, optional M2F time/screen state and negative outcomes can be reloaded with exact lineage; a separate append-only signed **GraphCommit must anchor the full DAG manifest digest**, not merely the raw SourceAdmission.
- After reload, verify signed monotone log/checkpoint, complete TrackSource and raw hash, the **caller-selected expected signed GraphCommit root digest**, genuine M2A re-ingestion, full typed DAG and independent M2B/M2C/M2D checks. Coordinated rewrite of unchanged-raw target/policy and ALL downstream results, swapped Activity/proof/area, receipt rollback, replaced same-version parser/verifier/native binary or unavailable historical engine **must fail closed** or report explicit unverified outcome.
- A fresh FIT and GPX source reproduce deterministic accepted evidence through M2A–M2F where supported; restart in a **separate process**, reload, verify and compare without importing repository source-tree code. Corrupted/no-position/missing-time cases preserve exact negative evidence and original source identity.
- Repeated import and concurrent attempts do not duplicate facts or silently overwrite a revision; staged crash at raw/receipt/DB and at assessment/segment commit boundaries resumes or rolls back with no partially trusted graph; cached verified raw is preferred to reacquisition.
- **F5 gate:** strict raw JSON duplicate-member, underflow, nonfinite, Unicode and malformed-number behavior agrees for scripts, runtime and stored snapshot loader, with explicit negative fixtures and no silent coercion.
- **F6 gate:** frozen Ubuntu/Python3.11/library-artifact environment with 2 warm-ups + 7 medians per size at 200/400/800/1600 parts, both 400→800 and 800→1600 doubling ratios ≤2.8 **for each producer and verifier**, ≤1.0s/512MiB at 1600 parts; enforce explicit [default and maximum numeric quotas](docs/post-m2-f3-f6-action-plan.md) with typed safe rollback and no silent truncation.
- **F3/F4 gates:** replay FIT timer pause/long sparse interval as an acknowledged coverage limitation; persisted clipped-time metrics retain derived-time allocation + original-parent screen scope after restart and never become certified physical observations.
- Pass independent tampering, **complete-DAG co-forgery**, Activity/source reassignment, signer-key/receipt/checkpoint rollback, same-version executable replacement, cached graph ambiguity, F6 numerical budgets, concurrent-conflict, crash-recovery and installed-wheel restart tests [C01–C22](docs/milestone3-evidence-custody-contract.md). Document the trust root, concrete capabilities and out-of-model operator compromise.

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

## Milestone 7 — Cross-Activity Evidence Fusion and Missing-Route Reconstruction

**Status:** NOT STARTED  
**Release target:** v0.6.0

### Goal

Use repeated historical activity evidence to reconstruct target-area route coverage that is systematically missing from individual GPS tracks, while preserving a strict distinction between observed geometry, bounded uncertainty, reconstructed geometry, and unresolved gaps.

The project objective at this stage is not merely to classify whether a gap affects TargetArea relation. It is to improve the completeness of the route representation within the TargetArea when the available evidence can support a defensible reconstruction.

### Scope boundary

Milestone 7 operates after deterministic per-activity reconstruction, persistence, source adapters, and resource-aware acquisition are available. It may combine evidence across multiple Activities, but it must not rewrite raw TrackSource evidence, CanonicalTrack observations, or previously accepted TargetSegments.

A reconstructed route is derived evidence. It is never serialized or presented as directly observed GPS geometry.

Milestone 7 does not require every gap to be reconstructed. Its valid terminal outcomes include:

- unique — one route remains admissible under the declared evidence model;
- ambiguous — multiple materially different routes remain admissible;
- unresolved — available evidence is insufficient to produce a useful reconstruction claim.

Exact serialization and whether these outcomes become a new persisted supporting artifact or a later-version domain entity must be decided from real datasets and documented before implementation. No new core entity is frozen by this roadmap revision.

### Evidence priority

Evidence should be used in descending authority where available:

1. observed geometry from other Activities that independently traversed the same corridor;
2. exact gap endpoints and verified parent-track lineage;
3. independently supported local reachability or distance bounds;
4. elapsed time, device distance, elevation, heading, speed, cadence, or other telemetry when its provenance and uncertainty are explicitly supported;
5. versioned external path/road/trail network data;
6. weaker historical similarity or statistical priors only as ranking evidence, never as sole proof of a unique route.

The implementation must distinguish evidence that proves a constraint from evidence that only ranks candidates.

### Work

- identify source and quality gaps that recur in the same target-area corridor across Activities;
- cluster repeated gaps without discarding Activity identity, direction, visit multiplicity, or provenance;
- search independently observed historical tracks for geometry that can explain a missing corridor;
- support verified local gap-reachability constraints when an evidence-backed method exists;
- generate candidate paths only inside the admissible spatial/evidence envelope;
- optionally use versioned external road/path/trail topology when historical observations do not resolve the gap;
- test candidate paths against available distance, elapsed-time, elevation, heading, telemetry, direction and topology constraints;
- retain all materially admissible alternatives rather than selecting a visually convenient route;
- classify reconstruction results as unique, ambiguous, or unresolved under explicit algorithm/version/parameters;
- produce reconstructed geometry only when supported by the declared evidence model;
- keep observed and reconstructed geometry separately queryable and separately renderable;
- persist complete reconstruction provenance once the supporting persistence model is defined;
- expose reconstruction confidence through explicit evidence state and alternatives rather than an ungrounded scalar confidence score;
- define deterministic rules for how accepted reconstructed geometry may be consumed by the later Historical Route Network milestone.

### Cross-activity safeguards

- an inferred or reconstructed segment must not be counted as an independent observed witness for reconstructing another gap;
- repeated reconstructions derived from the same underlying observed Activities must not create artificial evidence multiplicity;
- circular support chains are invalid;
- one complete observed traversal may support several missing Activities, but each derived claim must retain the exact contributing evidence set;
- contradictory observed traversals must preserve ambiguity unless other independent constraints resolve it;
- systematic GPS loss at the same location is evidence of a recurring observation gap, not proof by itself of one physical path.

### Reconstruction semantics

A local gap can be useful before its exact route is known. Therefore Milestone 7 keeps separate:

- **movement evidence** — evidence that motion occurred during the gap;
- **extent evidence** — evidence that constrains where that motion could have occurred;
- **candidate-route evidence** — evidence that admits or rejects specific paths;
- **reconstructed geometry** — a derived route claim supported by the preceding evidence.

A verified local spatial bound may settle TargetArea relation without settling route geometry. That remains a valid and weaker result. Route reconstruction is attempted only where it materially improves target-area path completeness.

### Exit criteria

- recurrent target-area gaps can be detected and grouped reproducibly across Activities;
- observed peer-track evidence can be used without losing exact contributing Activity and TrackSource provenance;
- reconstruction never mutates CanonicalTrack or converts inferred coordinates into observed coordinates;
- every reconstructed route is reproducible from an exact evidence set, external-network version where used, and algorithm/version/parameters;
- a unique result is emitted only when materially different admissible alternatives have been eliminated by explicit evidence or constraints;
- ambiguous candidates remain explicit and are not collapsed into a single route for visualization convenience;
- unresolved gaps remain unresolved when evidence is insufficient;
- inferred geometry cannot recursively manufacture independent evidence for later inference;
- repeated use of the same underlying evidence does not inflate support;
- at least one benchmark demonstrates recovery of a systematically missing corridor using independent observed traversals;
- at least one adversarial benchmark demonstrates that plausible competing routes remain ambiguous rather than being falsely resolved;
- downstream consumers can distinguish observed, reconstructed, ambiguous, and unresolved route coverage.

---

## Milestone 8 — Historical Route Network

**Status:** NOT STARTED  
**Release target:** v0.7.0

### Goal

Move from individual target-area segments and accepted reconstructed coverage to a reusable historical route-network representation that is as complete as the available evidence permits.

### Work

- route/segment similarity across observed TargetSegments;
- integration of accepted reconstructed geometry without erasing its evidence class;
- repeated coverage;
- temporal coverage;
- route families;
- observed-versus-reconstructed coverage accounting;
- network-level unresolved-gap accounting;
- optional heat/frequency representations;
- optional aggregation of speed/pace distributions across repeated observed route segments after route-segment identity is stable;
- define network-level completeness semantics separately from per-Activity SpatialAssessment completeness.

### Constraint

Do not freeze a network schema before real observed and reconstructed target-area datasets reveal the required semantics.

The network must not treat reconstructed traversals as equivalent independent observations when computing frequency, confidence, or repetition. Observed activity evidence remains separately countable.

### Exit criteria

- network results are reproducible from persisted observed TargetSegments and accepted reconstruction artifacts;
- network derivation never mutates source, canonical tracks, or per-Activity assessments;
- every network edge can report whether its support is observed, reconstructed, mixed, ambiguous, or unresolved;
- frequency and repeated-coverage statistics distinguish direct observations from derived reconstructions;
- network-level completeness can represent recovered systematic gaps without falsely upgrading incomplete per-Activity observation histories;
- coverage statistics remain traceable to contributing Activities, TrackSources, and reconstruction evidence.

---

## Milestone 9 — v1.0 Hardening

**Status:** NOT STARTED  
**Release target:** v1.0.0

### Goal

Prove that the project is genuinely reusable rather than a single-user or single-region workflow.

### Work

- run at least two materially different real-world benchmarks;
- include at least one benchmark with repeated GPS-loss corridors and reconstruction outcomes;
- stabilize public APIs and schemas;
- compatibility policy and migrations;
- CI for schemas, tests, linting, and skill validation;
- installation and usage documentation;
- contribution guidelines;
- release notes and semantic versioning;
- security/privacy review for activity-location data.

### Exit criteria

- the same core works across multiple data sources or usage environments without domain-model redesign;
- reconstructed-route behavior remains auditable across materially different regions and path-network structures;
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

**Current milestone transition:** Milestone 2 Deterministic Core is **DONE — fresh post-Codex PASS_WITH_LIMITATIONS** after versioned F1/F2 fixes, independent Codex PR #18 review with no major findings, 277 source tests and installed-wheel counterexamples on exact merged-main CI [37847574877](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37847574877). See [new exit review](docs/milestone2-codex-reexit-review.md). M3 persistence is the NEXT milestone and NOT STARTED; release/publishing of v0.1.0 is separate.

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
- **M2B — DONE after F1 correction:** v0.1.1 canonical admitted coverage partition independently enforced; adjacent equivalent split fails before M2C, genuine part/source/exclusion gaps remain separate; merged PR #18 and [re-exit](docs/milestone2-codex-reexit-review.md).
- **M2C — DONE:** deterministic spatial relation/completeness proof is merged after independent review in PR #4. It preserves exact M2A/M2B/TargetArea authority, explicit non-assessability, ordered parent-interval evidence, stationary evidence and target-relative gap relevance. The current domain-only bound remains insufficient for useful local short-gap proof and no missing route is reconstructed.
- **M2D — DONE after F1 admission hardening:** original M2D/ADR-0011/0012 remain; independent verifier depends on now-strict M2B 0.1.1 partition admission and cannot accept equivalent artificial quality interval splits; exact F1 source/wheel adversarial regression PASS.
- **M2E — DONE:** independently verified GeoJSON export and offline interactive SVG map accepted in merged PR #11 after 245 tests, Node.js map interaction checks and installed-wheel FIT/GPX→M2E smoke. Ordered observations, gap endpoints and uncertainty are preserved without reconstruction.
- **M2F — DONE after F2 correction:** versioned v0.1.1 per-original-edge exact screened `passed / indeterminate / unavailable / not_screened` and reason, live JS map line types, proportional-time and parent-cap semantics; original PR #13 PASS remains historical, [PR #18](https://github.com/lysion/target-area-route-reconstruction/pull/18) and [re-exit](docs/milestone2-codex-reexit-review.md) supersede.
- **Milestone 2 exit — DONE, PASS_WITH_LIMITATIONS:** [new post-Codex independent-exit review](docs/milestone2-codex-reexit-review.md) records original P1 failures and repaired exact-head plus merged-main 277-test CI, required Node, isolated wheel F1/F2 attacks and Codex fix PR code review without major findings. Earlier [invalidated PASS](docs/milestone2-exit-review.md) remains preserved for traceability; v0.1.0 is not publicly released.
- **Cross-cutting before M2 DONE:** installed-wheel/outside-checkout CI smoke, an explicit v0.1 FIT/GPX support matrix, explicit quality-policy ownership, and release documentation for quality/gap limitations.

Any schema need that would change a frozen invariant must trigger a new/superseding ADR rather than an implementation shortcut. Any proposed change to this checkpoint order or Milestone 2 scope must update this roadmap before implementation. M3 owns durable evidence custody/integrity after ingestion; M5 owns source-adapter acquisition provenance/authenticity only where mechanically supported.
