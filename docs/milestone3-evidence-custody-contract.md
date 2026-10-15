# Milestone 3 — persistent evidence and optional enhanced custody contract

**Status: IN PROGRESS; no persistence/custody exit acceptance.** Normative revision 2, 2026-10-14, adopted by [ADR-0013](decisions/0013-m3-layered-persistence-and-custody.md). Supersedes the [historical single-profile contract](history/milestone3-single-profile-contract.md). Strict JSON and basic-local source/M2A admission/replay are implemented, basic full-graph evaluation/replay is implemented, milestone acceptance remains open; see [progress](milestone3-progress.md).

## 1. Profiles and guarantees

| Profile | Trust boundary | Required guarantee | Not guaranteed |
|---|---|---|---|
| `basic-local` (baseline M3) | Trusted application, OS/operator and local storage | Exact evidence binding, corruption/inconsistent-edit detection, deterministic verified replay, conflict prevention, atomic recovery | Compromised worker/operator, coherent replacement of all mutable hashes/raw/graphs, malicious rollback |
| `enhanced-custody` (separate capability acceptance) | Worker may be compromised; signer, independently administered checkpoint and root remain protected | Baseline guarantees plus authenticated source/graph commitments and detection of finalized-history rollback | Signer/checkpoint/root compromise or collusion, pre-admission vendor authenticity |

Mode is an explicit persisted/requested selector. Reload requires expected graph identity and exact source/target/policy selectors. Never pick an arbitrary graph by source hash. Basic supporting verification status is `verified_local`; enhanced status is `verified_custody` only after independent finality. These are M3 API/storage states, not changes to frozen M0 entities or M2 status fields. Missing historical binaries yield `historical_unverified`. An unavailable explicitly requested enhanced backend yields `trust_backend_unavailable`, with no silent fallback. Cached mode/status cannot authenticate enhanced data.

## 2. Shared evidence and identity requirements

- Preserve exact original FIT/GPX bytes, SHA-256 and byte length, including malformed inputs. Application writes are content-addressed/no-overwrite; never mutate admitted bytes or silently replace revisions.
- Bind the **complete schema-valid TrackSource**: schema_version, id, revision_id, activity **{id} only**, origin, representation and extensions when present. Verify representation.content_hash if present. Canonical TrackSource digest and source revision bind raw bytes and Activity exactly once; contradictory concurrent admissions are conflicts. Deduplication of raw content does not merge TrackSource or Activity identity. Reconciliation is a separate auditable decision.
- Freeze a versioned strict canonical manifest encoding before tables: UTF-8, package strict lexical admission, ordered typed parent links, SHA-256; specify numeric serialization and identity without altering current M2 hashes. Source-admission encoding/storage is frozen in [ADR-0014](decisions/0014-m3-local-source-admission-storage.md); full DAG encoding is frozen in [ADR-0015](decisions/0015-m3-basic-local-derived-graphs.md), with cold replay implemented separately from the lexical decoder.
- Persist complete detached M2A IngestionResult (diagnostics and observation_sources included); M2B policy/algorithm, usable/excluded intervals, gaps/constraints and edge diagnostics; M2C authority, full target content, coverage/outside/stationary and gap relevance; M2D assessment and every ordered TargetSegment; optional M2E output/renderer recipe and optional M2F fragments, time allocation, parent screening and null reasons. Presentations/metrics are not fresh spatial authority.
- Each typed node records payload digest, exact ordered parent digests, id/revision/content selectors, algorithm parameters, actual wheel/module/native-library and environment artifact hashes, and verification outcome/issues. Validate a closed acyclic graph. Preserve failed/non_assessable/unsupported/unavailable stages explicitly; no successful empty replacement.
- Independently verify full input chain on reload before reuse: raw integrity, exact source binding, artifact availability, fresh M2A re-ingest, M2B/M2C/M2D verifiers and optional M2E/M2F provenance. Compare against the **explicit expected immutable graph**. Unavailable exact execution artifacts preserve historical evidence and return unverified, not a current-engine substitute. Storing hashes next to mutable data is not hostile-storage authentication.
- Publish atomically only after all required nodes and verification records are durable. Staging is never reusable as a verified graph. Retry is idempotent; crashes/concurrent writers cannot publish half an assessment or silently overwrite identity. Cache keys include the complete source/target/policy/artifact closure and profile.
- Apply F5 strict JSON at every persisted admission. Enforce F6 default/hard ceilings before unbounded work and roll back failed derived publication. Preserve F3 conditional continuity and F4 derived clipped-time semantics; never invent gap paths or observed boundary timestamps.

## 3. Basic-local storage and replay

Use SQLite transactions for identity/manifests/task state plus content-addressed raw/snapshot storage, unless a justified equivalent preserves these requirements. File-plus-DB publication requires a defined fsync/staging/recovery protocol; a SQL commit alone does not prove blob durability. Freeze uniqueness constraints, schema/migration versions, corruption/quarantine handling and manual-decision audit before implementation.

Supporting `SourceAdmission` binds full source/raw; `GraphCommit` binds the closed DAG and request selectors. In basic mode these are **local integrity records, not authenticated receipts**. Application no-overwrite and conflict tests remain mandatory. A trusted caller may retain an expected digest externally for additional detection, but the baseline does not assume a separately protected authority. A compromised writer can coherently replace these records or replay all local state; disclose this limit at API and user-facing export boundaries.

## 4. Enhanced-custody extension

Retain the selected Linux-first Ed25519 hash-chained signed log. Worker has no private key or log/checkpoint mutation authority; signer independently verifies full source/raw and graph closure before signing. Checkpoint authority is administered independently and stores a monotone latest sequence/head outside worker **and signer** control. Verifier obtains public keys/checkpoint independently of mutable caches.

Different Linux accounts are necessary but insufficient. Before enhanced acceptance demonstrate worker cannot read key, append/edit/truncate/rename/delete logs or alter checkpoint; signer cannot rewrite old records or alter checkpoint. Ordinary writable files/directories do not establish append-only behavior. Specify and test the actual protected append mechanism (e.g. storage-enforced retention under a separate log owner) and recovery/admin boundaries. If no such mechanism is available, enhanced mode remains unavailable; basic mode is still separately usable when explicitly selected.

Two receipt kinds are independently signed: `SourceAdmission` (full source/raw) and `GraphCommit` (full DAG root, source receipt digest, target/policy/artifact selectors). Both are signed once; finality must never change their bytes/digests. Append yields `PENDING_CHECKPOINT`. A distinct checkpoint-owner-signed finality record binds unchanged receipt digest/sequence and inclusion in independently trusted latest log head. Only then may the receipt/graph yield `verified_custody`. Source finality precedes graph signing. Crashes between append, finality and DB publication recover idempotently; no tail truncation or pending-success publication. Key rotation and administrative recovery are auditable. Enhanced upgrade of existing basic data requires new validated admission and signed graph, not relabeling old rows.

## 5. C01–C23 acceptance mapping

All cases below remain tracked. **B** is mandatory baseline evidence; **E** is additional enhanced evidence. An E-only case omitted from basic acceptance is explicitly NOT_IMPLEMENTED/NOT_TESTED, never PASS. Enhanced acceptance requires every B and E requirement.

| ID | Scenario | Basic-local requirement | Additional enhanced requirement |
|---|---|---|---|
| C01 | Raw byte/blob substitution | B: reject against admitted raw digest and expected local graph | E: authenticate raw against trusted receipt |
| C02 | Rewrite observations and internal hashes | B: reject against fresh re-ingest and expected graph | E: signed root independently binds graph |
| C03 | Coherently replace raw and all local records | Outside baseline hostile-writer guarantee; document | E: reject against protected source receipt |
| C04 | Same source revision, different bytes/concurrent writers | B: hard identity conflict | E: signer also rejects conflict |
| C05 | Same bytes, distinct source refs | B: dedup bytes without identity/Activity merge | E: separate source receipts |
| C06 | Splice source/policy/area/proof | B: reject typed parents and exact content selectors | E: anchored manifest check |
| C07 | Replace segment/ordinal/gap/metrics | B: reject expected snapshot and parent-edge mismatch | E: anchored manifest check |
| C08 | Historical algorithm unavailable | B: historical_unverified; preserve raw/snapshots | E: same, never accept by signature alone |
| C09 | Crash during blob/graph publication | B: no partial verified graph; recover staging | E: include receipt/finality domains |
| C10 | Retry/idempotence/cache after crash | B: no duplicate facts; verify before cache reuse | E: verify finality too |
| C11 | No-position, invalid GPX, missing time | B: retain exact negative/null outcomes | E: bind negative graph receipts |
| C12 | Duplicate/underflow/nonfinite/Unicode JSON | B: fixture/runtime/storage parity | E: signer admission parity |
| C13 | Over-budget/fragmentation inputs | B: F6 limits, performance and clean rollback | E: no partial signed publication |
| C14 | F4 clipped-time allocation | B: preserve derived provenance and parent cap scope | E: signed provenance closure |
| C15 | F3 timer/sparse sampling | B: retain conditional coverage semantics | E: same; signature adds no motion truth |
| C16 | Coherent target/policy/whole-DAG rewrite | B: reject against independently provided expected graph when retained; hostile replacement of local expectation is outside guarantee | E: protected GraphCommit must reject even with all local hashes rewritten |
| C17 | Reassign source Activity/provenance | B: no-overwrite full source binding, replay comparison | E: signed full-source digest |
| C18 | Same-version executable replacement | B: actual digest mismatch/unavailable -> unverified | E: anchored artifact set |
| C19 | Hide finalized history/replay old checkpoint | Outside baseline rollback guarantee; document | E: latest independent checkpoint rejects |
| C20 | Compromised worker key/log/checkpoint access | Outside baseline threat model; document | E: real principals and protected append controls deny attacks |
| C21 | Same source, multiple valid targets | B: explicit graph selection or ambiguity | E: select exact expected signed graph |
| C22 | Performance/ceilings | B: reproducible F6 profile, immediate hard-ceiling refusal | E: same plus publication boundaries |
| C23 | Receipt append/finality/DB crashes | B: local prepare/commit recovery, no claimed signed finality | E: immutable receipt before/after separate finality; pending never authoritative |

## 6. Implementation order and exit

- **M3A:** basic raw/full-source storage, identity conflicts and negative outcomes; define encoding and transaction recovery before tables. No multi-principal deployment prerequisite for this profile.
- **M3B:** complete DAG, explicit graph selectors, actual artifact hashes and separate-process verified replay.
- **M3C:** idempotence, concurrency, crash recovery, exact cache and manual audit. [Manual audit](milestone3c-manual-review.md) is implemented with local transactional predecessor checks; [caller-driven task lifecycle and exact verified reuse](milestone3c-task-runtime.md) are implemented; [basic-local snapshot backup, evidence quarantine and no-overwrite restore](milestone3d-backup-recovery.md) are implemented; scheduling/retention and F6 gates remain open.
- **M3D:** storage F5 integration, all F6 admission budgets, reproducible performance/scaling evidence and independent exit audit.
- **Enhanced extension:** independently deploy/test signer, protected log and checkpoint/finality; satisfy E requirements before claiming enhanced capability. This does not block basic-local M3 exit.

Baseline exit requires all B cases, real FIT and GPX fresh import → process exit → installed-wheel new-process reload, negative/gap/no-time cases, unchanged M2 outputs and independent integrity tests. Publish scope as **M3 basic-local accepted; enhanced-custody unavailable or separately accepted**. No generic tamper-proof claim. Enhanced mode acceptance additionally requires all E cases and real deployment evidence. M3 remains IN PROGRESS until actual baseline evidence exists; the current graph API is not milestone or enhanced-service acceptance.
