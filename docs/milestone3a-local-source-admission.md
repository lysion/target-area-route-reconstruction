# M3A — basic-local source admission and M2A replay

**Status: IMPLEMENTED, pending PR review; M3 IN PROGRESS, not DONE.** [ADR-0014](decisions/0014-m3-local-source-admission-storage.md) freezes encoding/storage. [ADR-0013](decisions/0013-m3-layered-persistence-and-custody.md) defines the trusted-local threat model.

## Public API

```python
from target_area_route_reconstruction import LocalEvidenceStore

source = {
    "schema_version": "0.1.0", "id": "source-a", "revision_id": "r1",
    "activity": {"id": "activity-a"},
    "origin": {"namespace": "local_import"},
    "representation": {"media_type": "application/gpx+xml"},
}
store = LocalEvidenceStore("evidence.sqlite", profile="basic-local")
admission = store.admit_file("activity.gpx", source_kind="gpx", track_source=source)
# Persist this explicit expected admission identity with the task/caller request.
loaded = store.reload_source("source-a", "r1", expected_record_digest=admission.record_digest)
assert loaded.status == "verified_local"
assert loaded.verification_scope == "source-and-m2a"
evidence = loaded.ingestion  # fresh complete IngestionResult, diagnostics retained
```

FIT uses explicit `source_kind="fit"` and `media_type="application/vnd.ant.fit"`; GPX uses `gpx` / `application/gpx+xml`. An extension/file name never chooses the parser. `admit_bytes` accepts exact immutable bytes with the same budget; `admit_file` shares M2's descriptor-based bounded regular-file reader and never writes input files. `track_source` accepts native JSON data only; raw JSON must first go through package `strict_json.loads_json/load_json`, never a permissive caller parser.

## Delivered capabilities

- Complete schema-valid source/provenance/Activity binding, raw SHA/length and optional content_hash guard.
- Raw content deduplication separate from source/Activity identity, exact repeat idempotence and serialized revision conflict rejection.
- SQLite BLOB raw bytes and full M2A JSON committed atomically with local admission; synchronous FULL, rollback journal, schema v1. No cross-filesystem publication dependency.
- Preserve success, failure and no_positioned_observations, missing time and multi-part evidence; never create inferred paths.
- Named parser/normalizer versions and fixed parameters, actual execution bytes, and exact native canonical admission encoding; integer/float equality aliases and signed zero normalize in source JSON, boolean remains distinct. Existing M2 payload is kept as exact JSON string and M2 identities remain unchanged.
- Explicit expected digest, raw and record corruption checks, current actual parser artifact comparison and fresh original-byte re-ingestion. Missing/mismatched artifacts yield historical_unverified with no usable ingestion. Re-admission cannot rewrite historical parser evidence.
- `LocalEvidenceError.code` stable admission/conflict/corruption failures. Invalid configuration fails before work; source limit 64 MiB default/256 MiB ceiling, record cap 16 MiB, stored lengths checked before large BLOB retrieval. Records/bytes remain available after replay refusal.

No M2A cached snapshot alone is returned as verified. SourceAdmission is a local binding record, not signed authority; `verified_local` here is explicitly **source-and-m2a**, not a verified M2B–M2F graph. The artifact set purpose is `m2a-replay-v1`; full execution closure, graph commitment and historical environment provisioning belong to M3B. Requests for enhanced-custody return trust_backend_unavailable.

## Verification and remaining work

Independent tests cover six real FIT/GPX positive/negative/gap/no-time files through separate-process reload, distinct source dedup/conflicts, numeric aliases/bool distinction, malformed persisted JSON, corruption and re-hashed M2A forgery, artifact changes/unavailability, simultaneous conflicting processes, and real child process exit immediately before/after commit. CI repeats them in an outside-checkout noneditable wheel. Original M2 bounds/numerical/identity/Node/mutation gates remain.

This is **partial M3A/M3C evidence**: source portions of C01/C02/C04/C05/C08/C09/C10/C11/C12/C17/C18/C23. C09/C23 cover local process crashes, not power-loss hardware certification or enhanced finality. Full C06/C07/C14/C16/C21 need M3B graphs; all observation/complexity/time/RSS F6 budgets, fragment benchmarks, task orchestration/manual decisions, migrations and enhanced services remain open. SQLite OS errors/timeouts are typed M3_STORAGE_FAILED, not hidden success. Local filesystem locking/fsync is assumed; :memory: is rejected, no network-filesystem/hostile-operator/rollback guarantee.
