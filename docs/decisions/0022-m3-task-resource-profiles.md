# ADR-0022: Bind configurable resource profiles to M3 task identity

**Status:** Implemented. M3 remains IN PROGRESS. Process wall-clock/RSS enforcement is implemented in the persistent task path; reproducible scaling acceptance remains open.

## Context

M3 task execution previously used fixed admission defaults for every task, while low-level ingestion and quality APIs had bounded overrides. The persisted task and graph identities did not express all of the effective observation, part, quality-fragmentation, target-vertex, and output-vertex limits. That made deployments unable to choose an approved bounded profile and left cache identity short of the execution policy.

## Decision

Add a frozen `TaskResourceProfile` carrying the six current per-source limits plus wall-clock and peak-RSS limits. Every field is an exact integer and is validated against its existing documented hard ceiling before source parsing, geometry conversion, or graph publication. The profile is serialized into the graph request and therefore into its digest; task requests retain the same complete selector. Reload requires the exact profile and re-executes the independent stage verifiers.

The default profile preserves existing M3 behavior. Existing `max_source_bytes` call sites remain supported and are translated to a profile with all other defaults unchanged. A custom profile's source-byte value cannot disagree with the separately supplied compatibility argument. Over-budget behavior remains fail-closed with the existing stage/input error codes and no partial trusted graph.

## Consequences

Profiles are caller-selected but cannot exceed the hard ceilings in `resource_limits.py`. Different limits intentionally produce different task and graph identities even when the source and assessment happen to be identical. The persistent task runner executes derivation and replay in a separate Linux worker, terminates it when the wall-clock deadline is exceeded, constrains address space with `RLIMIT_AS`, and samples `/proc/<pid>/status` for the explicit RSS failure result. The address-space ceiling ensures resident pages cannot exceed the configured byte limit; it can reject an allocation before RSS reaches that ceiling. This is per task worker and is not a distributed scheduler or a kernel cgroup guarantee. Fragmentation scaling and its numerical benchmark gate remain open.

Enhanced-custody behavior is unaffected. No M3 completion or release claim is made by this decision.
