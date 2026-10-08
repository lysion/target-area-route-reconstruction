# M2F — Valid temporal speed/pace and quality-aware map coloring

**Status:** ACTIVE — initial API, temporal tests and offline vector map overlay under review; NOT DONE.

**Entry evidence:** M2E PR #11 merged and accepted, M2E closeout PR #12 merged; M2A–M2E DONE on main. No schema, M2C relation, M2D revision or M2E verified export changes are authorized in M2F.

## Objective

Derive speed and pace only for observed, M2B-quality-admitted, strictly time-valid parent edge fragments belonging to already verified M2D TargetSegments. Preserve every accepted spatial feature even if its temporal evidence is missing or invalid. Project the derived metrics to optional per-edge GeoJSON features and render them in the M2E offline map with a neutral unavailable state and explicit layer/mode controls.

## API and ownership

`export_temporal_geojson(bundle, proof, evidence, quality_projection, quality_policy, target_area, target_reference, metric_mode="speed_mps", include_outside=True)` returns `GeoJSONExportResult`. It **first calls `export_geojson`**, which checks exact M2C and immutable M2D authority. It cannot accept a stale or forged bundle merely because its coordinates look plausible.

The output is a downstream **derived visualization**, not a seventh entity. No new core schema version, persistence key or time interpolator is added to M2A–M2D. The algorithm identity is `target-area-route-reconstruction.temporal-overlay/0.1.0`.

## Derivation policy

- Each existing M2D TargetSegment is broken into original parent observation-edge intervals with original start/end fractional positions. It must preserve occurrence, source part and edge lineage.
- Speed and pace are derived from observed CRS84 coordinates using GeographicLib WGS84 inverse distance. Original timestamp strings are interpreted via the accepted exact UTC temporal parser; BOTH original endpoints must exist and have strictly increasing timestamps.
- For a TargetSegment clipped to a strict subinterval of one parent edge, fractional elapsed time is proportional to that same parent edge's positive elapsed UTC. No timestamps are invented from adjacent edges or across gaps.
- The metric status is `valid` only when original time and duration are valid. Missing, unsupported, non-increasing or numerically unavailable times yield null metrics and a reason code, never a synthesized value.
- Stationary zero-distance subintervals keep their elapsed-time diagnostic in `metadata.temporal_overlay.stationary_observations` but do not fabricate positive-length LineStrings. Their speed may be 0 m/s with valid elapsed time; pace is undefined (null).
- No smoothing, implicit speed plausibility threshold, rolling average, resampling, device speed substitution, route matching or time interpolation across any continuity/quality/source gap. Existing M2B policy is caller-owned and must not be silently tightened.
- A parent edge with a planar CRS84 longitude jump >180 degrees has `planar_dateline_ambiguous` metric status (null speed/pace) rather than silently changing M2C's planar/periodic assumptions. Existing geometry remains visible.
- A valid speed is a geometrically derived number under explicit quality admission, **not certification of GPS accuracy or true athlete speed**.

## GeoJSON and map

Unchanged M2E features remain first and identical; additional `target_metric_edge` LineStrings are entirely subsets of already verified TargetSegment vertices, one per positive observed parent fragment. Each feature exposes parent edge, ordinal, fractional start/end, algorithm/version, metric reason code, derived distance/duration/speed/pace; unavailable values are null.

Map display colors only temporally valid, numerically finite metric fragments; unavailable time is neutral **gray dashed**, not borrowed from nearby good edges. Display color buckets are purely visual, **never an M2B quality filter**. `speed_screen` is recorded as `not_screened` or `explicit_m2b_policy_enabled` together with the caller's speed cap (or null). Time-valid unscreened fragments are rendered **blue dashed**, and time-valid explicit-rule-enabled fragments **blue solid**; neither is a claim of GPS truth. The visible map warning explicitly states when the speed rule is disabled. An explicit mode controls speed vs pace; a numerical/unit-bearing legend states boundaries 1.5/2.5/3.5/4.5 m/s and equivalent reciprocal min/km boundaries, with the explanation that reciprocal speed and pace preserve interval color. A layer checkbox allows the metric overlay to be hidden without removing accepted spatial evidence. No inferred or gap geometry is generated.

## Required completion gates

- Known constant-speed, acceleration/deceleration, clipped fractional interval, pause, missing and non-increasing time, cross-part source gap, quality exclusion and non-assessable cases;
- valid time and invalid time coexist within the same M2D segment without speed bleeding;
- invalid M2C/M2D authority, stale revisions and illegal overlay mode cannot return success geometry;
- original TargetArea, relation, coverage completeness, missing gap markers and repeated TargetSegments remain immutable;
- Node JS execution checks actual metric coloring, neutral unavailable, pace mode and layer toggles without suppressing previous M2E interaction checks;
- isolated noneditable wheel must execute M2F projection and rendering on real FIT/GPX source fixtures, including intentionally missing temporal evidence;
- independent source/adversarial re-review on exact final head with full CI successful;
- only after PASS/merge mark M2F DONE and evaluate the full M2 exit criteria; do not label v0.1.0 released merely because CI is green.

## Deliberate deferrals

Derived per-edge speed/pace is not sophisticated GPS motion correction. Smoothing is optional in the earlier design note and is not a prerequisite for honest unsmoothed metrics. Persistent metrics (M3), aggregate route network analytics (M7/M8), true missing-path restoration, new local gap bounds, physiological analysis and cross-platform acquisition are outside M2F.

## Initial adversarial re-review and remediation (2026-10-08)

Review [5456683052](https://github.com/lysion/target-area-route-reconstruction/pull/13#pullrequestreview-5456683052) returned **CHANGES REQUIRED** against initial head `eb50e6eb9efd5dc9c4ed7c69277c41485352941e`, notwithstanding its green CI. Issues: implicit color confidence/undefined pace legend, absence of extreme temporal and GPS jump cases, and isolated wheel not testing a no-timestamps GPX.

Remediation on the same PR branch:

- Separate original-edge UTC validity from caller-owned M2B speed screening, serialize `speed_screen` and `speed_cap_mps`, and show a prominent warning when screening is absent. A numerically valid uncapped GPS jump can still produce an extreme number, but is never certified or visually indistinguishable from explicit-screened output.
- Display fixed numeric thresholds and inverse pace thresholds with units; blue dashed = no explicit speed screen, blue solid = explicit cap enabled, gray dashed = temporal/metric unavailable. Palette encodes relative numeric speed only; it is **not** a race speed/physiology assessment and does not silently reject implausible input.
- Test real quality-policy rejection of a GPS jump and the unscreened counterpart, equal/reversed timestamps, precise sub-microsecond UTC, extremely small unrepresentable positive duration, mixed valid/missing time in one contiguous segment, fractional clipping, and planar date-line non-equivalence.
- Extend isolated-wheel smoke to real `gpx/no-timestamps.gpx` and assert that valid observed spatial geometry yields only missing temporal values; require Node JS runtime tests for explicit-screened versus unscreened strokes, units and pace correspondence.

**Review gate remains open** until final-head CI and independent final re-review. PR #13 remains Draft and M2F stays ACTIVE, not DONE. The accepted M2E/M2D source contract is unchanged.
