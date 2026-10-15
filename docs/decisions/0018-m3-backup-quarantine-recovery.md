# ADR-0018 — Basic-local snapshot backup, quarantine and restore

Status: implementation decision pending PR review. Date: 2026-10-15.

A v4 `LocalArchiveStore` provides consistent online SQLite snapshots, offline structural/integrity scanning, evidence quarantine and restore to a new empty path. It creates no database migration or self-referential receipt table. Backup is a single SQLite database snapshot; archive SHA-256 is returned and belongs at an operator-selected independent location if it must survive loss of the same disk. Local hashes detect accidental/inconsistent edits, not an attacker able to replace both evidence and expected digest.

Snapshot uses SQLite online backup, including committed journal/WAL state, then closes, fsyncs and validates the temporary database before no-overwrite atomic hard-link publication. Destination must be a new regular path in an existing directory on the same filesystem as its temporary snapshot. Files are mode 0600. Concurrent application transactions yield one consistent SQLite snapshot. A crash leaves the original intact and at worst an ignored incomplete temp file; cleanup is explicit.

Inspection opens read-only and checks format/version, exact required tables/columns, SQLite integrity, foreign keys, every bounded raw blob and source record, graph root/node closure, every review stream, task request and task event journal, and cross-row source/graph/task references. It does not re-run FIT/GPX parsers or certify algorithms; restore never means verified replay. Post-restore graph/task/review APIs still perform their normal fresh replay. Future schema versions fail closed and require compatible software.

Quarantine copies evidence into a digest-named 0700 directory, preserves the original input, writes a canonical manifest with observed SHA-256/length and caller actor/reason, fsyncs files, then publishes the manifest last. A directory missing the manifest is incomplete, not a valid quarantine receipt. The receipt is local claimed provenance, not signed custody. No automated restore from quarantine and no deletion/purge policy are added.

Default maximum snapshot/quarantine bytes are 2 GiB. This operational ceiling is distinct from source-file and F6 workload budgets. Restore requires a fully inspected backup and a new absent destination; it never overwrites an existing database. Corrupt candidates can be quarantined without opening as SQLite, provided their file size and explicit expected digest match.

This is basic-local recovery from operator error, process failure and accidental corruption. Coherent malicious rewrites/rollback, disk/device failure of all copies, independent media/key custody and enhanced-custody finality are not guaranteed. Operators must store at least one copy and expected digest independently; this API does not schedule, replicate, encrypt or automatically retain backups. Final F6 gates and independent M3 exit audit remain open.

Quarantine actor and reason are each nonblank UTF-8 text capped at 4,096 bytes before any copy is created. Manifest parsing applies strict JSON, exact keys, native integer byte length (no bool-as-int aliases), canonical encoding and content digest verification.
