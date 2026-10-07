# M2C — Spatial relation and completeness proof

Status: ACTIVE, implementation handoff for independent review. M2A and M2B are DONE; M2D remains NOT STARTED. Base: `4b61b6108f7ebfc41d06cd8c105f7af2d9e5da37` (the approved ROADMAP contract correction). No frozen schema or ADR is changed.

## Scope and ownership

M2C derives a **supporting proof**, not a seventh core entity. Frozen SpatialAssessment requires segment references for inside/partial; M2D owns segment extraction and final assessment assembly. M2C supplies facts without inventing either entity's identity or resolving their revision-reference cycle.

| File | Responsibility |
|---|---|
| `spatial_models.py` | Frozen supporting values, outcomes and stable issues |
| `spatial.py` | Evidence-first producer and relation/completeness decisions |
| `spatial_verifier.py` | Independent structural/accounting and decision checks |
| `_spatial_inputs.py` | Mandatory quality gate, offline schema validation, exact input authority |
| `_spatial_geometry.py` | Single-original-edge clipping and fractional lineage |
| `spec/{common,canonical-track,target-area}.schema.json` | Byte-identical runtime copies of frozen schemas |

Public entry points exported by the package:

```python
prove_spatial_relation(
    *, evidence, quality_projection, quality_policy, target_area, target_reference
) -> SpatialResult
verify_spatial_relation(proof, **the_same_arguments) -> SpatialVerification
```

`evidence` is the M2A IngestionResult, which already contains the parent CanonicalTrack. `target_reference` is an independently supplied `quality_models.ParentReference(id, revision_id)` expected by the caller. There is no unsafe entry-point flag. Internal geometry helpers are not authority-bearing public APIs.

Every call first runs the accepted M2B `verify_quality` against exact evidence and expected policy, before target topology or track clipping. Failure returns `invalid_input`, no proof, and `QUALITY_AUTHORITY_INVALID` plus M2B issue codes. Invalid TargetArea is not unknown relation. Target and parent pass Draft 2020-12 frozen-schema checks, with format checking and an offline reference registry. Non-finite target numbers, including extension values, are rejected by strict serialization. Unclosed, empty or invalid polygon topology is rejected; GEOS's implicit ring closure/repair is not allowed.

## Exact supporting structure

`SpatialRelationProof` has no independent id/revision, lifecycle, persistence or entity references to future segments. Its frozen fields serialize deterministically through the existing Snapshot utility:

| Field | Contents |
|---|---|
| `authority` | Exact parent id/revision; target id/revision and SHA256 of the entire target snapshot; M2A evidence digest; SHA256 of the entire verified QualityProjection; exact quality algorithm/version/parameters |
| `algorithm` | Spatial algorithm name, version and every material numerical/engine parameter |
| `assessable` | Boolean, independent of relation |
| `relation` | inside/partial/outside/unknown for assessable inputs; null otherwise |
| `coverage_completeness` | complete/incomplete for assessable inputs; null otherwise |
| `reason` | NO_POSITIVE_LENGTH_USABLE_GEOMETRY when non-assessable; null otherwise |
| `target_coverage_intervals` | Ordered positive covered fragments on individual original admitted edges |
| `outside_evidence_intervals` | Ordered positive outside fragments on individual original admitted edges |
| `stationary_evidence` | Original zero-distance edges and their covered-point status, retained for downstream lineage/maximality |
| `gap_relevance` | Each exact M2B Gap, original gap index, constraint index or null, bound classification, unresolved-coverage/possible-outside booleans and stable reason |

`SpatialResult` wraps `outcome`, optional `proof`, and `issues`. Outcomes are `produced`, `invalid_input`, or `numerical_failure`. `SpatialVerification` returns `valid`/`invalid` and structured issues. JSON uses sorted keys, fixed array order, finite numbers and no time/path/random values. Null is an explicit absence, not an unknown relation claim. All ranges refer to the original parent `(part_index, observation_index, fraction_to_next)`; there is no compacted array.

The caller supplies trusted M2A and TargetArea snapshots. Hashes bind subsequent claims to those exact snapshots; they do not authenticate an entirely forged input supplied as authority. Reusing an id/revision with changed target content invalidates the old proof through its content digest. Coordinates alone cannot substitute for source diagnostics or quality provenance.

## Assessability and relation

An admitted original same-part edge is positive exactly when its represented endpoint coordinates differ. No metric length cutoff is used. Singleton parts, only zero-distance edges, or all positive edges excluded by quality are **non-assessable**: relation and completeness are null, with no entity creation. This differs from `unknown`, which requires positive admitted route evidence.

For assessable tracks, derive positive covered/outside facts first:

| Reliable evidence and gap facts | Relation |
|---|---|
| Positive covered AND positive outside | partial, even with unresolved gaps |
| Positive covered, no positive outside, and every gap excludes possible outside route | inside |
| Positive outside, no positive covered, and no gap could hide positive target coverage | outside |
| Remaining assessable cases | unknown |

Point-only target contact contributes no covered fragment. Positive boundary overlap counts as covered. Polygon holes remain exterior except their covered boundaries. MultiPolygon components are clipped independently by the engine and sorted in original edge order. Repeated traversal in either direction or in identical separate parts retains every occurrence.

| Coverage evidence | Completeness |
|---|---|
| Any unresolved target-relevant gap | incomplete |
| No unresolved target-relevant gap | complete |
| Non-assessable | null; no assessment assertion |

Thus partial can be complete/incomplete. Inside can be incomplete when a verified bound excludes outside movement but leaves target traversal unknown. Outside is complete. Unknown is incomplete. Zero-distance edges alone neither establish assessability nor change the positive-route relation.

## Ordered clipping and numerical policy

Runtime engine: **Shapely 2.1.2**; the tested wheel supplies **GEOS 3.13.1**. Shapely was already the M1 dev oracle dependency; it is now a pinned runtime dependency for Polygon holes, MultiPolygon, line intersection/difference and bound predicates. Implementing a second polygon engine would add an unreviewed topology implementation. `jsonschema[format]==4.26.0` is also promoted to runtime for the frozen-schema authority boundary; bundled schema copies are tested byte-for-byte against repository sources. No production module imports fixture scripts. The wheel includes the existing GPX XSD and these schemas, so validation needs no network.

Algorithm: `target-area-route-reconstruction.spatial-proof`, version **0.1.0**. Serialized parameters:

- actual Shapely and GEOS versions;
- interpolation `planar-crs84-linear`;
- fraction method `dominant-axis-binary64-v1`;
- coordinate error cap `1e-12` degrees;
- comparison budget `8` binary64 ULPs;
- local error divisor `4`;
- boundary rule `positive-length-covered;point-contact-excluded`.

Only original M2B-admitted same-part edges enter clipping. Each edge is intersected with and differenced against the target. Positive line fragments are sorted in that edge's parameter space; point intersections are discarded. There is no union across visits, cross-edge maximality computation, gap chord, target buffering, smoothing or route repair.

Exact original endpoints map to fractions 0/1. Interior fractions use `(intersection[axis]-start[axis])/(end[axis]-start[axis])` on the largest-magnitude coordinate delta (longitude wins ties). Regeneration must agree within the minimum of the absolute cap, eight ULPs at the interpolation operand scale, and one quarter of the local fragment/edge length. `hypot` sets comparison scale, never positive-length existence. Fraction 1 becomes the next original observation with fraction 0. No nearest-point snapping or clamping is permitted. Fraction collapse, nonrepresentable interior fraction, coordinate disagreement, or failure of covered/outside fragments to partition `[0,1]` exactly returns a numerical failure, never outside/unknown.

The coordinate comparison tolerates ordinary diagonal endpoint noise (~1e-17 degrees). Lineage indices remain exact. The emitted fraction is the deterministic engine-derived value; verifier comparisons require the canonical fragment representation, not an approximate alternative clipping. Tiny positive edges at 5e-13 and 1e-200 degrees survive; no squared-length underflow decides positivity.

This is **coordinate-plane linear interpolation**, not geodesic interpolation or a physical-distance model. In particular, 179° to -179° follows the represented linear longitude edge through 0°, not an inferred shortest antimeridian crossing; a regression makes this behavior explicit. No periodic wrapping, polar/geodesic topology or projected-metre interpretation is claimed. Inputs needing those interpretations require a separately justified policy, not silent coordinate rewriting. Binary64/GEOS cannot represent every arbitrarily narrow fragment; such lineage failure is explicit. The M2B WGS84 screening distance has a separate role and is unchanged.

Changes to clipping, boundary, positivity, fraction derivation, relation/gap logic or comparison policy require a spatial algorithm-version bump. Engine versions are recorded and verifier requires its supported algorithm/engine parameters exactly. Cross-engine-version byte equivalence is not claimed.

## Gaps and admissible bounds

M2C preserves each M2B Gap verbatim, including parent revision, previous/next original positions, source location/diagnostic indices, quality exclusion and cause. Leading/trailing gaps keep their absent endpoint; the first/last positioned observation is not silently the activity start/end.

| Verified constraint relative to target | Coverage uncertainty | Possible outside route |
|---|---|---|
| No constraint | unresolved | yes |
| Bound disjoint | resolved for target coverage | yes |
| Bound fully covered by target | unresolved exact traversal | no |
| Bound intersects but is not wholly covered | unresolved | yes |

Unsupported, stale or malformed constraint claims fail the M2B gate; they are not ignored as unavailable evidence. Only `crs84-domain` is currently supported. For an ordinary nonempty local target the full-domain bound intersects and cannot prove local disjointness/containment. For a target covering the full CRS84 domain it proves `inside + incomplete` when admitted evidence is positive. Missing domain claims are not silently synthesized even for that target.

The disjoint decision is implemented as a bound predicate, but has no positive local-bound witness under current supported methods. The ROADMAP's useful-local-bound acceptance obligation remains **open**, not satisfied by the world-domain witness. No endpoint buffer, time/speed reachability circle, historical corridor, straight-line path or unique reconstruction is introduced. Both inside-endpoints and outside-endpoints fallacies are tested. Source and quality uncertainty reasons remain distinct.

## Verification and stable codes

The verifier never calls the producer. It reruns the M2B authority gate, enumerates original admitted edges independently, validates positions/order, and checks that covered/outside spans account for each positive edge exactly once. It recomputes per-edge clipping, checks stationary evidence, independently evaluates bound predicates, then derives assessability, relation and completeness. Manual proof values and malicious modifications are exercised by tests.

The producer and verifier share the narrow clipping primitive and pinned geometry engine. They are independent in authority/accounting/order/gap decisions, not independent implementations of polygon topology. Manually stated rectangle/hole/touch fractions, M1 scenario expectations and actual source mutations limit shared-oracle risk; they are not a formal numerical proof for all geometry.

| Stable code(s) | Meaning |
|---|---|
| `NO_POSITIVE_LENGTH_USABLE_GEOMETRY` | Successful non-assessable proof |
| `QUALITY_AUTHORITY_INVALID` + original M2B issues | Stale, malformed or unsupported quality/evidence/proof claim |
| `TARGET_AREA_SCHEMA_INVALID`, `CANONICAL_TRACK_SCHEMA_INVALID` | Frozen schema failure; path and keyword retained |
| `SPATIAL_INPUT_NONFINITE_OR_MALFORMED` | Input cannot form finite deterministic JSON |
| `TARGET_REFERENCE_MISMATCH`, `TARGET_RING_NOT_CLOSED`, `TARGET_TOPOLOGY_INVALID` | Wrong target revision or unsupported topology |
| `SOURCE_GAP_TARGET_UNRESOLVED`, `QUALITY_GAP_TARGET_UNRESOLVED`, `GAP_BOUND_DISJOINT` | Structured gap relevance reasons |
| `GAP_CONSTRAINT_NOT_VERIFIED` | A constraint lacks verified authority |
| `SPATIAL_FRACTION_UNREPRESENTABLE`, `SPATIAL_FRAGMENT_COLLAPSED` | Positive fragment has no reliable frozen-position representation |
| `SPATIAL_LINEAGE_NUMERICAL_FAILURE`, `SPATIAL_PARTITION_NUMERICAL_FAILURE`, `SPATIAL_ENGINE_FAILURE` | Coordinate, partition or geometry failure |
| `SPATIAL_PROOF_MALFORMED`, `SPATIAL_AUTHORITY_MISMATCH`, `SPATIAL_ALGORITHM_MISMATCH` | Invalid supporting claim/authority/policy |
| `SPATIAL_POSITION_INVALID`, `SPATIAL_RANGE_INVALID`, `SPATIAL_RANGE_ORDER_OR_OVERLAP` | Invalid original parent positions/ranges |
| `SPATIAL_FRAGMENT_CROSSES_EDGE`, `SPATIAL_EDGE_NOT_ADMITTED_POSITIVE`, `SPATIAL_EDGE_COVERAGE_MISMATCH` | Invalid/missing/doubled edge evidence |
| `TARGET_COVERAGE_PROOF_MISMATCH`, `OUTSIDE_EVIDENCE_PROOF_MISMATCH`, `STATIONARY_EVIDENCE_MISMATCH` | Submitted evidence differs from ordered parent facts |
| `GAP_RELEVANCE_MISSING_OR_EXTRA`, `GAP_RELEVANCE_PROOF_MISMATCH` | Lost, fabricated or misclassified gap |
| `ASSESSABILITY_PROOF_MISMATCH`, `NONASSESSABLE_ASSERTION_INVALID` | Assessability contract contradiction |
| `RELATION_PROOF_MISMATCH`, `COMPLETENESS_PROOF_MISMATCH` | Decision contradicts reliable evidence/uncertainty |

## Regression and mutation evidence

Focused command: `python -m unittest discover -s tests -p 'test_spatial_relation.py' -v`.

The suite includes all 19 valid M1 linked scenarios converted through production M2A/quality/M2C, retaining their explicit expected relation/completeness. Additional synthetic cases exercise positive boundary overlap, holes, MultiPolygon, source and quality gaps, leading/trailing FIT missing evidence, endpoint fallacies, tiny/zero geometry, stale target/quality, target topology, diagonal fractions and original repeated visits. All raw inputs are synthetic/privacy-safe; no real-user route validation is claimed.

`test_real_mutations_are_killed_by_unchanged_witnesses` copies the production package into disposable directories and changes actual behavior, running each unmodified positive witness in a subprocess. An assertion failure with one executed test is required; import failures/timeouts do not count.

| Mutation | Unchanged witness method |
|---|---|
| Ignore gaps | `test_partial_with_gap_witness` |
| Restore excluded geometry | `test_quality_gap_witness` |
| No proven target coverage becomes outside | `test_source_gap_chord_never_becomes_geometry` |
| Any gap erases partial into unknown | `test_partial_with_gap_witness` |
| Full domain becomes local disjoint bound | `test_domain_bound_local_witness` |
| Point touch becomes traversal | `test_point_touch_witness` |
| Collapse geometrically identical visits | `test_repeated_entry_and_direction_preserved` |
| Non-assessable becomes unknown | `test_singleton_nonassessable_witness` |

Before staging, self-review checked that the mandatory gate precedes geometry; identical coordinates do not authenticate changed source evidence; excluded edges/source chords never enter clipping; no non-assessable relation exists; endpoint guesses cannot settle gaps; partial survives uncertainty; holes/components/repeats retain their domain behavior; and lineage is never snapped. No entity construction, M2D activation or frozen-schema edit was introduced. Review also found and closed Python bool/int equality acceptance in stationary-position and constraint-index checks, with a regression.

## Validation record

Python 3.11, the CI major/minor version. Final local commands/results:

| Gate | Result |
|---|---|
| Focused M2C | 44 tests; includes 8 actual mutation subprocesses and 19 M1 scenario subcases |
| Full unittest discovery | 157 tests (25 M1 + 39 M2A + 49 M2B + 44 M2C) |
| Schema fixture validator `--verbose` | 260/260 expectations; 8 Draft 2020-12 schemas |
| Semantic validator `--verbose` | 56/56 expectations; 39 linked scenarios |
| Edge-case validator | EC-01..29 mapped; 13 non-file contracts; 6 negative cross-object registrations |
| Raw baseline | 12/12 files; 2 equivalence groups |
| Isolated installed wheel | 3 end-to-end FIT/GPX cases plus GPX XSD invalid-version rejection |
| `git diff --check` | Clean |

The workflow now builds a wheel, installs it and only runtime dependencies into a fresh venv, copies `tests/wheel_smoke.py` outside the checkout, clears PYTHONPATH, and checks the imported package is outside the repository. It exercises complete FIT Activity, GPX, segmentation, quality producer/verifier, spatial producer/verifier, deterministic serialization, packaged schema refs and GPX XSD. CI status for the final SHA is reported in the PR; this record does not declare independent acceptance or M2C DONE.

## M2D handoff and remaining limitations

M2D must first validate the supporting proof against exact inputs. It can consume assessability, relation, completeness, ordered covered/outside fragments, covered stationary edges and structured original gaps without guessing spatial facts. Positive covered fragments are deliberately **per edge**, not maximal segments. Stationary edges preserve duplicate observations needed for maximal lineage but do not themselves create a positive segment.

M2D still owns maximality within continuous usable parent ranges, ordinals, entity identity/revision, final geometry regeneration, exhaustive coverage, and consistent SpatialAssessment/TargetSegment references. It must not merge through any source/quality gap or invent geometry for unresolved coverage. Non-assessable means create neither entity. Resolving the frozen bidirectional revision-reference assembly remains M2D work, not an M2C implementation detail.

There is no useful local short-gap bound, no unique route reconstruction, no TargetSegment entity, no SpatialAssessment assembly, no metrics/map/export/persistence, and no global geodesic clipping claim. These omissions are explicit checkpoint boundaries. Independent review decides acceptance; this branch leaves M2C ACTIVE and M2D NOT STARTED.
