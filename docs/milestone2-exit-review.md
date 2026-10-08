# Milestone 2 — Independent Deterministic Core Exit Review

> **SUPERSEDED / HISTORICAL:** This original 2026-10-08 PASS did not test equivalently split admitted quality intervals or M2F `SPEED_NUMERICALLY_INDETERMINATE` propagation. Independent later Codex Remote audit of `7059953c` returned **CHANGES_REQUIRED (F1 and F2 P1)** despite the green 271-test suite. M2 is REOPENED pending the [corrective implementation and new independent exit decision](milestone2-codex-remediation.md). Do not treat this historical PASS as current release acceptance.

**Decision:** PASS — M2 scope is complete after independently authored cross-stage adversarial gates; **the `v0.1.0` package version is NOT a published GitHub/PyPI release or release approval**.

**Review date:** 2026-10-08.
**Upstream baseline:** PR #15 merged as `92f27ca1e761539793edb7d337152e60ef4dbfb2`, M2A–M2F checkpoint acceptance already complete.
**Exit challenge branch:** `docs/m2-exit-review`, PR #16. Its newly required cross-stage gates are independent of earlier M2A–M2F tests.
**Preflight CI:** [37781638868](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37781638868), PASS — 271 Python tests, two separately required Node.js map interaction checks, original installed-wheel M2A→M2F checks, plus new separately invoked exit-installed-wheel test. The **final branch head must be rechecked after this review/documentation update before merge**.

## Scope of the exit decision

M2 is the first **deterministic, local, one-source-at-a-time** FIT/GPX pipeline, not a complete historical route-reconstruction service. The frozen six core entities remain unchanged; M2B QualityProjection and M2C spatial proof are supporting results; M2E GeoJSON and M2F temporal overlays are non-authoritative derived presentations.

Audited chain:

`preserved FIT/GPX bytes → M2A CanonicalTrack → independently verified M2B QualityProjection → independently verified M2C spatial proof → verified M2D TargetSegment/SpatialAssessment → M2E GeoJSON/HTML map → M2F optional temporal per-edge derived overlay/map`.

Each downstream acceptance verifies the exact parent evidence/quality/target/algorithm and rejected stale or forged supporting claims. The review did not change accepted M0/M1 contracts or upstream CRS84 planar interpolation semantics.

## ROADMAP exit checklist

| ROADMAP exit requirement | Evidence and explicit boundary | Verdict |
|---|---|---|
| Deterministic `inside / partial / outside / unknown` relation | `tests/test_spatial_relation.py` manually witnessed and independently verifies all four classes, stationary/boundary/hole cases and missing-gap relevance. `tests/test_m2_exit_cross_stage.py` separately witnesses partial and unknown using raw format fixtures. | PASS |
| Partial track yields traceable, maximal TargetSegments | M2D hardening and independent verifier cover exact original TrackPositions, ordinal/maximality, repeats and canonical snapshot; new real FIT+GPX partial clips produce a single confirmed segment and two temporal parent-edge fragments. | PASS |
| Raw input never modified | `ingest_file` performs read-only `Path.read_bytes`; new exit test independently verifies original SHA-256 against raw fixture manifest before/after ingestion. New isolated-wheel exit smoke also compares source bytes. | PASS |
| Identical source gives stable output | M1/quality/spatial/M2D repeatability, deterministic M2E output and map HTML and M2F tests; independent exit tests rerun real FIT full chain and compare proof/assembly/GeoJSON/temporal results. | PASS |
| FIT/GPX equivalent geometry normalizes compatibly | Baseline `tests/source-fixtures/manifest.json` declares 1e-7° FIT-semicircle coordinate tolerance. Raw `equivalent/basic.fit` / `basic.gpx` cross-stage exit tests independently compare clipped M2D coordinates within 1e-6° **output comparison**, exact parent-edge ordinal and timing, while preserving distinct content-bound CanonicalTrack revisions. Synthetic tests are not vendor-format coverage. | PASS |
| Missing timestamps preserve valid spatial reconstruction | Source `gpx/no-timestamps.gpx` remains inside/assessable and produces TargetSegments. M2F derived speed/pace is null per original edge and shown neutral, with no fabricated timestamp. New unit and wheel exit cases enforce both halves. | PASS |
| Speed/pace valid only on temporal original intervals; no gap bridging | `tests/test_temporal_overlay.py`, `test_m2f_adversarial.py` cover positive UTC, zero/equal/decreasing/missing/sub-microsecond or underflow, pauses, clipped fraction timing, GPS jumps with/without explicit cap and planar antimeridian ambiguity. New cross-stage real discontinuity witness requires exactly two fragment parent parts and unresolved/incomplete spatial relation, no gap LineString. | PASS |
| Spatial code accepts only independently verified, exact quality claims | M2C independent `verify_quality` admission; stale policy/projection, adversarial proof and M2D canonical-snapshot mutation tests reject forged/stale revisions. Independently verified again in new cross-stage unit and installed-wheel tests. | PASS |
| No positive usable length → explicitly non-assessable; leading/trailing gaps fail closed | M2C/M2D original ADR-0004 and ADR-0011 acceptance, `tests/test_spatial_entities_hardening.py`, M2E nonassessability tests; exit tests independently cover `fit/no-position.fit` and a singleton valid GPX with no assessment, and source-gap unknown/incomplete without an inferred outside decision. | PASS |
| FIT/GPX support matrix documents actual subset | `docs/v0.1-support-boundaries.md` and raw fixture README distinguish GPX 1.1 `trk` from unsupported `rte/wpt`, XSD/DTD/invalid-root failures, one FIT Activity stream from chained FIT, and limited acceptance of developer/profile/compressed-message variants. New wheel exit case explicitly rejects route-only GPX. | PASS (bounded) |
| CI installed wheel outside checkout, using packaged XSD and runtime dependencies | CI builds **noneditable** wheel, venv-install with declared dependencies outside checkout and runs `tests/wheel_smoke.py` plus independently written `tests/m2_exit_wheel_smoke.py`. Package XSD/schema access and invalid GPX are checked; source-tree imports prohibited. Verified in the PR's CI logs. | PASS (Linux/Python 3.11 demonstrated) |
| Honest v0.1 support/release limits | README, support matrix, checkpoint records and this exit report distinguish actual shipped-to-main functionality from not-yet-published v0.1.0, unverified vendor formats, explicit quality policy, source/quality gaps, domain-only gap bounds, no inferred centerline, and later M3–M8 work. | PASS for M2 documentation |

## Cross-cutting obligations and threat accounting

1. **Identity and authority:** TrackSource caller-owned; M2A source bytes fingerprinted, CanonicalTrack revision source-bound; M2B independent verifier, M2C proof verifier and M2D canonical snapshot verifier reject stale/forged facts before M2E/M2F output. This is local deterministic memory-only operation; durable custody, idempotency, persistence and cross-Activity revision reconciliation belong to M3/M7.
2. **Quality:** `QualityPolicy.max_implied_speed_mps` is caller-owned and can intentionally be disabled. Quality-admitted geometry is not asserted as a true route. Time-monotone finite derived speed is not independently corroborated; uncapped figures are visibly blue dashed, explicit-cap-enabled admitted figures blue solid, unavailable metrics gray dashed. The map documents reciprocal pace thresholds.
3. **Gaps/geometry:** M2B current bound is only the global CRS84 domain. It does **not** prove useful local short-gap reachability. Missing GPS intervals may alter `relation` or `coverage_completeness`; no gap geometry/chord/map matching is emitted. CRS84 spatial edges are **planar in the M2C proof**, not periodically shortened at 180°. M2F rejects temporally ambiguous date-line speed rather than silently changing the earlier contract.
4. **Sources:** CI uses **synthetic, privacy-safe** FIT/GPX fixtures and pinned parser dependencies. FIT FileId/Record/Lap/Session/Activity representative profiles are covered; numerous possible real device messages/variants are **not** guaranteed. Tested installation environment is Ubuntu Linux / Python 3.11; no exhaustive OS/browser/Python-version or manufacturer conformance is claimed.
5. **Scope:** M2 demonstrates one Activity/TrackSource file and a caller-supplied TargetArea. It does not automatically fetch COROS, process multiple historical activities as a network, perform efficient remote discovery, infer missing paths, provide persistence or package a ChatGPT Agent Skill. M3 persistence, M4 packaging, M5 adapters, M6 acquisition, M7/M8 route-network/inference have their own roadmap gates.

## Evidence base, separate from author assertions

- Frozen domain/M1 stronger re-exit: [M1 re-exit review](milestone1-re-exit-review.md), `schemas/` and `tests/fixtures/`.
- M2A–M2F independently accepted checkpoint implementation/review records linked from [ROADMAP](../ROADMAP.md).
- Raw-file independent contract: [raw fixtures README](../tests/source-fixtures/README.md), `manifest.json` SHA-256, raw parser baseline.
- New **cross-stage challenge suite**: `tests/test_m2_exit_cross_stage.py` (6 tests) and `tests/m2_exit_wheel_smoke.py` (clean venv, real raw bytes, not imported from repository test modules).
- Exit CI: [37781638868](https://github.com/lysion/target-area-route-reconstruction/actions/runs/37781638868) initial independent gate; final PR head must have its own green CI record.
- Reviewer must verify actual CI logs and exact final PR head before approving M2 status. Merely checking earlier stage test counts is insufficient.

## Residual risks and release separation

**Accepted limitations:** synthetic coverage, no strong local short-gap proof, unfiltered speed values if caller elects to disable the quality cap, no actual browser-layout compatibility matrix, no full real-world FIT manufacturer corpus, no inferred missing centerline, no multi-Activity map overlay or automatically usable end-user skill.

**Not a blocker to M2:** the roadmap intentionally assigns persistence to M3, agent skill packaging to M4, remote adapters to M5, acquisition/quota to M6 and historical route network to M7/M8. Never advertise M2 as fulfilling the eventual 岳麓山 multi-activity historical map workflow.

**Release boundary:** `pyproject.toml` has project version `0.1.0`, and the roadmap names it the target release. Neither proves an artifact has been formally tagged, published to PyPI, distributed or independently used on all supported systems. **M2 DONE** means the bounded implementation and cross-cutting exit criteria are accepted; **v0.1.0 release is a separate action not performed by this exit review**.

## Final decision rule

Mark M2 `DONE` only after this report, source support/documentation fixes, all new exit tests and wheel gates are present in the *exact reviewed merge head*; branch CI must be fully green and independently re-reviewed. If new tests fail or a previously frozen proof boundary is weakened, keep M2 ACTIVE and document the blocker. This is a source/adversarial-evidence review conducted within ChatGPT, not external human sign-off.
