# ADR-0013 — M3 layered persistence and custody acceptance

**Status:** Accepted for implementation by owner instruction on 2026-10-14; repository change pending PR review. No feature acceptance is implied.
**Scope:** Supersedes the single mandatory enhanced trust backend and exact-hardware M3 exit gates; preserves M0/M1 entities, M2 correctness and identities. See the [historical design](../history/milestone3-single-profile-contract.md).

## Context

The primary product is a local single-activity tool. Reliable restart, evidence binding and deterministic verification are needed immediately. The previous contract additionally made compromised-worker resistance, independent administration and one physical runner prerequisites for all persistence. Those are materially stronger deployment promises with unimplemented infrastructure, not prerequisites for a useful trusted-local runtime.

## Decision

1. M3 baseline is **basic-local**: trusted application, OS/operator and local storage. Preserve exact raw bytes, complete TrackSource, immutable-by-application snapshots, full typed derivation DAG, explicit expected graph selection, actual executable hashes, strict JSON, verified replay, conflict/idempotence/crash handling and bounded resources. SQLite hashes and application immutability detect corruption and inconsistent edits; they do not authenticate hostile storage or prevent coherent replacement/rollback.
2. **enhanced-custody** is a separately accepted capability, not a mandatory baseline exit blocker. It adds independent protected Ed25519 receipts, append-only chain, externally obtained latest checkpoint, separate finality and actual least-privilege principals. It must pass its own attack suite before advertising resistance to a compromised worker. Requesting enhanced mode without that backend returns `trust_backend_unavailable`; no implicit fallback.
3. Persist and expose the profile and verification basis. Basic results may be `verified_local`; `verified_custody` requires enhanced finality and exact anchored graph. Missing artifacts return `historical_unverified`, never a latest-version success. Profile labels alone are not security evidence: enhanced verification must originate from independently configured trust roots, not cached metadata. New enhanced admission/replay is required to upgrade old basic data; an old baseline label cannot become a signature.
4. Record exact package/module/native binary/environment digests. Baseline need not automatically install or execute every historical environment; it must retain snapshots and raw bytes and refuse verified replay if exact artifacts are unavailable. No changes to existing M2 entity schemas or status enums: these are M3 supporting records/API results.
5. Replace one-hardware-only baseline performance exit with a frozen reproducible environment, enforced budgets, independent producer/verifier scaling tests and a comparison baseline. Keep the original i7-8700 absolute claim as an optional named performance profile requiring its exact runner. See [F6 protocol](../post-m2-f3-f6-action-plan.md).

## Consequences

Basic persistence can be implemented before signer deployment. Core evidence correctness is not deferred: both modes must preserve lineage, negative outcomes, gap semantics, F3/F4 provenance, resource admission and transactional consistency. Enhanced publication remains pending until independent finality. Neither mode authenticates vendor telemetry; enhanced excludes compromised signer/checkpoint/root. Different Unix accounts alone do not prove append-only storage or independent administration.

The [current contract](../milestone3-evidence-custody-contract.md) maps C01–C23 by profile. Basic M3 DONE must explicitly say **basic-local accepted; enhanced-custody unavailable or separately accepted**. Deferred enhanced cases are NOT_IMPLEMENTED/NOT_TESTED, not PASS. Existing audit findings and failed cases remain historical evidence. No implementation or test assertion is weakened by this documentation change.
