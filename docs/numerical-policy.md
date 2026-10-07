# Numerical policy for the M1 reference oracle

`scripts/ordered_spatial_oracle.py` implements the fixture oracle's policy. It is a reference for M2 tests, not a production GIS engine or a geodesic distance model.

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

## Input numbers

All validation tooling and test fixture readers use `scripts/strict_json.py`. Non-standard `NaN`, `Infinity`, `-Infinity`, and finite-looking numeric text that overflows binary64 (`1e9999`) fail before schema/semantic evaluation. Core coordinate bounds then enforce CRS84 ranges. This avoids treating Python's permissive JSON decoder as proof of standard JSON conformance.

## Regression witnesses

The formal schema and semantic manifests include diagonal interpolation noise, very short positive routes, a halved tiny covered interval on a long edge, repeated coordinates, boundary overlap, vertex touch, zero-length tracks, same-geometry parts, retracing, reordered visits and incomplete known coverage. The independent unittest layer additionally injects the cross-part-edge mutation and asserts it cannot validate the positive control.
