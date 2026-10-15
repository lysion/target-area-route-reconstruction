# M3C caller-driven task runtime

Implemented pending PR review; **M3 remains IN PROGRESS**. [ADR-0017](decisions/0017-m3-local-task-lifecycle.md) freezes request/journal encoding, v4 migration and recovery semantics.

```python
from target_area_route_reconstruction import LocalTaskStore
store = LocalTaskStore('evidence.sqlite')  # explicit v3→v4 migration
queued = store.submit_task(
    'task-123', source_id, source_revision, actor='local-operator',
    expected_record_digest=admission.record_digest, target_area=target_area)
done = store.run_task(
    queued.task_id, expected_request_digest=queued.request_digest,
    expected_head=queued.head_digest, actor='local-worker')
if done.state == 'completed':
    verified = store.task_result(
        done.task_id, expected_request_digest=done.request_digest,
        expected_head=done.head_digest)
```

Full policy, include_outside, temporal_mode and max_source_bytes are optional submission arguments with graph API defaults. `expected_graph_digest=chosen_graph_digest` requests exact verified reuse. It never calls derive_graph as fallback: wrong target/policy, absent graph, corruption or unavailable artifacts fail the attempt. This is verified reuse, not a shortcut around re-ingestion/computation. No automatic candidate search or heuristic graph selection is implemented.

Requests pin complete normalized graph selectors, exact source admission, profile and actual artifact digest. A task ID is immutable: identical retry returns current lifecycle metadata, changed request conflicts. Actor is event provenance and is not part of algorithmic graph identity. Runtime budget changes need a distinct task request; they do not change M2 entity semantics. Package updates change actual artifact digests, so historical tasks cannot resume under a new build. Use the exact historical runtime or explicitly submit a new task; no silent graph/review reassignment.

`TaskSnapshot` has task_id, request_digest, head_digest, state, graph_digest, failure_code and verification_scope=`task-lifecycle-only`. queued/running/failed/completed are lifecycle states, not spatial verdicts or cached verification authority. A completed evaluation may preserve numerical_failure, unavailable stages or null metrics. `task_result` freshly replays M2A–M2F and validates pinned artifacts and full source binding. A completed `run_task` retry also re-verifies; it never returns stale success solely because a status row says completed.

## Retry, recovery and audit

`task_snapshot(task_id, expected_request_digest=...)` returns current validated metadata. Keep externally expected request/head digests. `task_history(task_id, expected_request_digest=..., expected_head=...)` returns the complete validated canonical ordered journal. Stale heads are rejected. Initial queued, every claim, failure and completion remain visible; actor strings are caller provenance, not authenticated identities or trusted clocks.

Failures from LocalEvidenceError become failed snapshots with the stable original failure code. Unexpected exceptions persist M3_TASK_EXECUTION_FAILED then re-raise. Retry failed with its returned head using run_task. Input/stale-head errors before claim leave state unchanged.

The task profile applies a wall-clock deadline and RSS/address-space ceiling to the isolated Linux execution worker. A worker timeout, memory ceiling or unexpected exit is journaled as a typed failed attempt and may be retried. If the caller/runtime process itself exits while the task is still running, call `recover_task(task_id, expected_request_digest=..., expected_head=running.head_digest, actor='operator')`. This appends failed/M3_TASK_INTERRUPTED, then the returned head may be retried. Recovery is an explicit trusted caller decision, not proof the worker died. It fences even a live old worker from completing a newer attempt; stale writers get M3_TASK_HEAD_CONFLICT. There is no automatic lifecycle lease expiry, background polling or distributed scheduler.

Graph publication and task completion are separate transactions. A crash after graph commit preserves a valid standalone graph and running task; explicit recovery/retry reuses the same identity. A fenced worker may still finish a standalone graph but cannot complete the task. No partial or merely staged graph is exposed as a completed task result.

## Persistence boundaries

Explicit LocalTaskStore migration adds tasks and task_events in SQLite v4, preserving existing source/graph/review bytes. Older source/graph/review APIs understand v4; old software lacking v4 support must refuse it. Migration does not establish artifact compatibility or relabel historical evidence.

Task request ≤16 MiB; journal event ≤64 KiB; ≤1,000 events per task. Claim reserves space for a terminal event. Over-cap requests/streams fail, BLOB lengths are checked before loading. Numeric admission and process time/RSS ceilings are task-profile controlled; fragmentation scaling acceptance remains outstanding. Journals detect inconsistent corruption but cannot authenticate coherent malicious storage/expectation replacement or rollback. Enhanced custody remains unavailable.

Remaining baseline work: administrative backup/quarantine/recovery procedures, F6 complete resource and scaling gates, acceptance-matrix consolidation and independent M3 exit audit. This synchronous runtime covers submitted tasks and explicit retries; remote acquisition, broad workflow scheduling and distributed workers are not claimed by this API.

Task/source identifiers, actor and failure-code strings must be native nonblank UTF-8 strings of at most 4,096 bytes. These are task-runtime admission limits, not changes to the frozen spatial entity schemas.
