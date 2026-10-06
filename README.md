# Target Area Route Reconstruction

A reusable agent skill and deterministic toolkit for reconstructing historical activity tracks within a specified geographic area.

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

The first milestone is deliberately narrow:

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
- Edge-case coverage validation: `python scripts/validate_edge_case_coverage.py`
- [Evidence plan](docs/evidence-plan.md)
- [Real-world evidence record](docs/real-world-cases.md)
- [Track metric overlays](docs/track-metric-overlays.md)

## Status

Early public development. **Milestone 0: Domain Contract is DONE** and the v0.1 domain contract is frozen. The project is now in **Milestone 1: Schemas and Fixtures**. Shared schema conventions and reusable common definitions are established. All six frozen v0.1 core entity schemas are implemented, with valid/invalid fixtures across Activity, TrackSource, CanonicalTrack, TargetArea, SpatialAssessment, and TargetSegment. Formal Draft 2020-12, independent semantic-validation, and edge-case-coverage runners are in place and executed by GitHub Actions. All EC-01 through EC-29 now have an explicit Milestone 1 representation: schema fixture, linked semantic scenario, or machine-readable non-file contract case. The current registry contains 113 fixture entries, 16 linked semantic scenarios, 13 non-file contract cases, and 6 negative cross-object cases, including 14 independent conformance probes for shared common definitions. Milestone 1 next focuses on validation conformance and exit review rather than additional domain/coverage design. The Milestone 0 regression finished with 26 PASS, 0 REVIEW, 0 FAIL, and 3 explicitly bounded DEFERRED cases.
