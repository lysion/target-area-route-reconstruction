# Milestone 2 — fresh post-Codex remediation re-exit review

**Decision: PASS_WITH_LIMITATIONS — Milestone 2 DONE, scoped strictly to the deterministic, local, one-Activity-at-a-time FIT/GPX pipeline.** This acceptance supersedes the original October 8 PASS at `7059953c`, which was **correctly invalidated** by an independent Codex full-repository audit (F1/F2 P1). The original review and failed counterexamples remain part of the audit trail. **`v0.1.0` is not tagged, published or a complete end-user Agent Skill.**

**Review date:** 2026-10-09 (Asia/Tokyo); GitHub CI/review timestamps may be 2026-10-08 UTC.

## Frozen evidence and independent review trail

- **Failed baseline:** `7059953c0229cde14028b0018dd366c097e7ffd1`; independent external Codex full-repository review, supplied by the project owner, was **CHANGES_REQUIRED** despite previous 271 green tests. F1: QualityProjection equivalent splitting passed validation and broke M2D maximality. F2: numerically indeterminate speed screening disappeared in M2F and showed as solid screened blue. Original [historical exit review](milestone2-exit-review.md) is preserved but explicitly superseded.
- **Remediation PR:** [#18](https://github.com/lysion/target-area-route-reconstruction/pull/18), exact reviewed head `7d9d759e442ced95c306f95230231226e8ff189f`, merged into main as **`5b52738d0b490fb2725311775b66e97f8eff674f`**.
- **Review of final fix diff:** Codex GitHub PR Code Review **Completed** for `7d9d759` and reported **“Didn't find any major issues”** in [Codex's comment](https://github.com/lysion/target-area-route-reconstruction/pull/18#issuecomment-6069461158). This is a separate Codex review of **the remediation PR changes**, NOT a second full-repository cloud audit or external human approval. No inline review findings were returned. Existing original audit remains adversarial evidence.
- **Final fix-head CI:** [37846964272](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37846964272), SUCCESS with all steps passing.
- **Independent merged-main CI:** [37847574877](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37847574877), **SUCCESS**, validating exactly `5b52738d...`, not only a PR checkout. Main log confirms **277 Python tests PASS**, explicit Node JS M2E/M2F and Codex P1 map runtime checks PASS, both noneditable isolated installed-wheel smoke suites PASS; the second wheel suite explicitly reports **“F1 reject nonmaximal quality partitions and F2 preserve indeterminate numeric screening PASS”**. Other schema/semantic/source-fixture/edge coverage/mutation and whitespace gates also passed.
- **Public executable evidence:** `tests/test_m2_codex_p1_regression.py` (six independent F1/F2/F4 witness tests); `tests/m2_codex_screening_dom.cjs` (live map JS line styles, details and mode switch); `tests/m2_exit_wheel_smoke.py` (installed wheel outside checkout); original `tests/test_spatial_entities*.py`, `test_quality_projection.py`, `test_temporal_overlay.py`, and prior raw fixture / full-chain tests.
- **Supporting findings and deliberate non-goals:** [remediation record](milestone2-codex-remediation.md) and [source-format matrix](v0.1-support-boundaries.md). Frozen M0/M1 schemas and basic M2A/M2C/M2D/M2E spatial authority were not modified by the fix.

## Re-review of the two material P1 defects

### F1 — canonical maximal admitted coverage is an enforced verification contract

Previously a supported `QualityProjection` could replace a single admitted interval `obs0→obs2` with two adjacent `obs0→obs1` and `obs1→obs2` claims and remain `verify_quality=valid`. Downstream M2D treated this arbitrary data partition as two independent maximal TargetSegments, in violation of ADR-0005.

- The independent M2B verifier now rejects such claims with stable `USABLE_INTERVAL_NOT_MAXIMAL`, **before** M2C spatial proof or M2D assembly. The producer already emits canonical maximal runs.
- Deliberate real source part breaks and true excluded edges remain distinct; no missing geometry is reconnected and no producer-only normalization hides malformed claims.
- The supported QualityAlgorithm version is now **0.1.1**; previously constructed 0.1.0 claims are not silently accepted under the new stronger contract.
- Committed attack tests assert rejected alternate projection, forbidden downstream admission, valid rejected-edge and source-gap witnesses; wheel smoke independently repeats the attack from actual installed package.
- **Outcome: F1 FIX VERIFIED**, within the supported explicit QualityProjection and M2D target-coverage contract.

### F2 — exact original-parent-edge screening uncertainty survives derived metrics/map

Previously enabling `max_implied_speed_mps` caused all numerical M2F fragments to be marked as explicitly screened, even when M2B had emitted `SPEED_NUMERICALLY_INDETERMINATE` for that exact parent edge. This turned a clearly known uncertain screening into solid-blue apparently passed evidence.

- M2F now consumes the **independently validated** QualityProjection diagnostic at the exact original part/edge and exports `speed_screen_result` and `speed_screen_reason` per metric fragment and stationary record. Result states are `passed / indeterminate / unavailable / not_screened`; an enabled policy alone no longer implies pass.
- Node-executed actual map JS renders **blue solid** only for independently admitted parent-edge `passed`, **blue short-dashed** for numerically `indeterminate`, **blue long-dashed** for `not_screened`, and **gray dashed** when the temporal metric is unavailable. Missing/legacy screening states do not silently default to solid.
- The original independent tiny-distance/tiny-duration Codex counterexample is reproduced: mathematically valid high derived speed, explicit `max_implied_speed_mps=1`, M2B `SPEED_NUMERICALLY_INDETERMINATE`, M2F retains `indeterminate` **and** the original reason. Both source tests and isolated-wheel attack pass.
- The temporal overlay algorithm version is now **0.1.1**, distinguishing changed derived GeoJSON meaning from prior 0.1.0.
- **Outcome: F2 FIX VERIFIED**, including live SVG behavior; `valid` is strictly numerical UTC/maths validity, never independently authenticated true motion.

## Closure of all ROADMAP M2 exit obligations

| Requirement class | New or retained evidence | Verdict |
|---|---|---|
| `inside/partial/outside/unknown`, explicit non-assessable, open-ended gaps | Full M2C and linked scenario/negative tests; original 271 suite retained inside 277. | PASS |
| Maximal traceable target segments, repeated visits, exclusion boundaries | Independent exact M2D verifier + **new F1 noncanonical interval rejection**, wheel attack, positive exclusion/part witnesses. | PASS |
| Read-only source and stable repeatable results | SHA-256 manifest checks before/after actual FIT/GPX ingestion, full-chain repeatability tests, installed-wheel isolation. | PASS |
| FIT/GPX normalization compatibility, bounded format claims | Paired synthetic FIT/GPX real bytes; local GPX XSD packaged and tested; FIT semicircle tolerance and unsupported profiles clearly disclosed. | PASS, bounded |
| Missing/invalid timestamps retain spatial evidence | No-timestamp GPX remains assessable with null speed/pace; invalid temporal intervals neutral, no edge/gap interpolation. | PASS |
| Screened/unscreened uncertainty, parent lineage, no fabricated metric | **New F2** verified original-edge state, Node map styling, timestamp/clip underflow/overlap/extreme-GPS tests and wheel. | PASS |
| Independently verified M2B→M2C→M2D authority, stale input rejected | Producer-independent M2B quality verifier (F1 hardened), M2C proof verifier, M2D canonical snapshot verifier, duplicate JSON/numeric/revision attack gates. | PASS |
| Installed-wheel runtime and exact v0.1 support/limitation docs | CI built noneditable wheel in clean venv outside checkout; original FIT/GPX-to-M2F + new F1/F2 attacks pass; source support matrix explains explicit limits. | PASS |
| Explicit non-goals and release separation | Support docs and README distinguish observed/quality-admitted/inferred, provisional local gap bounds, M3–M8 later work, project package version versus released artifact. | PASS |

This PASS does **not** mean every conceivable input can be accurately tracked, or that producers/verifiers independently implement two GIS engines. It means the bounded deterministic contract and the two demonstrated critical gaps are closed with new regression gates.

## Accepted limitations and follow-up ownership

- **F3 — FIT timer/sampling:** FIT timer stop/start and long sparse sampling intervals do **not** independently establish missing GPS geometry under the supported continuity model. A sparse Record chord may be accepted; `complete` does not certify the true traveled path. No implicit elapsed-time threshold was introduced.
- **F4 — clipped-time assumption:** `duration_basis` is `observed_parent_endpoints` for an uncut edge and `proportional_parent_edge_allocation` for a clipped fragment. No actual border-crossing time is observed. M2B applies its cap to the *full original parent WGS84 geodesic*, while clipping follows planar CRS84 and the derived fragment can exceed that cap. The field, metadata and map warning now disclose the distinction. This remains a numerical model, not a motion-truth claim.
- **F5 — JSON test-fixture strictness:** fixture loader still differs from runtime strict loader on duplicate keys/underflow. No affected committed fixture shown; track as a bounded engineering clean-up before claiming end-to-end raw JSON byte equivalence.
- **F6 — worst-case complexity:** fragmented interval scans scale superlinearly; `ingest_file` reads entire input. M3 batch/large-history readiness requires indexed scans, file/point/target budgets and benchmark tests before guaranteeing throughput.
- **F7 — evidence custody:** M2 verifiers accept a trusted M2A snapshot supplied by the caller. They do not cryptographically re-establish original FIT/GPX derivation when a fully forged snapshot and hashes are co-modified. M3 **MUST** bind immutable original blob to TrackSource revision, complete IngestionResult and diagnostics, parser version, derivation chain and immutable snapshots on reload. Reject reused identities/revisions with divergent content and replay mixed-snapshot attacks before allowing trusted persisted caches.
- Private motivating real activity fixtures and exhaustive vendor FIT permutations were not replayed; current CI is Linux/Python 3.11 plus Node JS minimal DOM, not a complete cross-OS or true browser environment matrix.
- Persistence, idempotency/resume, user-facing Agent Skill, platform authentication/download, multi-Activity aggregation, road-network reconstruction, inferred missing centerlines and robust route identity remain later milestones. They are not implicitly included in M2 exit.

## Final decision and next stage

**M2 DONE: PASS_WITH_LIMITATIONS** after independent Codex source findings → versioned corrective production implementation → executable source and installed-wheel counterexamples → exact-head Codex remediation review without major findings → merge to main `5b52738d...` → successful merged-main CI `37847574877`. This is a materially stronger exit decision than the invalidated earlier PASS. The review cannot prove defect absence beyond tested boundaries.

**M3 status: NOT STARTED.** Its first design gate is immutable original-evidence custody and trustworthy reload/identity/revision semantics, *not* immediately persisting the six current dictionaries to SQLite. See F7 and [ROADMAP](../ROADMAP.md) M3 for scope. This review does not publish or tag v0.1.0.
