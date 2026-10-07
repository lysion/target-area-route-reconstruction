# Milestone 1 fresh re-exit review

**Date:** 2026-10-07  
**Audited baseline:** `141dc092f5a3c7845066156cafd26b3879e99137`  
**Implementation reviewed:** `87c29f8` (following the remediation commits)  
**Decision:** local review PASS; branch CI pending. M1 remains ACTIVE / remediation and M2 BLOCKED until CI verifies the branch.

This review supersedes the readiness conclusion of the [historical exit review](milestone1-exit-review.md), which remains intact. It evaluates the strengthened oracle and actual adversarial outcomes, not green fixture counts alone. Detailed before/after evidence and deliberate fixture corrections are in [the remediation record](milestone1-remediation.md).

## Re-exit criteria

| Criterion | Review evidence | Result |
|---|---|---|
| Original semantically valid inputs still pass | All original 16 linked scenarios and local semantic cases retained; no production schema weakened | PASS |
| Negatives fail for intended reason | Schema instance path/keyword; semantic stable issue code; wrong-reason mutations rejected | PASS |
| Audit counterexamples rejected | 23 registered adversarial/control scenarios, including original eight false accepts and two false rejects | PASS |
| No-edge mutation killed | Positive multipart control succeeds normally; bridging mutation cannot validate; independent edge-count regression | PASS |
| Ordered multiplicity/maximality/lineage | Per-part, per-edge parameter intervals; ordered vertex regeneration; identical/retraced/reordered visit attacks | PASS |
| Incomplete cannot bypass relation facts | Observed inside and outside force partial before submitted declaration; all six relation/completeness combinations exercised | PASS |
| Numerical policy consistent | Shared interpolation and comparison; positive length independent of tolerance; tiny/diagonal/repeated-coordinate regressions | PASS |
| Mandatory Layer A | Every linked component registered, correctly associated and schema-valid before semantic checks; three bypass mutations rejected | PASS |
| Strict JSON | All four gate entry points reject NaN/Infinity/-Infinity/1e9999 | PASS |
| Common-schema holes fixed | Exact lowercase 64-character SHA-256; trailing-newline negative fails for maxLength | PASS |
| EC-01..29 remain real contracts | Assertions, owner/milestone, future shape and reason required; duplicates/malformed/false-negative registrations rejected | PASS |
| Independent raw conformance | Pinned fitdecode; offline official GPX 1.1 XSD via pinned lxml; complete Activity summaries, sentinel and mixed-position cases | PASS |
| Source/platform independence | No FIT/GPX/device fields added to core; original raw bytes retained; parsers remain M2 | PASS |
| Frozen domain unchanged | Six entity schemas unchanged; shared hash definition tightened to existing meaning; no new/superseding ADR needed | PASS |
| Final branch CI green | Pending remote execution; do not close milestone until verified | PENDING |

## Local CI-equivalent validation

Fresh isolated Python **3.11.16**, using the workflow's `requirements-dev.txt`: jsonschema **4.26.0**, Shapely **2.1.2** / GEOS **3.13.1**, fitdecode **0.11.0**, lxml **6.1.3**. The actual GitHub Actions runner must additionally verify the committed branch.

| Command | Result |
|---|---|
| `python scripts/validate_schema_fixtures.py --verbose` | 260/260; eight Draft 2020-12 schema documents |
| `python scripts/validate_semantic_fixtures.py --verbose` | 56/56; 17 local checks and 39 linked scenarios |
| `python scripts/validate_edge_case_coverage.py` | 29/29 mapped; 13 owned non-file contracts; six negative registrations |
| `python scripts/validate_source_fixture_baseline.py` | 12/12 files; two equivalence groups |
| `python -m unittest discover -s tests -p 'test_*.py' -v` | 25 tests passed, including reason/registration/numeric/continuity mutations |
| `git diff --check` | PASS |

Counts describe registered representations, not independent invariant counts. Many linked components intentionally share an entity shape. The independent assertions and mutation witnesses establish the behaviors those counts alone could not establish.

## Qualified findings and remaining scope

No audit defect was intentionally rejected. The original FIT files were valid minimal binary message streams; they were insufficient complete-Activity coverage. All original six files remain byte-identical. New bytes are separate fixtures. General FIT compressed messages/developer fields/sensor telemetry and production GPX ingestion remain M2 parser coverage.

The current fixture interface cannot mechanically prove generic local-area gap bounds. [The quality-layer interface](quality-layer-interface.md) explicitly proposes the minimum supporting result and deterministic verifier responsibilities. The full-domain inside/incomplete witness is proved independently of its declared relation. Unsupported multi-part completeness fails closed in this oracle. ADR-0007 still allows target-irrelevant gaps and bounded inside/incomplete; M2 must implement and test the required supporting proof before emitting those claims for local targets. No new domain semantics were invented.

M2 also owns actual quality rejection, stable source-to-normalized diagnostic mapping, geodesic/antimeridian numerical policy, speed/pace outputs and maps. M1 now includes all six metric input conditions it promised. Persistence and immutability across stored revisions remain M3; adapters/reconciliation M5; quota/stopping policy M6; route aggregation M7. The explicit non-file test contracts retain that ownership.

## Things challenged successfully

The original holes, MultiPolygon, point touch, positive-length boundary overlap, repeated entry, strict segment ordering, exact revision references, no-timestamp evidence and zero-length assessment rejection still behave correctly after remediation. Raw regeneration is deterministic across all 12 files. Valid diagonal/tiny inputs are accepted while missing multiplicity and shortened intervals are rejected.

PR and final CI evidence will be added after remote execution. No merge is authorized by this review.
