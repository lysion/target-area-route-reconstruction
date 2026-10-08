# ADR-0012 — M2D canonical assembly snapshots and semantic geometry validity

**Status:** Proposed for independent acceptance in PR #8; candidate implemented on the review branch. This does not mark M2D DONE.

**Date:** 2026-10-08

**Scope:** Versioned M2D supporting API and assembly policy, not a frozen entity/schema amendment.

## Evidence and problem

[PR #9](https://github.com/lysion/target-area-route-reconstruction/pull/9) reproduced two failures on `533b0b94c90e08391892daa481c49f125f4a59ac`. Its one-ULP TargetSegment perturbation passes the independent M1 lineage oracle but fails M2D's exact geometry comparison. Its duplicate JSON member is incorrectly accepted. Additional admission probes found schema-legal extension content accepted under the unchanged revision and boolean provenance indices equated with integers.

Simply relaxing geometry equality would allow different payloads to reuse a revision whose pre-reference seed did not bind those payloads. Conversely, reporting every byte-level geometry difference as an invalid parent lineage contradicts the numerical-policy comparison budget.

## Candidate decision

Choose option (b) explicitly authorized by [the PR #8 remediation task](https://github.com/lysion/target-area-route-reconstruction/pull/8#issuecomment-6053442931): `verify_spatial_entities` validates the **canonical assembly snapshot** for the supplied, independently verified authority, not every possible schema-valid entity with semantically equivalent geometry.

There are two distinct checks:

1. Semantic lineage: exact ordered parent range, vertex count and sequence, positive geometry, and the documented bounded coordinate comparison. Use the minimum of 1e-12 degrees, eight ULPs at parent/interpolation operand scale, and one quarter of the regenerated interval length. No epsilon decides positive length or changes intervals.
2. Immutable snapshot: every decoded entity field must equal the canonical payload implied by that authority and assembly algorithm. Compare canonical JSON, including numeric representation, rather than Python equality. Different coordinates (even within semantic tolerance), unbound extensions, bool/integer substitutions or different numeric payloads cannot claim the same generated revision.

The original PR #9 one-ULP input remains **semantically valid** and **snapshot-invalid** (`M2D_CANONICAL_SNAPSHOT_MISMATCH`), without `M2D_GEOMETRY_REGEN_MISMATCH`. This deliberately refines the original test's expectation that the M2D bundle verifier should accept it. The original red review run remains historical evidence; we do not claim its unchanged expectation passes.

Object member order and whitespace have no semantic meaning under the frozen schema conventions. They are accepted when strict parsing yields the same canonical payload. `bundle.to_json()` then yields identical canonical bytes. Duplicate keys, including equal values and escaped aliases, are rejected recursively before any normalization. Non-finite numbers, overflow, nonzero binary64 underflow and invalid UTF-8 strings fail closed.

## Version and identity

M2D algorithm changes from `0.1.0` to `0.1.1` and serializes `snapshot_policy = m2d-canonical-payload-v1` in assessment algorithm parameters. `m2d-prereference-seed-v1` retains its seed construction, with the new algorithm version included. Old and new assembly revisions therefore differ. No core schema version, M2A/B/C algorithm version or package release version changes.

The seed binds the exact M2C proof (itself bound to M2A/M2B/target authority), ordered segment payloads and unresolved uncertainty payloads. SHA-256-derived assessment/ordinal-specific segment tokens are determined before reciprocal references are constructed. Hashing final mutually referencing objects to a fixed point is forbidden. ID/revision suffixes retain 160/192-bit truncation; these are collision-resistant implementation identifiers, not mathematical collision-free identities or Activity reconciliation. M3 must enforce immutable revision uniqueness rather than treating a token as a substitute for content verification.

No API permits caller-supplied extensions to be added to an existing generated snapshot. The frozen schemas still permit extensions in other schema-valid entities; a future assembly policy supporting such inputs must bind them into a versioned seed and output contract.

## Independence and error semantics

The verifier independently derives maximal ranges, uncertainties, identities and whole expected payloads without invoking the producer. Its semantic and schema checks run before whole-payload comparison. Shared regeneration, numerical comparison, serialization and hashing are narrow primitives, not independent oracles; existing M1 scenario comparisons, hand-checked geometry, and actual shared-primitive mutations remain required.

Unexpected authority, numerical or verifier failures produce explicit failure outcomes/codes, never empty successful coverage. M2C verification remains the first gate; additional exact serialized metadata comparison closes Python bool/int equality ambiguity without adding spatial inference.

## Consequences and alternatives

M1's bounded semantic validator remains valid and unchanged. The six frozen entities, relation/completeness, maximality, original parent indices, evidence ownership and ADR-0011 null semantics remain unchanged. A new frozen-contract ADR/schema change is not required; this ADR records the narrower versioned assembly API choice for independent review.

Option (a), accepting arbitrary tolerance-equivalent geometry under the existing seed/revision, is rejected because the seed does not authorize those changed payloads. Rehashing mutually referencing final entities is not a remedy. Rounding, snapping or buffering the target to hide the mismatch is also rejected.

Future changes to acceptance, payload fields, numeric regeneration, seed construction or numerical comparison require an explicit M2D algorithm version decision and regression updates. They must not silently reinterpret existing immutable snapshots.
