# M3B — complete local graph commitments and cold replay

**Status: IMPLEMENTED, pending review; M3 IN PROGRESS.** [ADR-0015](decisions/0015-m3-basic-local-derived-graphs.md) freezes the supporting graph format. This is basic-local integrity/replay, not signed enhanced custody.

## API and selection

```python
from target_area_route_reconstruction import LocalGraphStore, QualityPolicy

store = LocalGraphStore("evidence.sqlite")
# `admission` comes from admit_file/admit_bytes; `area` is complete TargetArea JSON.
commit = store.derive_graph(
    admission.source_id, admission.revision_id,
    expected_record_digest=admission.record_digest,
    target_area=area, policy=QualityPolicy(), include_outside=True,
    temporal_mode="speed_mps",  # or pace_s_per_km, or None explicitly disables M2F
)
result = store.reload_graph(
    commit.graph_digest, expected_source_digest=admission.record_digest,
    target_area=area, policy=QualityPolicy(), include_outside=True,
    temporal_mode="speed_mps",
)
assert result.status == "verified_local"
# Inspect every stage outcome before using its spatial/metric result.
```

`graph_candidates(source_id, revision_id)` returns unverified candidate identities only; there is no automatic preferred result. Full target content/revision, quality policy and export options must match at reload. Same request/artifacts produce the same graph digest; different target, policy, mode or artifacts are separately committed graphs. Numeric input aliases normalize before invoking M2 so they cannot split accepted graph identity. Bool/number option aliases and policy subclasses/instance codec overrides are rejected.

## Retained evidence

The graph retains complete source-reference/root binding, full request, explicit algorithms/versions/parameters (including unavailable stages), actual core/dependency/native/interpreter artifact hashes and seven ordered nodes: request + M2A–M2F. Each stage includes exact complete dataclass payload JSON and B/C/D independent verification records. M2D includes immutable assessment/segment JSON and reciprocal references; M2F retains parent screening, allocation basis and null reasons. M2E contains actual export and default map regeneration recipe with renderer artifact in the attested core set. No HTML cache or modified renderer is trusted separately.

Every node hashes its payload and exact parents; closure is checked at load. Serialized models are never hydrated into trusted authority. Cold replay reads integrity-checked original bytes/full source and recomputes M2A–M2F, runs the existing independent stage verifiers and compares the full manifest exactly. Tampered local hashes alone cannot replace a caller-retained expected graph; even a newly chosen forged hash must match fresh replay. A hostile actor coherently replacing all bytes/records/expectations remains outside basic-local guarantees.

A numerical failure or missing source evidence produces explicit stage_unavailable plus ordered downstream unavailable nodes, not outside/complete or successful empty data. A non-assessable proof/export retains its actual typed outcome. Temporal mode None yields disabled; a produced metric export may still contain missing_timestamp/null metrics. Graph verified_local means the complete **evaluation record** was verified, not that every stage or metric is successful. Always inspect outcomes. historical_unverified returns no verified manifest when exact artifacts are unavailable/changed.

## Storage, migration and new derivations

Schema v2 transactionally adds the graph table to v1; original source records are unchanged. Source APIs continue working with v2. Publication rechecks parent/raw integrity inside its write transaction and inserts the entire manifest once. No staged half graph is exposed; replay/refusal does not mutate historical records. Source records remain capped at 16 MiB. Graph manifests now use the identity-bound 32 MiB default / 128 MiB hard cap (ADR-0022), checked before publication and before stored BLOB allocation.

An explicitly requested current graph may be generated from old integrity-checked raw/source material even if its **old M2A snapshot** is historical_unverified. The new graph records current artifacts and fresh M2A output; old source snapshot status/digest are not upgraded. Historical graph verification itself still needs exact historical artifacts; this feature does not auto-install arbitrary past environments.

## Evidence and remaining gates

Tests include exact frozen spatial facts, multiple area/policy candidates, explicit selectors, canonical numeric aliases, disabled mode, real FIT/GPX cold replay, negative/no-position/gap/no-time outcomes, Fraction-positive unrepresentable coverage remaining numerical_failure, F4 parent-cap/allocated-time distinction, root/node tampering with coherent node rehash, verifier refusal, size rejection, and real process exit before/after graph commit. Installed-wheel CI repeats the new suite and original M2/M3A gates.

M3C lifecycle and M3D admission/worker budgets now have implementation and test evidence. The same-batch fragmentation scaling benchmark remains open after one clean run exceeded its ratio limit; administrative backup drills/retention and final independent M3 exit audit also remain. Enhanced signing/log/checkpoint/finality is outside baseline basic-local and remains unavailable. Application/OS/local storage and static deployed code are trusted. This batch supports Linux ELF artifact discovery (actual loaded CPython provider, not build-time paths); other graph artifact backends fail unavailable and are not claimed tested. This is not M3 DONE or universal environment reproducibility/power-loss certification.
