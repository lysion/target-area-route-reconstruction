# M3D local backup and recovery

Implementation pending PR review; M3 is IN PROGRESS. [ADR-0018](decisions/0018-m3-backup-quarantine-recovery.md) defines the basic-local storage and trust boundary.

```python
from target_area_route_reconstruction import LocalArchiveStore
store = LocalArchiveStore('evidence.sqlite')  # requires supported v4 database
backup = store.create_backup('/mnt/operator-backup/evidence.sqlite')
checked = store.inspect_backup(backup.path)  # read-only structural/integrity scan
restored = store.restore_backup(backup.path, '/var/lib/app/restored.sqlite')  # new path only
```

Snapshot creation uses SQLite online backup, so committed transactions are captured consistently while writers remain active. Publication occurs only after close, fsync, schema/integrity/hash checks and same-filesystem no-overwrite link. A failed or interrupted publication leaves the original database unchanged; incomplete temp files are preserved for operator cleanup. File mode is 0600. Database snapshot SHA-256 and size are returned.

The scanner opens read-only. It verifies schema v4/table/index layout, SQLite integrity and foreign keys, bounded content-addressed raw blobs, complete source records and digest linkage, graph envelope/node closure, M2D assessment bindings for every review chain, task request/journal chains and completed-task selectors. A verified scan establishes local storage consistency, not algorithmic replay or trusted route data. Normal reload APIs still replay original bytes and validate all stages.

Restore accepts only a fully scanned backup and publishes a copied database at an absent destination after a second scan. It never overwrites a current or existing destination. Instantiate the normal store on the restored path; use its explicit source/graph/review/task selectors and expected digests to validate records as needed. A different code/artifact set can leave historical graphs/tasks unverified.

Suspect files can be quarantined without opening SQLite:

```python
saved = store.quarantine_file(
    'suspect.sqlite', '/mnt/quarantine', expected_sha256=observed_digest,
    actor='operator', reason='integrity scan failed')
```

Quarantine copies exact bytes to a content-digest directory and publishes a canonical manifest last. A crash before the manifest leaves an incomplete directory; inspection refuses it and retry does not overwrite it. Source remains in place. Manifest actor and reason are claimed local provenance, not authenticated. Quarantine is preservation only; it cannot be restored as a database without a valid scan.

Limits: one archive ≤2 GiB; raw blobs retain the existing 256 MiB hard source ceiling; record, graph, review and task sublimits continue to apply. Unsupported schema versions fail closed. The API does not schedule backups, replicate to another device, encrypt data, retain keys/digests independently, purge old snapshots, or automatically replace a database. Store at least one copy and expected digest outside the storage failure domain. This remains a trusted-local function: an attacker rewriting both database and expected hash is outside baseline guarantees.

The 2 GiB cap bounds archive bytes. Task wall-time/RSS and a 1,600-part end-to-end profile have passing evidence, while the same-batch M2D fragmentation scaling gate remains open after an unstable run exceeded the 2.8 ratio. Operator restore drills, backup retention, external custody and independent M3 exit audit also remain outstanding.

Quarantine actor and reason each require a nonblank UTF-8 string of at most 4,096 bytes. The manifest reader rejects duplicate/noncanonical JSON, wrong field types (including `true` used as byte length), symlinked files, and content/hash mismatches.
