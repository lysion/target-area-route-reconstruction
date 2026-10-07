# Milestone 1 Remediation Record

**Opened:** 2026-10-07  
**Base commit:** `141dc092f5a3c7845066156cafd26b3879e99137`  
**Status:** ACTIVE; Milestone 2 BLOCKED

The independent adversarial audit found that the previous Milestone 1 green gate was insufficient to prove the frozen v0.1 contract. It demonstrated acceptance of omitted or reordered repeated traversals, nonmaximal known segments, and a wrong relation under incomplete coverage. It also demonstrated a valid diagonal clipping result rejected because of floating-point noise, negative fixtures passing for unrelated reasons, linked semantic objects bypassing schema validation, and raw FIT/GPX baseline weaknesses.

The historical PASS in `milestone1-exit-review.md` remains a record of what was checked at the time. It is no longer the current readiness decision. None of these findings requires a change to the six frozen core entities or their domain semantics.

Re-exit requires reason-specific negative expectations, Layer A validation of every linked component, ordered parent-track interval checks for TargetSegment lineage and exhaustive coverage, evidence-first relation checks, a consistent numerical policy, mutation-sensitive continuity tests, strict JSON and common-schema conformance, meaningful EC-01..EC-29 contract mapping, independent raw-source conformance checks, and a fresh exit review. Production Milestone 2 parsing and spatial implementation remain out of scope during this remediation.

## Before/after evidence

At the audited base, all four gates passed: 113 schema fixtures, 33 semantic expectations, 29 mapped EC IDs and six raw files. Independent adversarial execution nevertheless found eight invalid bundles accepted and two valid bundles rejected. Six runner/implementation mutations survived all four gates. Those green results were therefore insufficient.

| Defect / baseline behavior | Repaired assertion and durable evidence |
|---|---|
| A→B→A accepted as A→B | `audit-nonmaximal_half_of_retraced_inside_part`: `TARGET_COVERAGE_NOT_EXHAUSTIVE` |
| Identical second part omitted | Both `audit-complete_omits_identical_second_part` and the separate incomplete variant require the missing ordered occurrence |
| Repeated entry omitted | `audit-complete_omits_repeated_entry`: ordered coverage mismatch |
| O→A→O→B→O reordered | `audit-segment_reorders_two_loops`: `TARGET_SEGMENT_LINEAGE_MISMATCH` |
| Incomplete known segment shortened | `audit-incomplete_nonmaximal_known_segment`: maximal observed interval mismatch |
| Established partial relabeled inside/unknown | Both `audit-proven_partial_relabelled_*`: `ASSESSMENT_RELATION_CONTRADICTS_EVIDENCE` |
| Positive tiny route called outside; correct inside rejected | Correct 5e-13 and 1e-200 positive controls pass; outside claim fails; zero-length control still fails assessability |
| Ordinary diagonal clipping rejected | `audit-nonaxis_interpolation_roundoff` passes under the unified numerical policy; original large-coordinate crossing remains valid |
| Negative fixture failed for an unrelated reason | Schema path/keyword and semantic stable-code expectations; both wrong-reason mutations fail |
| Unregistered invalid linked Activity accepted | Semantic runner enforces registration, correct schema and actual Layer A; unregistered, registered-invalid and wrong-schema mutations fail |
| Part-bridging implementation mutation survived | Positive identical-part scenario and injected mutation witness; mutation cannot validate |
| Coverage contracts removed; negatives pointed to positives | Missing fields, duplicates, malformed cases and positive negative-registrations fail |
| Nonstandard Infinity accepted | Every gate rejects NaN/Infinity/-Infinity/1e9999 before validation |
| Hash with trailing newline accepted | Exact 64-character constraint plus named negative schema fixture |
| FIT label implied full Activity, bad header CRC not checked | Old bytes retained as minimal streams; new Activity summaries independently decoded; header-CRC mutation rejected despite recomputed file CRC |
| FIT invalid sentinel interpreted as a coordinate | Independent decoder agrees that sentinel is absent; mixed positioned/missing/positioned evidence preserved |
| XML parse success confused with valid GPX | Offline official GPX 1.1 XSD rejects wrong root, version and coordinate range separately from malformed XML |

The 23 adversarial/control scenarios are full registered component graphs in `tests/fixtures/adversarial/`, not a bypass around the normal Layer A/B gates. Unit tests deliberately mutate disposable repository copies; they do not mutate committed fixtures during normal validation.

## Deliberate fixture corrections

The old local zero-length segment also had reversed parent indices. Its end observation was corrected so its expected semantic failure isolates zero length. No valid domain behavior changed.

During remediation, an initial positive multi-part `inside + complete` control was found to lack independent gap-bound evidence. It is retained as `audit-unproven_complete_multipart`, now explicitly negative. The proper positive control uses `unknown + incomplete` and retains both known segments; a separate full-domain target proves `inside + incomplete`. The original complete omission attack remains, and an additional incomplete omission attack ensures that completeness rejection cannot mask lost multiplicity.

Bundled audit files were moved into individual entity fixtures so the official manifests enforce Layer A. None of their useful behavioral assertions was removed.

## Domain and architecture review

All six core schemas retain their identity and ownership. The only production-contract schema change is tightening the shared SHA-256 digest to the already intended exact 64 lowercase hex characters. No frozen invariant required a new or superseding ADR. No finding was rejected to preserve a passing implementation.

The raw FIT finding is qualified precisely: the old files have valid framing/message definitions/file CRC and are independently readable. Their deficiency was representative Activity-profile coverage, not fake binary data. They remain useful and unchanged.

The [quality result/value proposal](quality-layer-interface.md) documents the genuine gap in mechanically proving bounded local uncertainty. It does not invent a new relation meaning or hide required semantics in extensions. General bounded-gap verification, anomaly decisions and production parsing remain M2. The M1 oracle fails closed on unsupported multi-part completeness claims; this limitation must not become an M2 domain rule.

The six promised metric input classes are now registered and tested. Validated speed/pace, smoothing and map overlays remain optional M2 behavior, consistent with the roadmap. Persistence/idempotency stays M3; source identity reconciliation and durable acquisition stay M5 (with M3 durability); resource stopping policy stays M6; route-network aggregation stays M7.

## Validation and closure

Run the four documented validators and `python -m unittest discover -s tests -p 'test_*.py'`. The [fresh re-exit review](milestone1-re-exit-review.md) records exact final results, execution environment and CI evidence. M1 remains ACTIVE and M2 BLOCKED until that review and branch CI pass. The historical PASS is never erased.
