# Target Area Route Reconstruction

A deterministic local FIT/GPX toolkit for evidence-aware target-area track assessment, GeoJSON export and interactive visualization. This is a foundation for a future agent skill—not an already packaged skill or multi-activity historical route network.

## Problem

Historical activity data is often split across platform metadata, FIT/GPX files, API streams, and local exports. A reliable reconstruction workflow should be able to:

1. discover historical activities;
2. resolve and ingest available track sources;
3. normalize tracks into a stable internal representation;
4. validate track quality;
5. assess each track against a target area;
6. extract the portions that belong to the target area; and
7. produce auditable route datasets and maps.

The core design intentionally separates platform access, file formats, acquisition constraints, and visualization from the domain model.

## v0.1 scope

The first release is deliberately narrow:

- local FIT and GPX inputs;
- an explicit target area;
- canonical track normalization;
- track-quality validation;
- spatial classification as `inside`, `partial`, `outside`, or `unknown`;
- extraction of target-area segments;
- GeoJSON export;
- a basic interactive map;
- optional quality-aware speed/pace coloring when valid temporal evidence is available.

The following are deferred until the deterministic core is stable:

- COROS, Garmin, Strava, or other platform adapters;
- acquisition quota/cost optimization;
- route-network aggregation and heatmaps;
- training-performance or physiological analysis beyond local track speed/pace visualization;
- route recommendation.

## v0.1 domain model

The current evidence-backed model centers on six entities:

- **Activity** — a real-world activity event.
- **TrackSource** — original source evidence and provenance.
- **CanonicalTrack** — normalized observations with explicit spatial continuity.
- **TargetArea** — a versioned Polygon/MultiPolygon assessment target.
- **SpatialAssessment** — the evidence-aware relation between a canonical track and target-area version, including target-coverage completeness.
- **TargetSegment** — an ordered, traceable maximal covered portion of a canonical track.

The evidence-backed domain decisions are frozen in [docs/domain-model.md](docs/domain-model.md) and ADR-0001 through ADR-0010 under [docs/decisions/](docs/decisions/). Milestone 0 is complete.

## Development approach

Development follows a contract-first and test-first sequence:

1. freeze the v0.1 domain contract;
2. encode schemas and edge-case fixtures;
3. implement deterministic parsing and spatial analysis;
4. add persistence, idempotency, and resume behavior;
5. package the workflow as an agent skill;
6. add source adapters and higher-level route reconstruction.

See [ROADMAP.md](ROADMAP.md) for milestone gates, exit criteria, and change-control rules.

Current design artifacts:

- [Domain model](docs/domain-model.md)
- [Architecture decisions](docs/decisions/)
- [Edge cases](docs/edge-cases.md)
- [Milestone 0 edge-case regression](docs/edge-case-regression.md)
- [Milestone 0 contract freeze review](docs/contract-freeze-review.md)
- [Shared schema conventions](docs/schema-conventions.md)
- [Schema workspace](schemas/README.md)
- Executable schema validation: `python scripts/validate_schema_fixtures.py`
- Executable semantic validation: `python scripts/validate_semantic_fixtures.py`
- [Milestone 1 linked semantic scenario coverage](docs/milestone1-linked-scenario-coverage.md)
- [Milestone 1 complete edge-case coverage](docs/milestone1-edge-case-coverage.md)
- [Milestone 1 validation run](docs/milestone1-validation-run.md)
- [Milestone 1 exit review](docs/milestone1-exit-review.md)
- [Synthetic raw source fixtures](tests/source-fixtures/README.md)
- Raw source fixture validation: `python scripts/validate_source_fixture_baseline.py`
- Edge-case coverage validation: `python scripts/validate_edge_case_coverage.py`
- [Evidence plan](docs/evidence-plan.md)
- [Real-world evidence record](docs/real-world-cases.md)
- [Track metric overlays](docs/track-metric-overlays.md)
- [Normalized evidence / quality interface](docs/quality-layer-interface.md)
- [Numerical policy](docs/numerical-policy.md)
- [M1 remediation and before/after evidence](docs/milestone1-remediation.md)
- [M1 fresh re-exit review](docs/milestone1-re-exit-review.md)
- [M2A deterministic canonical ingestion](docs/milestone2a-canonical-ingestion.md)
- [M2B quality projection and gap verification](docs/milestone2b-quality-projection.md)
- [M2C spatial relation and completeness proof](docs/milestone2c-spatial-relation.md)
- [M2D contract blocker history](docs/milestone2d-target-segments.md)
- [M2D deterministic entity assembly implementation](docs/milestone2d-implementation.md)
- [M2E verified GeoJSON and offline interactive map](docs/milestone2e-geojson-map.md)
- [M2F temporal metric overlay — prior acceptance; corrective review in progress](docs/milestone2f-temporal-overlay.md)
- [M2 independent cross-stage exit review — superseded historical PASS](docs/milestone2-exit-review.md)
- [M2 Codex P1 remediation and re-exit contract](docs/milestone2-codex-remediation.md)

## Status

Early public development. **Milestone 0: Domain Contract is DONE. Milestone 1: Schemas and Fixtures is DONE after adversarial remediation and re-review. Milestone 2: Deterministic Core is REOPENED after a later independent Codex audit found two P1 violations of the original exit claim.** See [M2 remediation and re-exit](docs/milestone2-codex-remediation.md); the earlier [PASS](docs/milestone2-exit-review.md) is historical. An independent audit of commit `141dc092f5a3c7845066156cafd26b3879e99137` invalidated the sufficiency of the previous green oracle. The ordered-interval oracle, reason-specific negatives, mutation regressions and independent raw-source checks passed branch CI before PR #1 was merged. See [the fresh re-exit review](docs/milestone1-re-exit-review.md). The [historical exit review](docs/milestone1-exit-review.md) and [remediation record](docs/milestone1-remediation.md) preserve the original PASS and reopening. [M2A ingestion](docs/milestone2a-canonical-ingestion.md) is DONE after independent review and merge. [M2B quality projection](docs/milestone2b-quality-projection.md) is DONE after independent review and merge. [M2C spatial relation/completeness proof](docs/milestone2c-spatial-relation.md) is DONE after independent review and merge of PR #4. It produces a supporting proof, including explicit non-assessability, rather than a SpatialAssessment entity. [M2D TargetSegment extraction and SpatialAssessment assembly](docs/milestone2d-implementation.md) is DONE after independently accepted PR #8 was merged. ADR-0011 repaired leading/trailing uncertainty and ADR-0012 accepted the canonical-snapshot verification policy; historical blockers remain documented. See [the implementation record](docs/milestone2d-implementation.md), [accepted snapshot policy](docs/decisions/0012-m2d-canonical-assembly-snapshots.md), and [tested support boundaries](docs/v0.1-support-boundaries.md). [M2E GeoJSON/basic interactive map](docs/milestone2e-geojson-map.md) is DONE after independent source-and-adversarial-evidence re-review of the final head, green CI, and merged [PR #11](https://github.com/lysion/target-area-route-reconstruction/pull/11). [M2F validated temporal speed/pace and quality-aware map coloring](docs/milestone2f-temporal-overlay.md) is DONE after final-head CI [37779156527](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37779156527), independent [PASS re-review](https://github.com/lysion/target-area-route-reconstruction/pull/13#pullrequestreview-5456795395) and merged PR #13. M2B quality partition and M2D maximality (F1), and M2F per-edge screening representation (F2), are under corrective re-review in PR #18. Prior checkpoint PASS labels and the M2 exit report are historical, NOT current acceptance. M3 is NOT STARTED. No v0.1.0 tag, PyPI distribution or end-user skill release is claimed.
