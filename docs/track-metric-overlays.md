# Track Metric Overlays

This note records a planned extension to the deterministic core: visually encoding track metrics such as speed or pace along the route.

The capability is intentionally separated from the Milestone 0 domain contract.

## Scope

The first overlay metric will be speed/pace when valid temporal information is available.

The design must later remain extensible to other per-track metrics such as:

- elevation;
- grade;
- heart rate;
- cadence;
- power.

This is a visualization and derived-metric capability, not a training-performance analysis subsystem.

## Core design rule

Observed telemetry and derived metrics are different facts.

For example:

- device-recorded speed is **observed telemetry**;
- speed calculated from position and elapsed time is a **derived metric**.

They must not silently share one semantic field.

```text
TrackSource
    ↓
CanonicalTrack
  geometry
  optional timestamps
  optional observed telemetry
    ↓
Derived Track Metrics
  segment speed
  pace
  smoothing/quality state
    ↓
Track Metric Overlay
    ↓
Map rendering
```

## Why speed is not a required CanonicalTrack field

Target-area reconstruction remains valid for spatial tracks that do not contain timestamps.

Therefore:

- speed is not required for CanonicalTrack validity;
- missing timestamps must not invalidate spatial classification;
- speed/pace overlays are available only when evidence supports them.

## Segment semantics

Speed is naturally an interval property rather than a point property.

For adjacent valid positions:

```text
P0 -------- P1 -------- P2
      v01         v12
```

A future derived metric representation may contain fields such as:

```text
start track position
end track position
duration_s
distance_m
speed_mps
pace_s_per_km
quality
algorithm/version
```

The exact schema is not frozen in Milestone 0.

## Quality requirements

Raw adjacent-point speed must not be rendered without validation.

Potential distortions include:

- GPS drift;
- extreme position jumps;
- variable sampling intervals;
- pauses;
- tunnels or canopy-related signal loss;
- discontinuities between observed track parts.

The deterministic pipeline should conceptually follow:

```text
CanonicalTrack
    ↓
continuity / quality validation
    ↓
distance and time interval calculation
    ↓
invalid-interval rejection
    ↓
optional smoothing
    ↓
derived speed/pace profile
    ↓
metric overlay
```

Derived metrics must retain algorithm/version provenance if persisted.

## Relationship to TargetSegment

Metric overlays should work on both:

- the full CanonicalTrack;
- TargetSegment-derived views.

This allows a user to inspect either the whole activity or only the part relevant to the target area.

## Roadmap integration

### Milestone 0

No new core entity is introduced for speed.

Evidence collection for GPS discontinuity and outliers should record timing/distance anomalies that may later affect speed derivation.

### Milestone 1

Add representative temporal/metric fixtures, including:

- constant speed;
- accelerating/decelerating track;
- pause;
- GPS jump;
- discontinuity;
- no timestamps.

These fixtures are optional-capability fixtures and must not redefine minimum spatial-track validity.

### Milestone 2

Implement the first derived track metric pipeline:

- validated segment speed;
- pace;
- optional smoothing;
- map coloring by speed/pace.

This is part of the basic map capability when temporal evidence is available.

### Milestone 3

If derived metrics are persisted, record:

- algorithm name/version;
- source CanonicalTrack version;
- parameters;
- quality state.

### Milestone 7

Only after route-network semantics are stable should the project aggregate metrics across repeated route segments, for example:

- speed distributions on the same route section;
- longitudinal changes;
- repeated-section comparison.

## Non-goals

This note does not add:

- fitness scoring;
- physiological interpretation;
- training-load analysis;
- race-performance prediction;
- automatic route recommendation.

Those are outside the current project scope unless explicitly added by a later roadmap revision.
