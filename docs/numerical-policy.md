# Numerical policy for the M1 reference oracle

`scripts/ordered_spatial_oracle.py` implements the fixture oracle's policy. It is a reference for M2 tests, **not** a production GIS engine, a geodesic distance model, or an independent exact-numeric verifier. The second independent Codex full-repository audit found R2-01 P1: the M1 GEOS oracle **shared** extreme-float clipping errors with M2C producer and verifier. The historical M2 PASS was reopened. The new separate [R2 exact-Fraction witness tests](../tests/test_m2_r2_numerical_gate.py) establish positive intersection without GEOS.

## Positive length and parent identity

Positive length means at least two distinct adjacent represented coordinates. No epsilon, buffer, minimum-distance cutoff or squared-length calculation defines it. `coordinate_length` uses `hypot`/`fsum` only to scale numerical comparison, avoiding avoidable underflow; it does not decide whether evidence exists. Both 5e-13 and 1e-200 degree tracks are regression inputs. Identical coordinates, singleton parts and vertex-only touches do not create positive-length coverage.

The oracle clips each existing observation edge against the target using planar CRS84 linear interpolation. GEOS identifies line intersection endpoints, including polygon holes and MultiPolygon boundaries. Fractions are recovered on the edge's dominant coordinate axis, avoiding distance-squared underflow and preserving exact observation endpoints at 0/1. Fraction 1 is serialized canonically as the next observation with fraction 0.

All identity, ordering and merging occurs in `(part_index, observation_index, fraction_to_next)` space. Only adjacent covered intervals in the same part can merge. Repeated zero-distance edges at the start, interior or end remain in maximal lineage. Geometry union, equality, Hausdorff distance and length equality are never completeness or lineage proofs.

## Binary64 comparison

Interpolation has one implementation shared by TrackPosition evaluation and segment regeneration. A regenerated segment retains its ordered observation vertices, including duplicates; this fixture serialization deliberately does not simplify or resample it.

For coordinate regeneration and endpoint comparison, the allowed error is the minimum of:

- 1e-12 CRS84 degrees (absolute cap);
- eight binary64 ULPs at the coordinate/interpolation operand scale;
- one quarter of the local interval length (and edge length for TrackPosition comparison).

Parent part and observation indices must match exactly. Fraction comparison propagates the same coordinate budget through division by edge length, or uses eight ULPs at fraction scale if larger. This accounts for cancellation when subtracting large coordinates on short edges (the original 112.9-degree crossing has fraction noise around 7e-13 despite identical regenerated coordinates). Local interval scaling prevents that budget from hiding a halved tiny covered interval. The policy also tolerates ordinary GEOS/interpolation differences around 1e-17 degrees without requiring exact topology equality afterward. There is no independent `area.covers(regenerated_line)` check that would reintroduce incompatible exact endpoint predicates.

Tolerance is only a computation comparison policy. It does not define minimum positive length or permit changing topology, merging parts, buffering targets or discarding visits. M2 should report unsupported/numerically indeterminate input explicitly rather than silently classify it outside. The current oracle is tested on local planar fixtures and the explicit CRS84-domain witness; it does not claim robust geodesic/antimeridian/global clipping or arbitrary precision. Those production policies require M2 tests before implementation is accepted.

## R2 numerical safety boundary and independent oracle (under corrective review)

The original legal finite GPX coordinates `(-9e-200,0)→(1.8e-199,0)` intersect a strictly positive-width target `[8e-200,nextafter(8e-200,+∞)]×[-1,1]` as an exact mathematical fact, yet original GEOS overlay returned `outside+complete` while issuing floating RuntimeWarnings. A second positive intersection `(-1.3e-199,0)→(3e-200,0)` and `[0,5e-324]×[-1,1]` produced a target segment beyond the target boundary. **Finite schema-valid binary64 operands alone do not guarantee GEOS's output is a reliable topology proof.**

Corrective `spatial-proof/0.1.1` in [PR #21](https://github.com/lysion/target-area-route-reconstruction/pull/21) treats GEOS RuntimeWarning as stable `numerical_failure`, and for sufficiently tiny positive parent edges uses exact **per-ring-edge bounding-box comparisons** as a conservative non-intersection preflight. A ring-edge bbox that might intersect the original edge bbox causes fail-closed uncertainty — never a fabricated outside, inside, or snapped geometry. When **every** exterior and interior ring edge bbox is disjoint from the parent edge bbox, the entire positive parent edge has a constant coverage predicate: retain the full observed parent interval, classified by both endpoint predicates. This handles truly positive 1e-200 and 5e-324 degree edges fully within an ordinary 2-degree rectangle without silently discarding them. This magnitude is an engine arithmetic risk guard, **not a minimum route length**.

New mandatory independent tests compute exact rectangle/segment parametric overlap with `fractions.Fraction(float)`, not GEOS, Shapely, a producer shared helper or the M1 oracle, and then exercise **real GPX decimal XML → ingestion → quality → producer → verifier → M2D**; an installed noneditable wheel repeats the two original counterexamples. The M1 oracle's own GEOS RuntimeWarnings now raise `ORACLE_NUMERICAL_FAILURE`, rather than pretending a returned geometry is independent truth. This additional gate **does not** prove arbitrary-precision robust general polygon topology for all possible floating-point inputs; unclear interactions must be reported as numerical failure.

R2-02 separately establishes that all typed `TrackPosition.fraction_to_next = 0, +0.0, -0.0` refer to **one canonical +0.0 binary64 parent vertex identity**, before `QualityProjection` or downstream `SpatialAssessment` hashing. Canonical constructors normalize these representations; verifiers reject untrusted bypassed-constructor noncanonical forms. QualityAlgorithm `0.1.2` and spatial-proof `0.1.1` mark the versioned stronger admission/semantics, **pending independent corrective review**.

## Input numbers

All validation tooling and test fixture readers use `scripts/strict_json.py`. Non-standard `NaN`, `Infinity`, `-Infinity`, and finite-looking numeric text that overflows binary64 (`1e9999`) fail before schema/semantic evaluation. Core coordinate bounds then enforce CRS84 ranges. This avoids treating Python's permissive JSON decoder as proof of standard JSON conformance.

## Regression witnesses

The formal schema and semantic manifests include diagonal interpolation noise, very short positive routes, a halved tiny covered interval on a long edge, repeated coordinates, boundary overlap, vertex touch, zero-length tracks, same-geometry parts, retracing, reordered visits and incomplete known coverage. The independent unittest layer additionally injects the cross-part-edge mutation and asserts it cannot validate the positive control.

## Production quality distance (M2B)

[M2B's implementation record](milestone2b-quality-projection.md#first-quality-algorithm-and-numerical-policy) separately defines the pinned GeographicLib 2.1 WGS84 inverse endpoint-distance method, metre units, antimeridian/polar behavior, exact UTC fractional-duration arithmetic and a 1 micrometre computational comparison guard. That screening policy does not change this planar fixture oracle, canonical interpolation or the domain definition of positive length. It preserves every tiny/zero-distance candidate edge and never uses the guard to delete observations or manufacture a gap route.

## Production spatial proof (M2C)

[M2C](milestone2c-spatial-relation.md#ordered-clipping-and-numerical-policy) promotes pinned Shapely 2.1.2 to runtime and implements per-admitted-edge planar CRS84 clipping, dominant-axis fractional lineage, the bounded coordinate-regeneration comparison above, and exact canonical partition accounting. It records Shapely/GEOS versions and reports explicit numerical failure when fractions or partitions cannot be represented reliably. It does not snap, buffer, merge visits or use an epsilon to define positive length. Longitude interpolation is explicitly linear, including 179 to -179 through 0; shortest-geodesic/periodic antimeridian interpretation is not inferred. This is separate from M2B physical-distance screening and does not broaden the M1 oracle claims.

## M2D semantic comparison versus immutable snapshot identity

[M2D algorithm 0.1.1](decisions/0012-m2d-canonical-assembly-snapshots.md) separately checks bounded semantic parent-lineage geometry and exact canonical assembly payload. It regenerates coordinates from ordered parent observations without rounding or snapping. The semantic comparison uses the minimum of 1e-12 degrees, eight ULPs at parent/coordinate operand scale, and one quarter of the regenerated interval length, with exact vertex count/order and positive-length checks. Immutable revision validation additionally requires the canonical payload produced by that algorithm. A one-ULP change may pass M1 semantic validation but fail `M2D_CANONICAL_SNAPSHOT_MISMATCH`; it must not be mislabeled a lineage failure or silently accepted under an unbound revision. Whitespace/object order remain non-semantic; duplicate members and nonzero numeric underflow are rejected before canonicalization. M1 and M2C policies and the frozen schemas are unchanged.
