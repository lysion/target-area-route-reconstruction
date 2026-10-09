# Codex Remote — independent current-state repository audit request

**Status:** REVIEW REQUEST ONLY. This document is a read-only audit brief, not a PASS claim, implementation requirement, or change to accepted code. Do not merge this PR as part of the review.

## Immutable audit target

- GitHub repository: `lysion/target-area-route-reconstruction`
- Audited baseline: `main` at commit `7059953c0229cde14028b0018dd366c097e7ffd1`.
- Milestones as claimed by existing records: M0 DONE, M1 DONE, M2A–M2F DONE, Milestone 2 Exit Review DONE, M3 NOT STARTED.
- Code and acceptance evidence: `ROADMAP.md`, `README.md`, `docs/milestone2-exit-review.md`, `docs/v0.1-support-boundaries.md`, `docs/decisions/`, `schemas/`, `src/target_area_route_reconstruction/`, `tests/`, `tests/source-fixtures/`, `.github/workflows/`, and `pyproject.toml`.
- Final M2 code + documentation PRs: #2, #3, #4, #8, #11, #13, #16; these prior acceptance comments were authored within the same ChatGPT-assisted implementation loop, **not** independently vetted by Codex Remote. Do not treat them as authoritative.

## Mandate

Perform a genuinely independent **read-only, full-repository audit** of actual checkout files and executable evidence, not just this audit PR's diff. Do not modify, commit, tag, merge, publish, delete, or rewrite anything. Never conflate green CI with proof of scientific/semantic correctness. Inspect evidence/authority behavior in source code, and selectively execute reproducible tests or construct small adversarial probes.

Focus in priority order:

1. **Actual progress vs roadmap:** Which commitments M0/M1/M2/M2A–F are truly implemented, test-backed and accepted? Are any milestones prematurely labeled DONE or future M3/M4/M5/M7/M8 behavior misleadingly claimed? Explicitly distinguish a usable local deterministic toolkit from an agent skill and the eventual 岳麓山 multi-Activity historical route overlay goal.
2. **End-to-end data integrity:** Raw FIT/GPX read-only evidence, identity/revision binding, FIT vs GPX coordinate tolerance, deterministic parsing and serialization, non-editable installed-wheel behavior and packaged data.
3. **Missing-track semantics:** GPS dropout, open-ended leading/trailing uncertainty, repeated visits, target-area boundary/hole/MultiPolygon, no positive-length track, unknown vs non-assessable, partial coverage and anti-fabrication properties. Ensure no gaps are bridged/reclassified by any downstream output.
4. **Authority and adversarial claims:** Independent M2B/M2C/M2D verifier separation; forged, stale, duplicate JSON, tiny numeric changes, source/target/policy mismatch, evidence lineage, first/last parent edge cases, and failures that should fail closed.
5. **Temporal correctness and UX:** Subsecond UTC, zero/reversed/missing timestamps, stationary pauses, clipping fractional elapsed time, geodesic vs planar longitude jumps, quality screening opt-in, extreme GPS jumps, map color legends, neutral missing-metric markers and source provenance.
6. **Security/reliability:** Untrusted FIT/GPX/XML/JSON handling, SVG/HTML injection, script payload escaping, performance with many points, resource exhaustion, dependency packaging and any CI/test false-positives or skips.
7. **M3 readiness:** What minimum durable evidence/integrity, identity, idempotency, immutable snapshots and acquisition constraints must be settled *before* M3 implementation? Identify missing ADRs or contract changes required before work.

## Required output

Provide a **review report on the exact baseline commit** with:

- One of `PASS`, `PASS_WITH_LIMITATIONS`, `CHANGES_REQUIRED` or `INSUFFICIENT_EVIDENCE` for the existing **Milestone 2 DONE claim**, and separate readiness assessment for M3.
- Verified findings ranked `P0/P1/P2/P3` (or explain severity); every nontrivial finding must include repository path and line range, relevant existing test or uncovered edge, reproducible counterexample and clear impact. Mark speculative risks separately.
- A checklist of ROADMAP commitments: `PASS / FAIL / NOT_TESTED / OUT_OF_SCOPE` with supporting source/test evidence and limitations.
- A short, prioritized remediation plan, distinguishing M2 exit blockers from M3 design/implementation tasks. If genuinely no blocking defects, say so but also identify residual uncertainty.
- A compact test ledger: commands executed, passes/failures/skips, environment, and any test code used solely for review.

**No modifications or automatic fixing.** Do not treat this prompt or earlier AI-generated PASS labels as proof. If unable to execute the review, clearly report environment/connection limitations rather than guessing.
