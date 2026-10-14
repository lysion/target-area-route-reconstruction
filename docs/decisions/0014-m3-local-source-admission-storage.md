# ADR-0014 — Basic-local source admission encoding and atomic storage

**Status:** Implementation decision, pending PR review. **Date:** 2026-10-14.
**Scope:** M3A basic-local source/M2A records; no domain schema change, enhanced signatures or complete M3B graph claim.

## Encoding v1

`m3-local-source-v1` encodes exact native finite JSON using UTF-8, lexicographically sorted object keys, compact separators, no ASCII escaping and no NaN. JSON number aliases are canonicalized mathematically: finite integral floats become exact Python integers, negative zero becomes integer zero; booleans remain booleans. Nonintegral binary64 values use Python's round-trip JSON encoding. No coordinate approximation, Unicode normalization or array reordering is allowed. Unsupported classes, tuple/subclass/missing or malformed Unicode values fail before hashing. SHA-256 covers these bytes. Input from raw JSON uses the shared strict decoder before normalization. This supporting encoding does not replace M2 identity algorithms.

TrackSource is schema-validated completely and normalized with this encoding. Stored full M2A output is its exact existing `to_json()` string, so declared field types/codec and diagnostics are preserved unchanged; no lossy reconstruction from a subset. Source record binds complete source, raw SHA/length/kind, exact parser artifact manifest, ingestion JSON, profile and encoding version. There are no timestamps or paths in its identity seed.

## Atomic SQLite storage

Use SQLite BLOBs for raw content, keyed by SHA-256, and a separate source-admission table keyed by `(source_id, revision_id)`; source identities do not merge when blob content deduplicates. This deliberately keeps raw and admission publication in **one SQLite transaction**, avoiding a cross-file fsync/DB commit protocol at this stage. Schema user_version=1, foreign keys, rollback journal DELETE, synchronous FULL and BEGIN IMMEDIATE provide publication and conflict serialization. Supported deployment is a trusted local filesystem honoring SQLite locking/fsync. Network filesystems and hostile-storage resilience are not claimed.

Hash/read integrity is rechecked on every retrieval, using explicit expected record digest. No last-write-wins updates, unknown automatic migrations, trusted partial admissions or default enhanced fallback. Source-only APIs do not migrate; opting into LocalGraphStore performs the explicit additive v1→v2 transition frozen in [ADR-0015](0015-m3-basic-local-derived-graphs.md). Exact retry returns the existing immutable record even if current parser artifacts differ; verified reload still checks artifact equality and reports historical_unverified instead of rewriting old evidence. SQLite raw blobs and records are application-immutable, not privileged-write-proof. No mutable verified flag is authoritative.

M3A stores parser failures/no-position evidence too. Read budget defaults to 64 MiB, hard cap 256 MiB, including bytes-entry checks and retrieved blob length before allocation. Record JSON cap is 16 MiB. Processing/observation/time/RSS caps are remaining M3D work; byte limits alone do not bound parsing CPU or expansion. A rejected admission publishes neither raw nor record. If a source was previously committed, later replay failure preserves it.

## Recovery and interfaces

SQLite rollback/recovery handles process death before commit; blobs and records become visible together after commit. Fault tests must exercise a real child process terminated immediately before/after commit, concurrent conflicting admissions, committed blob corruption and deterministic new-process reload. Uncommitted raw inserts have no verified publication. No automatic deletion/quarantine of suspected bytes; errors preserve storage for investigation. Unknown schema version fails closed. Full manual decisions, derived graph commits and task resume are later M3B/C records, not implicit capabilities of this source table.
