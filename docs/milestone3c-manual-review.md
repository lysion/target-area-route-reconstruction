# M3C local manual review audit

Status: implemented, pending PR review; **M3 remains IN PROGRESS**. [ADR-0016](decisions/0016-m3-local-manual-review-audit.md) defines encoding, migration and deterministic lifecycle. Implements [ADR-0009](decisions/0009-manual-decision-lifecycle.md).

## API

```python
from target_area_route_reconstruction import LocalReviewStore

store = LocalReviewStore('evidence.sqlite')  # explicit v2→v3 migration
selectors = dict(expected_source_digest=admission.record_digest,
                 target_area=target_area)  # use exact policy/options if non-default
first = store.append_decision(
    graph.graph_digest, scope='task-123', expected_head=None,
    decision_id='review-123', actor='local-reviewer', reason='Task-specific choice',
    timestamp='2026-10-14T12:00:00.000000Z', relation='outside', **selectors)
projection = store.effective_review(
    graph.graph_digest, scope='task-123', expected_head=first.digest, **selectors)
revocation = store.append_decision(
    graph.graph_digest, scope='task-123', expected_head=first.digest,
    decision_id='review-124', actor='local-reviewer', reason='Withdraw earlier choice',
    timestamp='2026-10-14T12:10:00.000000Z', action='revoke', **selectors)
```

Keep returned digest as the explicit expected stream head. Corrections use a new decision_id and expected_head; exact repeats are idempotent even after later facts. Different content with an existing decision_id yields `M3_REVIEW_ID_CONFLICT`. Stale head yields `M3_REVIEW_HEAD_CONFLICT`; the caller must review the competing decision before retrying, not silently overwrite it. No list API automatically selects a latest graph or audit head.

Every call freshly verifies the graph using raw evidence and all M2 verifiers. `historical_unverified` yields `M3_REVIEW_GRAPH_UNVERIFIED`; unavailable M2D yields `M3_REVIEW_ASSESSMENT_UNAVAILABLE`. A verified assessment with unknown relation can be reviewed, but this cannot create geometry or measured data. Relation choices are inside/outside/partial/unknown. A revoke restores the algorithmic relation; it never revives an earlier override. A second revoke without an intervening set is rejected.

`EffectiveReview` contains exact graph identity, assessment JSON, task scope, head digest, algorithmic relation, effective task-facing relation and full ordered audit JSON. The assessment JSON retains completeness and references; original graph/segments/metrics remain immutable. M2E/M2F exports remain algorithmic; the API caller must present manual interpretation separately. `verified_local` here means a replayed graph plus a structurally valid local audit stream, not verified human judgment, authenticated actor, trusted timestamp or real movement truth.

## Storage and limits

Schema v3 adds reviews with unique decision_id/digest, graph foreign key and ordered stream index. SQLite IMMEDIATE transaction serializes append and checks predecessor; pre-commit process death rolls back, post-commit retry reuses the fact. Raw/source/graph readers support v3. Older software that understands only v2 must refuse v3; no implicit downgrade. No automatic schema conversion of evidence or reinterpretation of old reviews. Schema migration preserves existing bytes but does not establish artifact compatibility: upgrading package code changes the graph artifact set. Historical graphs remain unverified under a different build; use the exact historical runtime, or explicitly derive a new graph and review it separately. Decisions never migrate silently to a newly derived graph.

Native types are required before replay/hash. Each canonical record ≤64 KiB, each graph/task stream ≤10,000 records. Stored oversized BLOB is refused before loading it. Strict JSON, exact field sets, hash, assessment binding and predecessor/action validation apply on every read. Missing predecessor, altered bytes and stale external head fail closed. Storage is preserved for investigation; no automatic quarantine or destructive repair.

## Remaining gates

General task scheduling/resume, verified cache orchestration, administrative backup/recovery and quarantine, F6 full input/time/memory/scaling gates, and final independent exit audit remain open. Basic-local trusts application/OS/storage: coherent hostile rewriting of all facts and expectations is not authenticated. Actor and UTC timestamp are caller provenance. Enhanced custody remains explicitly unavailable.
