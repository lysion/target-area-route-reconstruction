# M3 implementation progress

**Status: IN PROGRESS, not accepted / not released.** Started 2026-10-14 after issue #22 was closed by PR #23 and its merged-main CI passed. M2 remains DONE with disclosed limitations.

## First implementation: strict JSON admission prerequisite

`target_area_route_reconstruction.strict_json` owns `loads_json(str | bytes)`, `load_json(path)` and `StrictJSONError`. The fixture adapter and M2D runtime parser use it. Independent tests specify malformed/duplicate/nonfinite/underflow/Unicode inputs, legal binary64 boundaries, nested duplicate members and UTF-8 bytes. Mutation tests still kill removal of duplicate/underflow checks; their source locations were moved with the implementation, not their assertions.

Policy: UTF-8 without BOM; duplicate object names rejected at every depth, including escaped equivalent names; NaN/Infinity and binary64 overflow rejected; nonzero float underflow to zero rejected; integers stay integers, float tokens stay binary64 (including signed zero); valid escaped surrogate pairs decode normally, isolated surrogates/invalid UTF-8 fail. Malformed grammar, decoder integer/exponent constraints and excessive recursion fail closed. No epsilon, decimal-to-zero coercion or Unicode normalization. File system errors remain OSError.

For compatibility, `StrictJSONError` retains stable `M2D_DUPLICATE_JSON_MEMBER`, `M2D_NONFINITE_JSON`, `M2D_JSON_NUMBER_UNREPRESENTABLE`, `M2D_BUNDLE_MALFORMED` codes; historical `BundleJSONError` is the same class. M2D's string-only adapter remains string-only. This does not change canonical JSON identity or valid M2 outputs. Admission is separate from schema, evidence and geometric validation. This loader is not a custody receipt, cryptographic canonicalization standard, or resource-budget implementation.

## Revised next step: baseline raw custody and verified replay

[ADR-0013](decisions/0013-m3-layered-persistence-and-custody.md) adopts **basic-local** baseline and a separately accepted **enhanced-custody** extension. [ADR-0014](decisions/0014-m3-local-source-admission-storage.md) freezes encoding and SQLite atomic raw/source storage. Source admission and M2A replay are implemented; next implement complete derived graph binding and replay. M3B retains complete DAG and artifact checks, explicit expected graph selection and process-restart verification; M3C adds concurrency/idempotence/recovery; M3D enforces strict persistent admission and all resource/scaling gates.

Basic mode assumes trusted runtime/storage and cannot authenticate coherent hostile replacement or rollback. Enhanced mode retains protected signer, append-only log and independent checkpoint/finality; unavailable enhanced requests must fail, not downgrade. Actual append protection and key isolation must be proven before enhanced acceptance, but are no longer prerequisites for baseline tables.

Current implementation includes the JSON prerequisite and [M3A local source admission/M2A replay](milestone3a-local-source-admission.md): encoding, atomic SQLite BLOB/source binding, idempotence/conflicts, negative outcomes, artifact checks and separate-process M2A replay. Full graph/runtime/reliability baseline B cases remain open. Enhanced E cases and named fixed-hardware performance are separately unavailable/unmeasured. Baseline M3 DONE requires all B cases; enhanced capability requires all B+E cases. No acceptance is created by this design revision.
