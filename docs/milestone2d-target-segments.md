# M2D — Target-area segments and SpatialAssessment assembly

**Status: BLOCKED — entity implementation stopped at frozen-contract preflight.**

M2A, M2B and M2C remain DONE. M2D is the sole current checkpoint; M2E remains NOT STARTED. This is a blocker and design record, not an implementation-ready handoff.

## Base and required review

Preserved existing branch `codex/m2d-target-segments` by tracking its remote branch. Starting HEAD: `632e9c7d38d1b4b4c748e3a699cffe6acc9888fa`. Initial worktree was clean. Remote main: `0ee5b1b` (PR #5 missing-route ROADMAP), already an ancestor; fast-forward synchronization reported already up to date. PR #4's merge `8c06eb3`, PR #5's merge and the M2D ACTIVE status correction are all present. No commits were rewritten or discarded.

Reviewed current ROADMAP, domain model, ADR-0004/0005/0007/0010, schema conventions, quality interface, M2B/M2C implementation records, numerical policy, common/TargetSegment/SpatialAssessment schemas, existing linked scenarios and semantic validator. M2B/M2C implementation records contain historical handoff statuses; current execution is governed by the updated ROADMAP.

## Objective and stop condition

M2D must consume an independently verified SpatialRelationProof and emit exhaustive maximal observed TargetSegments plus one SpatialAssessment only for assessable inputs. It must inherit relation, completeness, all authority and target-relative uncertainty without reclassification, reclipping or invented geometry.

Preflight confirmed a legal, verified M2C state that cannot be losslessly represented by the current mandatory **closed** `affected_track_range` without introducing an undocumented anchor interpretation. The task's frozen-contract stop rule applies: preserve schemas/evidence, provide a minimal reproducer, and propose change-control. No partial production assembler or placeholder successful result was added.

## Minimal failing evidence

```text
leading:  empty GPX source part -> (-2, 1) -> (-1, 1)
trailing: (-2, 1) -> (-1, 1) -> empty GPX source part
target:   [0, 2] x [0, 2]
policy:   QualityPolicy() — no implicit speed threshold or gap bound
```

Both raw GPX files pass production XSD/parsing. M2B and M2C verifiers return `valid`. M2C proves positive outside geometry with a relevant source gap: `assessable=true`, `relation=unknown`, `coverage_completeness=incomplete`, no known covered intervals.

| Case | Exact verified gap endpoints | Faithful schema probe failure |
|---|---|---|
| Leading | null -> `(0,0,0)` | `coverage_uncertainties/0/affected_track_range/start`, `type` |
| Trailing | `(0,1,0)` -> null | `coverage_uncertainties/0/affected_track_range/end`, `type` |
| Two-ended control | `(0,1,0)` -> `(1,0,0)` | None |

FIT missing-position prefix/suffix Records independently exercise the same production authority chain and endpoint mismatch. This is not peculiar to an XML empty-part encoding.

Relevant paths:

- `schemas/spatial-assessment.schema.json#/$defs/coverageUncertainty`: `affected_track_range` required;
- `schemas/common.schema.json#/$defs/trackRange`: start/end required, both non-null TrackPosition;
- `src/target_area_route_reconstruction/normalization.py`: absent previous/next positioned source neighbors stay absent;
- `quality_models.Gap`: start/end may be absent;
- `tests/test_spatial_relation.py::test_leading_and_trailing_fit_gaps`: already accepted M2C state;
- `scripts/validate_semantic_fixtures.py::validate_spatial_assessment`: permits equal real endpoints but defines no leading/trailing anchor convention;
- `validate_track_position_against_parent`: cannot accept a nonexistent observation as a missing endpoint.

## Alternatives and change-control

The frozen domain allows uncertainty attached to an interval, continuity break or quality issue, but the current schema serializes only a two-ended parent interval. None of the accepted fixtures establishes an alternative open-boundary encoding.

Duplicating the known endpoint can pass Layer A and M1's local semantic checks. That is a **false-green risk**, not a proof of a lawful mapping. A zero-length affected observed interval is not the absent prefix/suffix. Copying the exact gap into provenance cannot silently redefine the core field. The reproducer explicitly shows this limitation rather than claiming the old validator already rejects it.

Null/omission fails the frozen schema; a sentinel index fails parent bounds; ignoring the uncertainty violates incomplete; changing relation/completeness or returning non-assessable contradicts M2C. Inventing a source position is forbidden.

[ADR-0011](decisions/0011-open-ended-coverage-uncertainty.md) proposes a separate uncertainty-range value with explicit bounded/leading/trailing variants. It is **Proposed**, not accepted. No schema, domain model, runtime code, schema version or package data is changed. Public nullability/version compatibility must be reviewed before any amendment is implemented.

## Architecture/public API — pending after contract resolution

No `assemble_spatial_entities` or `verify_spatial_entities` API is published in this branch. Future production API must receive original M2A evidence, M2B projection, caller-owned policy, target snapshot/reference, M2C proof and a reviewed deterministic identity policy. Its first gate must call `verify_spatial_relation`, not trust proof fields.

Required result states remain planned: produced, non-assessable, invalid-input, numerical/assembly failure. No runtime reason code is claimed implemented here. For this blocker the testable failure identity is the frozen schema's exact instance path plus `type`/`required`; the Proposed ADR is the review reference.

## Identity/revision investigation

`common.schema.json` and schema-conventions section 6 define opaque ids/revisions, not a mandated hash-generation algorithm. Existing fixture pairs use explicit names such as `scenario-assessment-r1` and `scenario-segment-0-r1`, checking exact reciprocal references. M2A normalization hashes source/normalizer/parts for canonical revisions; this does not impose a hash of final self-referential entity JSON on M2D.

There is therefore no proven hash-cycle blocker. A future separately documented/versioned policy could derive all references from a canonical pre-reference assembly seed containing caller-owned identity scope, exact verified authority, algorithm/policy and ordered semantic payloads. Domain-separated assessment/segment reference tokens can be determined together before constructing immutable final objects. The verifier would derive the expected tokens from exact inputs independently. It must never accept arbitrary caller-selected contradictory refs or hash mutually containing final entities to a fixed point.

That is a design direction only, not an adopted identity convention, implemented API or solved acceptance test. M2D must record/review its precise policy before resuming implementation.

## Maximality, regeneration and verifier — unimplemented obligations

After resolution, extraction must merge only adjacent M2C-covered ranges within one continuous usable parent interval, retaining covered zero-distance observations for maximal lineage. It must preserve repeated occurrences and never span a part/source/quality/unresolved gap. Incomplete coverage cannot excuse dropping known fragments.

Geometry must regenerate from parent TrackPositions and original ordered observations, retaining duplicates and fractional endpoints under the existing numerical policy. No clipping geometry, set union, simplification or interpolation across gaps can substitute for lineage.

An independent verifier must check schemas, authority, reciprocal refs, ordinal/order/overlap, maximality, geometry regeneration, exhaustive ordered coverage, unchanged relation/completeness and exact unresolved-gap conversion. Sharing narrow interpolation primitives may be reasonable; calling the producer as its oracle is not. No such M2D verifier is claimed in this blocker PR.

## Tests and mutation status

`tests/test_m2d_contract.py` contains eight tests: leading; trailing; omitted endpoint; bounded positive control; duplicate-known-endpoint false-green; invalid parent sentinel; dropped uncertainty; FIT missing-position prefix/suffix. All use actual accepted production stages, deterministic snapshots and exact failure categories. Three synthetic GPX inputs and a target live under `tests/m2d-contract/`; these are standalone contract probes, not new linked entity scenarios or M2D output.

M2D's requested extraction/identity/verifier adversarial matrix and ten production mutation witnesses are **not implemented**, because there is no authorized production assembler to mutate while this contract blocker remains. Existing M1/M2A/M2B/M2C tests and their actual code mutations remain unchanged and mandatory. Passing blocker tests or CI is not M2D acceptance.

## Validation

Local validation used Python 3.11.16, matching the CI Python 3.11 series:

| Gate | Result |
|---|---|
| `python -m unittest discover -s tests -p 'test_m2d_contract.py' -v` | 8/8 blocker tests |
| `python -m unittest discover -s tests -p 'test_*.py' -v` | 165/165 (157 existing + 8 blocker tests) |
| Schema fixture validation `--verbose` | 260/260; 8 schemas |
| Semantic expectations `--verbose` | 56/56; 39 linked scenarios |
| EC mapping | 29/29; 13 explicit contracts and 6 cross-object negatives |
| Raw source baseline | 12/12; 2 equivalence groups |
| Rebuilt wheel, fresh isolated venv, outside checkout | 3 FIT/GPX end-to-end cases and invalid-GPX XSD rejection PASS |
| `git diff --check` | PASS |

The existing CI discovers the new tests and retains its isolated wheel gate; its final commit/run URL is recorded in the PR. There are no new runtime modules/package resources, so wheel validation checks unchanged accepted M2A/M2B/M2C functionality rather than a nonexistent M2D API. Green results establish regression safety and reproducibility of the blocker, not M2D completion.

## Resume criteria and M2E handoff

1. Independently accept ADR-0011 or an equally explicit alternative representation; do not infer acceptance from this PR's green CI.
2. Adopt an explicit schema-version/compatibility decision, update contract fixtures/validators and packaged schemas in a reviewed amendment.
3. Implement M2D identity policy, extraction, assembly and independent verifier, including all requested scenarios/adversarial cases and ten mutations.
4. Pass the full regression and installed-wheel gates, then submit implementation for independent acceptance.

M2E has no entity handoff from this branch and remains NOT STARTED. No observed evidence changes, inferred route, network/map, metric, persistence, adapter or M7 implementation was introduced.

**Verdict: M2D BLOCKED.**
