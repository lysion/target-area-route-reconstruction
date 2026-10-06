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

## Draft domain model

The current evidence-backed model centers on six entities:

- **Activity** — a real-world activity event.
- **TrackSource** — original source evidence and provenance.
- **CanonicalTrack** — normalized observations with explicit spatial continuity.
- **TargetArea** — a versioned Polygon/MultiPolygon assessment target.
- **SpatialAssessment** — the evidence-aware relation between a canonical track and target-area version, including target-coverage completeness.
- **TargetSegment** — an ordered, traceable maximal covered portion of a canonical track.

The evidence-backed domain decisions are documented in [docs/domain-model.md](docs/domain-model.md) and the ADRs under [docs/decisions/](docs/decisions/). No blocking domain-design question remains; Milestone 0 is pending full edge-case regression and contract freeze.

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
- [Evidence plan](docs/evidence-plan.md)
- [Real-world evidence record](docs/real-world-cases.md)
- [Track metric overlays](docs/track-metric-overlays.md)

## Status

Early public development. The repository is currently in **Milestone 0: Domain Contract**. Representative evidence, controlled attacks, cross-source identity semantics, coverage-completeness semantics, and manual-decision audit semantics are now incorporated into the domain model and ADRs. The remaining Milestone 0 work is the full edge-case regression and v0.1 contract freeze.
