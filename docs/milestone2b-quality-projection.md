# M2B — deterministic quality projection and gap verification

> **ORIGINAL ACCEPTANCE REPAIRED AND RE-ACCEPTED:** independent Codex audit of M2 exit invalidated the historical M2B 0.1.0 acceptance: equivalent nonmaximal adjacent `usable_intervals` bypassed verifier and split M2D TargetSegments. Versioned `QualityAlgorithm 0.1.1` now independently enforces maximal canonical admitted runs. Source/installed-wheel F1 adversarial tests and [fresh M2 re-exit](milestone2-codex-reexit-review.md) passed after reviewed PR #18. The original M2B implementation-era statuses below are historical only.

**Status:** implementation handoff for independent review. ROADMAP remains M2B ACTIVE; M2C is NOT STARTED.

**Base:** remote main `05e96912a605d6ed6d4e2af2c9561d851ef8ec69`. Both M2A merge `f22b060c8df93d8442e2dab3bf1ec3462d53cee0` and the sequencing commit are ancestors. Branch: `codex/m2b-quality-projection`.

## Objective and ownership

Implement exactly the [M2B checkpoint](../ROADMAP.md): deterministic track-quality validation, supporting QualityProjection, explicit source/quality gaps, optional independently supported constraints and an independent verifier. The six frozen schemas and M0/M1 semantics are unchanged; no superseding ADR is required for this supporting value already authorized by [the quality interface](quality-layer-interface.md) and ADR-0002.

| Owner | Responsibility |
|---|---|
| `quality_models.py` | Frozen dataclass values, explicit policy and deterministic detached serialization |
| `quality.py` | Per-original-edge quality decisions, same-part admission runs, exclusions and explicit gaps; opt-in domain proof claims |
| `quality_verifier.py` | Independent edge coverage/order, decisions, evidence references, required gaps and proof verification |
| `_quality_evidence.py` | Shared input boundary checks and fingerprinting, with no quality decision or output construction |
| `_quality_numerics.py` | WGS84 physical-distance primitive and exact UTC-duration primitive |
| `__init__.py` | Public `project_quality`, `verify_quality`, QualityPolicy and result types; existing M2A API retained |

The verifier does not import the producer. Input validation and numerical primitives are shared, while edge accounting, quality decisions and gap/proof checks are independently implemented. Hand-built claims are tested with producer/decision functions patched to raise if called. Shared distance mathematics is independently tested against the equatorial WGS84 analytic arc and antipodal reference distance.

## API and supported evidence

```python
from target_area_route_reconstruction import (
    ingest_file, project_quality, verify_quality, QualityPolicy,
)

evidence = ingest_file("activity.gpx", source_kind="gpx",
                       track_source={"id": "source", "revision_id": "r1"})
# Caller-owned screening policy; 100 m/s is an example, not a human speed cap.
policy = QualityPolicy(max_implied_speed_mps=100.0, include_domain_bounds=False)
result = project_quality(evidence, policy=policy)
if result.outcome == "produced":
    verification = verify_quality(result.projection, evidence, policy=policy)
    # Consume a claim only when verification.outcome == "valid".
```

Policy must be explicitly passed to both APIs. `QualityPolicy()` deliberately disables motion screening; it does not install a default physical threshold. The verifier takes the independently expected policy, so altering a serialized threshold/version cannot validate itself.

Input is the successful M2A `IngestionResult`: CanonicalTrack plus content hash, ordered diagnostics and original observation/source mappings. The supported normalizer is the committed ingestion version 0.1.0. Missing canonical evidence, unsupported normalization or inconsistent source evidence yields `quality_evidence_unavailable` with a stable issue, rather than an empty successful claim. There is no FIT/GPX reparsing in M2B.

Input checks recompute the documented M2A id/revision digest and reject in-place parent edits; check finite CRS84 coordinates; require every original observation mapping in exact order; account for FIT positioned/missing Record indices; and validate continuity-diagnostic neighbors against source order. All inter-part boundaries need M2A supporting diagnostics. M2B does not accept an arbitrary schema-valid CanonicalTrack without this evidence bundle.

`evidence_digest` is SHA-256 of the entire deterministic M2A serialization, including mappings and diagnostics. It binds the claim to a supplied snapshot. It is not an authentication signature: the caller must supply trusted ingestion evidence and maintain raw-source custody. M2B does not authenticate a forged replacement source bundle or implement persistence.

## Exact value/serialization structure

QualityProjection owns no identity or evidence. All produced nested values are frozen dataclasses and tuples; JSON snapshots are detached. `to_json()` sorts keys, uses fixed compact separators, and rejects non-finite numbers. Tuple arrays serialize as JSON arrays. No time, randomness, filesystem path or unordered set enters output.

| Field | Serialized meaning |
|---|---|
| `canonical_track` | `{id, revision_id}` of the exact unchanged parent |
| `algorithm` | `{name, version, parameters}`; parameters contain full policy, distance method/guard and temporal method |
| `evidence_digest` | Fingerprint of the independently supplied M2A snapshot |
| `usable_intervals` | Ordered `{start, end}` parent TrackPositions |
| `excluded_intervals` | Ordered `{interval, reason, observation_source_indices}`; algorithm provenance is inherited from the projection |
| `gaps` | Ordered `{canonical_track, start, end, kind, causes, diagnostic_indices, excluded_interval_index, state}` |
| `gap_constraints` | Optional claims serialized as an array; an empty array means no constraint |
| `diagnostics` | Ordered per-edge `{interval, code}` for rules that could not establish an admission/exclusion result |

Every TrackPosition reuses M2A's `(part_index, observation_index, fraction_to_next)` value. This first algorithm classifies whole candidate edges, so projection positions have fraction 0. Valid fractional parent positions remain part of the frozen domain but are unsupported quality ranges in this version (`WHOLE_EDGE_RANGE_REQUIRED`). M2B does not establish a second coordinate array or compact indices.

Result states are `produced` or `quality_evidence_unavailable`. Verification states are `valid`, `invalid`, or `quality_evidence_unavailable`. For each structurally valid gap, constraint checking returns `unavailable`, `unsupported`, `invalid`, or `verified`. Early structural failures return no constraint statuses; they authorize no gap interpretation. A gap's route remains `unresolved` even with a verified domain bound.

## Candidate edges and interval rules

The spatial edge universe is exactly each original same-part `obs[i] -> obs[i+1]`. There is no cross-part edge. A singleton part has no candidate edges. Repeated and zero-distance observations still form candidate edges and are never removed.

Every edge is admitted or excluded exactly once. The producer coalesces adjacent admitted edges only within their original part and flushes a run on rejection. Exclusions are individually represented as one original edge for exact reason/source attribution. Usable and excluded interiors never overlap; adjacent intervals may share their original endpoint. Verification independently enumerates original `(part, edge)` identities and rejects omissions, duplicate accounting, overlap, reversal, wrong order and cross-part ranges. Geometry equality cannot establish any of these facts.

For the committed GPS-jump input, observations 0,1,2,3 remain intact. With the explicit test policy 100 m/s, usable intervals are `(0,0)->(0,1)` and `(0,2)->(0,3)`; `(0,1)->(0,2)` is excluded. Its two source mapping indices remain 1 and 2. Nothing connects observation 1 to 2 downstream.

## First quality algorithm and numerical policy

Algorithm: `target-area-route-reconstruction.quality`, version **0.1.0**.

Exact serialized parameters:

```json
{
  "policy": {"max_implied_speed_mps": null, "include_domain_bounds": false},
  "distance_method": "geographiclib-2.1-wgs84-inverse",
  "distance_roundoff_guard_m": 0.000001,
  "temporal_method": "exact-utc-seconds-fraction-v1"
}
```

The example above disables the motion rule. When enabled, `max_implied_speed_mps` must be an explicit finite positive binary64 number in metres per second. The test policy uses 100.0; it separates the committed fixture's ordinary and jumping edges without claiming a physiological limit.

For a candidate edge with two supported strictly increasing UTC instants, calculate WGS84 shortest endpoint geodesic distance `d` and exact elapsed seconds `dt`. Exclude only when `d - 1e-6 m > max_implied_speed_mps * dt`. The multiplication/comparison uses exact rational representations of binary64 parameters/results and exact timestamp fractions. No division or derived speed output is serialized.

The shortest distance supplies minimum endpoint displacement for screening. It does not assert the traversed route was that geodesic, change canonical interpolation, or establish any gap reachability constraint. A result below threshold proves only admission under this screening policy; it is not exhaustive GPS reliability certification.

Runtime dependency **`geographiclib==2.1`** is pinned in `pyproject.toml`. The standard library lacks a robust WGS84 inverse solver, existing Shapely is a development-only planar fixture tool, and an ad-hoc spherical approximation would introduce a different unreviewed model. GeographicLib is a maintained small pure-Python implementation of Karney's ellipsoidal algorithm, handles antimeridian/polar/antipodal cases, and installs as a platform-independent wheel. Its [documented WGS84 roundoff accuracy](https://geographiclib.sourceforge.io/html/python/geodesics.html#accuracy) is about 15 nm. The 1 micrometre comparison guard conservatively exceeds that computational roundoff; it is not a GPS accuracy bound or minimum geometry length.

If the threshold falls within the distance guard, retain the edge with `SPEED_NUMERICALLY_INDETERMINATE`; do not claim the rule passed. No coordinate epsilon discards short geometry. Even when a 1e-200 degree displacement rounds to zero in physical-distance arithmetic, its original edge and coordinates survive. This policy is distinct from [M1's planar clipping policy](numerical-policy.md).

Missing timestamps, non-increasing times, unsupported UTC/leap-second representations, unavailable distance or a disabled policy leave the motion rule unassessed. They retain the spatial edge and emit a precise diagnostic. Order is never sorted by timestamp. UTC fractional seconds beyond microseconds are preserved as exact fractions; unrepresentable durations remain unsupported rather than fabricated. Optional device speed/distance telemetry never supplies a missing timestamp or physical cap.

Future changes to rules, distance implementation/model/guard, temporal interpretation, default decisions, range/gap construction, proof semantics or material serialized parameters require a quality algorithm-version bump (and proof-version bump where applicable). The six schema versions remain 0.1.0.

## Gaps and provenance

Source gaps group M2A continuity/missing/empty-part diagnostics by their exact previous/next parent-position pair. Every original diagnostic index remains referenced in encounter order; causes are distinct codes in encounter order. The fingerprint resolves each index to its exact SourceLocation, including FIT Record indices and GPX track/segment locations.

This preserves multiple missing-position Records, leading/trailing runs and empty GPX parts. Leading or trailing gaps have one absent endpoint. GPX boundaries and FIT missing runs may yield adjacent canonical parts, including singleton parts, without creating any edge between them. Source absence is never recorded as a quality exclusion.

Each quality-excluded edge has one separate `quality_exclusion` gap referencing its exact excluded-interval index, original endpoints and reason. That index addresses supporting metadata, not a rewritten observation array. A missing gap or a fake gap covering an admitted edge is invalid. Quality algorithm/version is inherited from the containing projection. Every gap remains unresolved and contains no invented intermediate geometry.

## Gap proof model

The only supported proof is **`crs84-domain`, version `1`**. Its independent basis is the frozen core 0.1.0 OGC:CRS84 coordinate contract. The claim contains its gap index, exact parent, M2A evidence digest, proof method/version, `{coordinate_contract: "core-0.1.0-OGC:CRS84"}`, and a DomainBound `{spatial_reference: "OGC:CRS84", bbox: [-180,-90,180,90]}`.

The verifier requires the exact complete domain and contract, correct gap/parent/evidence, finite numbers, ordered unique gap references, and the expected opt-in policy. A smaller local rectangle is not this proof. Unsupported methods fail explicitly; they are never ignored or substituted. No constraints are generated by default. When `include_domain_bounds=True`, this deterministic producer supplies one domain claim for each gap and the verifier requires that exact policy behavior.

This bound proves only that route coordinates represented under the frozen contract belong to the complete canonical coordinate domain. It does not bound elapsed motion locally, recover any path, prove where within the domain movement occurred, or resolve the gap. Its utility is deliberately tautological, matching M1's full-domain witness. It cannot be tightened using endpoints or a quality threshold.

Local physical reachability, endpoint buffers, observed-average-speed bounds, road/path matching, historical route similarity, inferred timer/movement rules and unique missing-route reconstruction remain **unsupported**. Short gaps without independently verifiable evidence serialize exactly as unresolved gaps with unavailable constraints. A future proof method needs independent evidence, explicit assumptions, versioned parameters, an independent verifier and positive/adversarial tests before acceptance.

## Stable codes

Producer exclusion reason: `IMPLIED_SPEED_EXCEEDS_POLICY`. Producer rule-unavailability diagnostics: `SPEED_RULE_DISABLED`, `SPEED_TIME_MISSING`, `SPEED_TIME_NONINCREASING`, `SPEED_TIME_UNSUPPORTED`, `SPEED_DISTANCE_UNAVAILABLE`, `SPEED_NUMERICALLY_INDETERMINATE`.

| Failure family | Stable codes |
|---|---|
| Input/policy | `QUALITY_POLICY_INVALID`, `QUALITY_EVIDENCE_UNAVAILABLE`, `QUALITY_EVIDENCE_INVALID`, `QUALITY_EVIDENCE_UNSUPPORTED`, `PARENT_CONTENT_REVISION_MISMATCH`, `SOURCE_MAPPING_INVALID`, `SOURCE_GAP_EVIDENCE_INVALID`, `SOURCE_GAP_EVIDENCE_MISSING` |
| Projection/parent/algorithm | `PROJECTION_MALFORMED`, `PARENT_REFERENCE_MISMATCH`, `EVIDENCE_REFERENCE_MISMATCH`, `ALGORITHM_CONTRACT_MISMATCH` |
| Position/range | `TRACK_POSITION_INVALID`, `TRACK_POSITION_OUT_OF_BOUNDS`, `WHOLE_EDGE_RANGE_REQUIRED`, `INTERVAL_CROSS_PART`, `INTERVAL_REVERSED_OR_EMPTY`, `INTERVAL_ORDER_INVALID`, `INTERVAL_OVERLAP`, `EXCLUSION_MUST_BE_ONE_EDGE` |
| Accounting/decision | `EDGE_UNACCOUNTED`, `EDGE_DOUBLE_ACCOUNTED`, `EDGE_DECISION_MISMATCH`, `EXCLUSION_REASON_INVALID`, `EXCLUSION_EVIDENCE_MISMATCH`, `QUALITY_DIAGNOSTICS_MISMATCH` |
| Gap | `GAP_PARENT_MISMATCH`, `GAP_STATE_INVALID`, `GAP_ORDER_INVALID`, `GAP_PROVENANCE_MISMATCH`, `GAP_KIND_UNSUPPORTED`, `REQUIRED_GAP_MISSING` |
| Constraint | `CONSTRAINT_GAP_REFERENCE_INVALID`, `GAP_CONSTRAINT_UNSUPPORTED`, `CONSTRAINT_EVIDENCE_MISMATCH`, `CONSTRAINT_PARAMETERS_MISMATCH`, `CONSTRAINT_BOUND_INVALID`, `CONSTRAINT_BOUND_PROOF_MISMATCH`, `CONSTRAINT_POLICY_MISMATCH` |

Issues include deterministic structural paths where applicable. Rejection tests assert expected codes; arbitrary prose or “some exception” cannot satisfy them. Malformed dataclass claims return `PROJECTION_MALFORMED`; known non-finite bounds retain their specific failure code rather than losing it to subsequent JSON serialization.

## Tests, mutations and self-adversarial review

`tests/test_quality_projection.py` covers all six committed metric input classes, all 12 raw-baseline outcomes through unchanged M2A, explicit GPX/empty-part boundaries, FIT single/multiple/leading/trailing missing Records, repeats/zero edges, singleton parts, tiny geometry, valid/missing/non-increasing temporal evidence, determinism, exact fractional seconds and distance behavior. No real personal tracks are introduced; existing anonymized M0 evidence remains design rationale, not claimed production acceptance data.

Independently constructed claims attack wrong/stale parent, in-place parent edits, omitted and duplicate edges, order/overlap, cross-part/reversed/fractional/out-of-bounds ranges, compacted indices, fake/missing gaps, erased missing-record provenance, altered source mappings, wrong exclusion reasons, algorithm/parameter changes, dropped unavailable diagnostics, unsupported proof methods, stale proof evidence, non-finite/local bounds and proof/reference mismatches.

Three actual producer source mutations in disposable package copies must fail unchanged positive integration witnesses: retain a usable run through a rejected edge; drop FIT source-gap creation; collapse GPX parts into one usable range. These tests require assertion failures, not import/runtime crashes. The existing M1 and two M2A continuity mutations remain mandatory.

Before staging, self-review checks every rejected/missing edge cannot be exposed through a usable interval; all source gap provenance survives; exact parent indices and repeated observations remain; omissions/double accounting/revisions/unsupported proofs fail; missing time causes no spatial rejection; thresholds remain explicit; bounds contain no inferred centerline. Production searches find no TargetArea/SpatialAssessment/TargetSegment dependency or reconstruction object. No frozen schema, prior fixture expectation, parser implementation or M2C behavior is changed.

## Validation record

CI-equivalent local environment: Python 3.11.16, jsonschema 4.26.0, Shapely 2.1.2 / GEOS 3.13.1, fitdecode 0.11.0, lxml 6.1.3 and GeographicLib 2.1, installed from current `requirements-dev.txt`.

| Command | Result |
|---|---|
| `python -m unittest discover -s tests -p 'test_quality_projection.py' -v` | PASS: 49 focused M2B tests |
| `python -m unittest discover -s tests -p 'test_*.py' -v` | PASS: 113 tests: 25 M1 + 39 M2A + 49 M2B |
| `python scripts/validate_schema_fixtures.py --verbose` | PASS: 260/260 expectations |
| `python scripts/validate_semantic_fixtures.py --verbose` | PASS: 56/56 expectations |
| `python scripts/validate_edge_case_coverage.py` | PASS: 29/29; six negatives; 13 owned non-file contracts |
| `python scripts/validate_source_fixture_baseline.py` | PASS: 12/12; two equivalence groups |
| `git diff --check` | PASS: clean M2B diff |

Wheel build and isolated Python 3.11 runtime installation passed, using only fitdecode 0.11.0, lxml 6.1.3 and GeographicLib 2.1. Outside the checkout, the installed wheel passed ingestion, quality projection, opt-in domain proof and verifier smoke checks. The existing PR CI workflow installs the pinned runtime dependency through `requirements-dev.txt` and discovers the new tests automatically; remote results accompany the final PR head. Counts enumerate tests/registered representations and do not substitute for the explicit invariant/mutation evidence above.

## Known limits and M2C handoff

M2B screens only explicit implied endpoint motion and source continuity. It does not identify every GPS anomaly, infer a universal quality threshold, decide observation accuracy, or authenticate raw evidence independently of trusted M2A. Motion-rule availability is explicit; admitted edges with unavailable screening are not certified against that rule. Only whole-edge quality decisions and this M2A normalizer version are supported.

M2C must first verify the projection against exact parent/evidence and expected policy, retain its original TrackPositions, consume only admitted same-part intervals, and preserve unresolved gaps/diagnostics. A verified domain envelope is not recovered geometry. Local-area gap claims need additional independently supported proof methods. Target-relative relation/completeness interpretation belongs exclusively to M2C and must fail closed when current evidence is insufficient.

M2B creates no spatial assessments/segments, speed/pace outputs, GeoJSON, map, route matching, acquisition adapter, persistent store or migration. M2C–M2F and M3+ retain ROADMAP ownership. Independent acceptance decides M2B completion; this implementation does not declare a final pass.
