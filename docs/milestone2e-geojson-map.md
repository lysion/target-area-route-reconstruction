# M2E — Verified GeoJSON export and basic interactive map

**Status:** ACTIVE — first GeoJSON export slice implemented on `codex/m2e-geojson-map`; M2E not DONE. Initial offline interactive SVG map implemented; independent review and expanded adversarial coverage still pending.

**Baseline:** M2D PR #8 independently accepted and merged; ADR-0012 Accepted; M2A–M2D are DONE. M2E does not change any frozen core schema, evidence/revision policy or spatial classification.

## Objective

Deliver a usable, audit-friendly, reproducible local path:

`FIT/GPX → CanonicalTrack → QualityProjection → verified SpatialRelationProof → verified SpatialEntityBundle → GeoJSON → interactive map`.

The export/view layer displays spatial facts established upstream. It cannot become an alternative classification, interpolation or missing-route reconstruction engine.

## Input authority and API

First production slice:

`export_geojson(bundle, proof, evidence, quality_projection, quality_policy, target_area, target_reference, include_outside=True)`

Returns immutable `GeoJSONExportResult(outcome, geojson_json, issues)` with `produced`, `invalid_input` or `export_failure`. No invalid input can turn into empty successful coverage.

The exporter first independently verifies M2C `SpatialRelationProof` against the exact evidence, quality policy, TargetArea and reference, and then requires `verify_spatial_entities(...)=valid`, including the accepted ADR-0012 canonical snapshot policy. A non-assessable, verified proof and `bundle=None` may export only the TargetArea and real diagnostics, with null relation/completeness; it must not fabricate an `outside` assessment.

Do not treat a merely schema-valid JSON entity or GeoJSON representation as spatial authority. M2E's own GeoJSON is a downstream, derived visualization artifact, not a seventh core entity.

## Deterministic feature layers

Features are generated in fixed order:

1. `target_area` — exact source TargetArea Polygon/MultiPolygon, including holes;
2. `target_segment` — one distinct ordered Feature per accepted M2D TargetSegment, preserving LineString vertex sequence, ordinal, revision references and parent TrackPosition lineage;
3. optional `observed_outside` — per-M2C original outside interval geometry regenerated from its exact parent TrackPositions; it is diagnostic context, not a merged path;
4. `gap_endpoint` — Point only at each **actually observed** leading/trailing neighbor of a verified M2C gap. No gap line, chord, inferred shape, fabricated start/end or phantom position may ever be produced.

The RFC 7946 FeatureCollection includes a documented `metadata` foreign member with the exact parent/target/assessment references, M2D relation/completeness (or null for non-assessable), gaps with source/quality kind and real nullable TrackPosition neighbors, and an explicit warning that missing route portions are not geometries.

`include_outside` is a strict boolean controlling only diagnostic outside geometry. No omitted outside feature changes relation, completeness or TargetSegment membership.

## Basic interactive map — first implementation slice

Build a lightweight interactive HTML map from **accepted** GeoJSON:

- preserve each independent Feature; no simplification, snapping, geometry union, map matching, route interpolation, gap chord or straight-line connection across missing observations;
- show TargetArea outline/fill, inside segments, optional outside context, and observed gap endpoints with distinct legend/layer controls;
- label and display `relation` separately from `coverage_completeness`, with explicit warnings for `unknown` and `incomplete`;
- display gap kind, number and target relevance without inventing a path;
- allow zoom/pan and basic inspection of ordered segment references/provenance;
- work for ordinary local coordinates without requiring a proprietary remote map API; if an optional basemap is unavailable, the vector data remains visible;
- keep output reproducible and avoid external injection by safely serializing or escaping untrusted provenance in generated HTML;
- do not implement metrics/speed/pace/quality coloring (M2F), persistence (M3), source adapters (M5), missing-route reconstruction (M7), historical network (M8), or new CRS/date-line behavior (deferred);
- do not label the resulting map as a complete historical route network.

## Acceptance gates before M2E DONE

- stable GeoJSON FeatureCollection semantics; exactly all M2D-confirmed TargetSegments, each original occurrence separately traceable;
- zero geometry created across source gaps, quality exclusions or unobserved intervals;
- leading/trailing nullable gaps yield only actual endpoint point features, with no fake neighbor;
- invalid/stale or duplicate-key M2D snapshots cannot become valid GeoJSON;
- incomplete/unknown/non-assessable statuses remain truthful in data and map;
- explicit duplicate, omitted, reversed and cross-gap mutation witnesses, schema/semantic compatibility and isolated installed-wheel checks;
- hostile HTML/JSON characters from provenance cannot inject scripts;
- polygon holes, MultiPolygon, boundary overlap, repeated vertices/visits, optional outside, no-segment and no-assessment scenarios;
- at least one HTML/map interaction smoke check; independent reviewer approval and green final-head CI;
- ROADMAP M2E marked DONE only after independent acceptance/merge. M2F remains NOT STARTED.

## Known limitations

M2B supplies no useful local gap-reachability bound; no inferred centerline can be plotted. M2C's longitude interpolation is planar CRS84, including 179°→−179° linearly, not geodesic/periodic; map rendering must not silently reinterpret it as a newly proven route. No persistent dataset/revision index exists before M3.

This document is a milestone implementation record, not permission to change the frozen six-entity contract.

## Initial map implementation

`render_geojson_map(geojson_json, title=...)` produces self-contained HTML with an interactive SVG vector viewport, pan/zoom/reset, layer visibility and per-feature provenance inspection. No remote basemap or network dependency is required. JSON provenance is escaped in the inert application/json script and only rendered into the DOM via textContent. SVG elements are constructed from coordinate arrays, not untrusted HTML. The map is not a substitute for verified export authority: callers should render only the result of `export_geojson`. The first map smoke tests do not yet constitute the independent M2E acceptance gate.
