# M3 implementation progress

**Status: IN PROGRESS, not accepted / not released.** Started 2026-10-14 after issue #22 was closed by PR #23 and its merged-main CI passed. M2 remains DONE with disclosed limitations.

## First implementation: strict JSON admission prerequisite

`target_area_route_reconstruction.strict_json` owns `loads_json(str | bytes)`, `load_json(path)` and `StrictJSONError`. The fixture adapter and M2D runtime parser use it. Independent tests specify malformed/duplicate/nonfinite/underflow/Unicode inputs, legal binary64 boundaries, nested duplicate members and UTF-8 bytes. Mutation tests still kill removal of duplicate/underflow checks; their source locations were moved with the implementation, not their assertions.

Policy: UTF-8 without BOM; duplicate object names rejected at every depth, including escaped equivalent names; NaN/Infinity and binary64 overflow rejected; nonzero float underflow to zero rejected; integers stay integers, float tokens stay binary64 (including signed zero); valid escaped surrogate pairs decode normally, isolated surrogates/invalid UTF-8 fail. Malformed grammar, decoder integer/exponent constraints and excessive recursion fail closed. No epsilon, decimal-to-zero coercion or Unicode normalization. File system errors remain OSError.

For compatibility, `StrictJSONError` retains stable `M2D_DUPLICATE_JSON_MEMBER`, `M2D_NONFINITE_JSON`, `M2D_JSON_NUMBER_UNREPRESENTABLE`, `M2D_BUNDLE_MALFORMED` codes; historical `BundleJSONError` is the same class. M2D's string-only adapter remains string-only. This does not change canonical JSON identity or valid M2 outputs. Admission is separate from schema, evidence and geometric validation. This loader is not a custody receipt, cryptographic canonicalization standard, or resource-budget implementation.

## Next implementation gate: M3A selected trust backend

Keep the [normative selected design](milestone3-evidence-custody-contract.md): Linux split principals, protected Ed25519 signer and append-only log, separate checkpoint owner, immutable receipts, separately signed finality. Before any trusted tables/cache/publication, demonstrate real signer/worker/checkpoint account permissions and C20/C23 failure behavior. A missing backend must report `trust_backend_unavailable`. No in-process signing key or worker-writable checkpoint fallback is authorized.

Remaining M3A: immutable raw bytes/full TrackSource binding, signature/hash chain, uniqueness/conflict, separate checkpoint finality, negative outcomes and crash recovery. M3B: full typed DAG and exact artifact attestation, expected GraphCommit selection and verified replay. M3C: transactional runtime lifecycle. M3D: persistence integration of strict JSON plus remaining processing budgets and benchmarks.

The dedicated frozen F6 runner is not provisioned by this PR; its result is NOT_TESTED. Actual principal isolation, signed custody, restart/reload, C01–C23 integration and complete F6 are not claimed. These are M3 exit blockers, not reasons to mark this prerequisite or M2 failed. M3 must not be marked DONE until its full exit contract has independent evidence.
