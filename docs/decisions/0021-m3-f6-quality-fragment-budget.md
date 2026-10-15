# ADR-0021 — Bound M2B quality-proof fragmentation

Status: implementation decision pending PR review. Date: 2026-10-15.

## Context

The M2A admission limits bound source bytes, FIT records, positioned observations, and continuity parts. They did not bound the number of M2B objects derived from those observations. A route alternating between rejected speed edges and admitted edges can produce many excluded intervals, maximal usable runs, diagnostics, and corresponding gaps. Source diagnostics can also produce many nested gap references. The independent verifier builds edge maps and expected diagnostics from a submitted projection, so a verifier-side bound is required in addition to producer admission.

## Decision

M2B reserves one aggregate fragment budget while constructing the projection. It counts usable and excluded intervals, edge diagnostics, source-gap groups and diagnostic references, gap causes and records, exclusion-gap records, and generated gap constraints. The default cap is 10,000 entries; the low-level `project_quality` API accepts an exact positive integer up to the 100,000 hard ceiling. Exceeding the caller's cap returns `resource_limit_exceeded`, no projection, and `PART_OR_INTERVAL_LIMIT_EXCEEDED`. No partial proof is returned.

The independent verifier counts outer arrays plus nested source references, causes, and source-index tuples before building its edge universe or proof maps. Claims beyond the 100,000 hard ceiling are invalid with the same stable resource code. The persisted M3 task pipeline uses the default cap; it does not expose a profile override. An over-budget M2B stage is committed as an explicit `stage_unavailable` graph result so the attempt is auditable and replayable; M2C–M2F carry unavailable results, and no partial spatial proof or target geometry is produced.

## Consequences

- Large fragmented evidence fails closed before M2B proof serialization and before M2C–M2F.
- All accepted under-budget M2B semantics and identities are unchanged; the resource policy is also covered by the graph artifact fingerprint.
- Callers of the low-level quality API may request a different cap only up to the hard ceiling. Changing the persistent task policy requires a future versioned task profile whose exact selector is pinned into identity.
- This does not bound M2A source diagnostic creation, process RSS, or CPU time, and it does not establish asymptotically scalable producer/verifier behavior. Those F6 gates remain open.

This ADR closes only the bounded M2B fragmentation admission subtask. M3 remains IN PROGRESS and M4 is not authorized.
