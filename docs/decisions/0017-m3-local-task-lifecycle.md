# ADR-0017 — Local task lifecycle and explicit verified reuse

Status: implementation decision pending PR review. Date: 2026-10-14.

`LocalTaskStore` explicitly migrates v3→v4, retaining source, graph and review bytes. Immutable task requests (`m3-local-task-v1`) bind caller task_id, source id/revision/admission digest, normalized full graph request, basic-local profile, current actual graph-artifact digest, raw-byte budget and optional explicit expected graph digest. A reused task_id must have identical request bytes. Task budgets belong to runtime identity, not M2 entity identity. No search chooses an arbitrary graph.

An append-only canonical hash-linked journal (`m3-local-task-event-v1`) records queued → running → completed/failed. Failed → running retries preserve prior events. Caller supplies expected request digest and head for all actions; IMMEDIATE transaction performs compare-and-append. Each event records actor provenance, state, previous digest, optional graph and failure code. Actor is caller provenance, not authentication. Order is the predecessor chain, not a clock claim. Reads validate exact shape, native types, canonical JSON, parent links and legal transitions. Snapshot status is lifecycle metadata, never cached verification authority.

Execution is synchronous, caller-driven: claim running, release SQLite transaction, evaluate/verify, append completion conditionally against the exact claim head. Explicit recovery changes an interrupted running head to failed with M3_TASK_INTERRUPTED. It can fence a live worker as well; the trusted caller decides recovery. A stale worker cannot complete/fail a newer attempt. There are no time-based leases, automatic dead-worker inference, background queue or distributed scheduler.

Without expected_graph_digest, derive a graph from original bytes under pinned artifacts then verify it. With one, replay exactly that graph with exact task selectors; mismatch/unavailability is failure, with no silent fallback to fresh derivation. Result reads replay again; completed alone is never verified. A completed-task retry verifies before returning its existing state. Negative spatial outcomes can complete evaluation; task completion is not an inside/complete or metric-success claim.

Graph publication and task completion are separate atomic commits. A crash after graph commit can leave an intact graph and running task, never a completed task without graph verification. Recover/retry idempotently regenerates the same graph (or explicitly replays the requested graph). A fenced worker can leave a valid standalone graph, but cannot publish task completion. Runtime artifacts changing requires an explicitly new task; no historical artifact relabeling.

Task request cap 16 MiB; journal event cap 64 KiB; at most 1,000 events per task. Reserve one terminal slot before claiming a run. Reads bound BLOBs before allocation. These local limits do not complete F6 workload/time/RSS gates. Basic-local does not authenticate coherent hostile store rewrites or rollback; enhanced custody remains unavailable. Backup/quarantine administration, F6 and final independent M3 exit audit remain open.

Task/source identifiers, actor and failure-code strings must be native nonblank UTF-8 strings of at most 4,096 bytes. These are task-runtime admission limits, not changes to the frozen spatial entity schemas.
