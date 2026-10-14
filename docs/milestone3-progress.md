# M3 implementation progress

**Status: IN PROGRESS, not accepted / not released.** Started 2026-10-14 after issue #22 was closed by PR #23 and its merged-main CI passed. M2 remains DONE with disclosed limitations.

## First implementation: strict JSON admission prerequisite

`target_area_route_reconstruction.strict_json` owns `loads_json(str | bytes)`, `load_json(path)` and `StrictJSONError`. The fixture adapter and M2D runtime parser use it. Independent tests specify malformed/duplicate/nonfinite/underflow/Unicode inputs, legal binary64 boundaries, nested duplicate members and UTF-8 bytes. Mutation tests still kill removal of duplicate/underflow checks; their source locations were moved with the implementation, not their assertions.

Policy: UTF-8 without BOM; duplicate object names rejected at every depth, including escaped equivalent names; NaN/Infinity and binary64 overflow rejected; nonzero float underflow to zero rejected; integers stay integers, float tokens stay binary64 (including signed zero); valid escaped surrogate pairs decode normally, isolated surrogates/invalid UTF-8 fail. Malformed grammar, decoder integer/exponent constraints and excessive recursion fail closed. No epsilon, decimal-to-zero coercion or Unicode normalization. File system errors remain OSError.

For compatibility, `StrictJSONError` retains stable `M2D_DUPLICATE_JSON_MEMBER`, `M2D_NONFINITE_JSON`, `M2D_JSON_NUMBER_UNREPRESENTABLE`, `M2D_BUNDLE_MALFORMED` codes; historical `BundleJSONError` is the same class. M2D's string-only adapter remains string-only. This does not change canonical JSON identity or valid M2 outputs. Admission is separate from schema, evidence and geometric validation. This loader is not a custody receipt, cryptographic canonicalization standard, or resource-budget implementation.

## Revised next step: baseline raw custody and verified replay

[ADR-0013](decisions/0013-m3-layered-persistence-and-custody.md) adopts **basic-local** baseline and a separately accepted **enhanced-custody** extension. [ADR-0014](decisions/0014-m3-local-source-admission-storage.md) freezes encoding and SQLite atomic raw/source storage. Source admission and M2A replay are implemented; [M3B graph commitments/cold replay](milestone3b-local-graph-replay.md) now implements complete staged evaluation snapshots, explicit selectors, artifact checks and re-ingestion. Next complete runtime lifecycle and reliability gates. M3B retains complete DAG and artifact checks, explicit expected graph selection and process-restart verification; M3C extends those guarantees to manual audit and task lifecycle; M3D enforces strict persistent admission and all resource/scaling gates.

Basic mode assumes trusted runtime/storage and cannot authenticate coherent hostile replacement or rollback. Enhanced mode retains protected signer, append-only log and independent checkpoint/finality; unavailable enhanced requests must fail, not downgrade. Actual append protection and key isolation must be proven before enhanced acceptance, but are no longer prerequisites for baseline tables.

Current implementation includes the JSON prerequisite and [M3A local source admission/M2A replay](milestone3a-local-source-admission.md): encoding, atomic SQLite BLOB/source binding, idempotence/conflicts, negative outcomes, artifact checks and separate-process M2A replay. Basic graph evaluation/replay is implemented; full runtime/reliability baseline gates and final independent exit audit remain open. Enhanced E cases and named fixed-hardware performance are separately unavailable/unmeasured. Baseline M3 DONE requires all B cases; enhanced capability requires all B+E cases. No acceptance is created by this design revision.

## M3C batch: append-only manual decision audit

[Local review API](milestone3c-manual-review.md) and [ADR-0016](decisions/0016-m3-local-manual-review-audit.md) implement explicit schema v3 migration, exact verified graph/assessment binding, task-scoped immutable decisions, corrections/revocations, idempotent retry, concurrent predecessor conflict, cold replay and commit crash recovery. Effective task classification exposes algorithmic relation and ordered manual provenance; it never changes spatial evidence, completeness, segments or metrics. Native type checks precede hashing; record/stream bounds apply. Actor/time are local claimed provenance, not authentication.

At the manual-review checkpoint, task lifecycle/resume and verified-cache orchestration were still open; the next batch below implements their caller-driven baseline. Administrative backup/quarantine, remaining F6 resource/scaling gates and final independent exit audit remain open. No M3 DONE or enhanced-custody claim.

## M3C next batch: task attempts and explicit verified reuse

[Task runtime](milestone3c-task-runtime.md) and [ADR-0017](decisions/0017-m3-local-task-lifecycle.md) add opt-in v4 immutable requests and hash-linked lifecycle journals. Complete source/target/policy/options/artifact selectors are pinned; explicit expected graph reuse always replays, never falls back. Concurrent claims, stale-worker fencing, failed-attempt retry, interrupted-process recovery, terminal commit crashes and v3 graph/review preservation are tested. Task metadata is not verification authority; task_result performs fresh replay. Negative evaluation outcomes remain negative.

Baseline task orchestration is synchronous and caller-driven, with explicit recovery and no automatic leases/distributed scheduler. Remaining work is administrative backup/quarantine/recovery, full F6 resource/scaling evidence, acceptance-matrix consolidation and independent M3 exit audit. M3 is still IN PROGRESS.
