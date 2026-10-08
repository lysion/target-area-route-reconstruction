# Milestone 3 — immutable evidence custody and verifiable derived-snapshot reload contract

**Status: REQUIRED M3 DESIGN / IMPLEMENTATION NOT STARTED.** This is a normative engineering and acceptance contract for the next milestone, not an existing persistence feature, schema release, database implementation, cryptographic proof of vendor authenticity or new seventh M0 core entity.

**Non-negotiable goal:** establish an **immutable original-evidence → complete derived-snapshot binding that can be reloaded, independently verified and never confused with another source, revision, policy, area or algorithm**. A database that merely saves current dictionaries and hashes and can re-hash forged values does **not** satisfy M3.

See [ROADMAP M3](../ROADMAP.md), [post-M2 F3–F6 action owners](post-m2-f3-f6-action-plan.md), [M2 re-exit](milestone2-codex-reexit-review.md), ADR-0002, ADR-0008, ADR-0012 and the frozen M0 six-entity contract. The new custody manifest/receipts are **supporting storage records**, not invented domain core entities.

## 1. Trust and immutability boundary (freeze before writing tables)

1. **At admission, the exact original FIT/GPX byte stream is authoritative.** Compute and verify its `SHA-256(raw_bytes)` when admitting it, not from canonical JSON. Preserve the byte sequence unchanged, including malformed sources with explicit parse failure.
2. **Capture a trusted append-only source admission receipt** containing the **complete canonical frozen TrackSource revision** (not only `{id,revision_id}`): `schema_version`, `id`, `revision_id`, `activity:{id,revision_id}`, `origin`, `representation` and present `extensions`, plus canonical TrackSource SHA-256, raw format, byte length, raw SHA-256, immutable blob locator and intake record. `representation.content_hash`, when present, must equal the verified raw content. The complete TrackSource revision is bound exactly once: changing Activity reference, origin, representation, raw bytes or revision is a **CONFLICT**, even when the original bytes remain unchanged. Do not silently mutate the old association.
3. **Content deduplication is separate from identity.** Multiple TrackSource revisions may explicitly reference the *same* content-addressed raw blob; their **signed complete TrackSource payloads and Activity references** remain separate. One source revision cannot silently refer to another blob **or another Activity**. Later cross-source reconciliation is a separate append-only auditable decision with explicit provenance (ADR-0008), not an in-place edit to the originally admitted TrackSource revision.
4. **Concrete M3 v0.2 trust mechanism (chosen design; changing it requires a reviewed superseding decision):** Linux-local **split-principal, Ed25519-signed, hash-chained append-only custody log**. The normal SQLite/import worker cannot access the signer private key or amend the receipt log. A distinct custody signer service verifies the complete TrackSource revision, immutable raw bytes **and complete derived-graph manifest closure** before signing two immutable receipt kinds: (a) `SourceAdmission` and (b) `GraphCommit`. A distinct protected checkpoint authority pins the monotone signed log head/sequence **outside worker-editable storage**, so a deleted/hid/replayed log tail fails verified reload. The receipt log is append-only under a separate OS principal with enforced filesystem/log-store permissions, **not merely an append-only SQL table**; checkpoint and public verification key are root/operator controlled. Signer rotation and receipt rollback are auditable, not silent. Before implementation, test these exact Linux principal/permissions/append/checkpoint controls; another OS or trust backend needs an explicit alternative architecture review.
5. **Threat-model honesty:** the scheme detects a **compromised import worker** changing SQLite records/blobs/snapshot DAG/policies/areas, suppressing signed log entries or trying to replay old state while signer key and independent checkpoint stay protected. Hashes alone do not authenticate input provenance, and a malicious signer, checkpoint operator/root compromise, lost trusted checkpoint, broken signature implementation or colluding privileged actors fall outside that guarantee. Document availability/rotation/recovery as failure-closed, and never call third-party device telemetry intrinsically authentic.

## 1A. Selected signer/checkpoint boundary and actor capabilities

This is a **single concrete Linux-first design**, not a choice left open to the implementation author. A separate signed-log trust service is necessary even when the working store is SQLite. Checkpoint authority must be independently administered and must keep the monotone latest **signed log-head digest + sequence** in a store inaccessible to the normal worker and signer; a read-only verifier is configured with its trusted public key and checkpoint source.

| Principal | May append/sign | May verify/read | May replace/delete or roll back old receipts/checkpoint | Authority constraints |
|---|---|---|---|---|
| Untrusted importer / SQLite worker (`runtime`) | **No**; may only submit validated proposals | May read public key and receipts | **No** | Can mutate its own cache, temporary blobs and task state, but cannot obtain private key or modify receipt/checkpoint store |
| Custody signer service (`custody-signer`) | **Yes, append-only after independently checking full TrackSource + raw + complete derivation DAG and uniqueness** | Yes | **No** (separate write-only append permission, protected log and externally pinned latest head) | Owns private Ed25519 key, denies signing same source revision with different full TrackSource content, and cannot uncommit a published receipt |
| Checkpoint authority (`checkpoint-owner`, separate OS/security principal) | Pins/attests newest signer-verified sequence and log-head hash, never signs derived data itself | Yes | **No during ordinary operation**; audited administrator recovery is out of worker threat model | Independent monotone root must detect hidden tail/rollback. Key rotation requires signed predecessor/successor rotation event plus independently pinned checkpoint |
| Read-only reload verifier | No | **Yes**, uses independently obtained checkpoint and trusted signer public key | No | Must reject absent/old/untrusted graph or signer identity; cannot trust a checkpoint supplied alongside mutable cache |
| System owner/root or compromised signer/checkpoint | Can defeat these controls | Yes | **Outside stated integrity guarantee** | Must be explicitly described rather than claiming unlimited tamper proof |

**Required process test before M3A acceptance:** launch worker and signer under distinct least-privilege service accounts; verify worker cannot read/export the signer key, append/edit/truncate/rename/delete receipt log, roll back checkpoint, or request a conflicting signature; verify signer cannot rewrite existing entries or alter checkpoint authority, and verifier fails closed when log entries are removed or an older signed head is replayed. If a target platform cannot enforce the selected append-only/independent-checkpoint boundary, it must be marked `trust_backend_unavailable`, not silently downgraded to ordinary mutable SQLite.

**Do not conflate an append-only *claim* with a security property:** tests must demonstrate permissions/independent checkpoint, backup/recovery and consistency after crash. Implementing this design may require an explicit service separation not present in M2; this is a new M3 design commitment, not a statement that it already works.

## 2. Persist the complete evidence graph, not just six entity dictionaries

The storage design must provide durable, versioned, **detached byte-for-byte or canonical-serialization snapshots** for every state that downstream verifiers actually consume, including negative outcomes:

| Node | Mandatory retained content | Exact parent binding |
|---|---|---|
| Raw TrackSource custody | Original bytes, canonical **complete TrackSource** (`schema_version,id,revision_id,activity,origin,representation,extensions` when present), canonical TrackSource SHA-256, source format, original raw SHA-256/byte length and immutable signed admission receipt | Trusted signed SourceAdmission commits the **full Activity reference and all TrackSource provenance**; any new reconciliation is a new independent signed event, never an in-place reassignment |
| M2A ingestion result | **Complete** `IngestionResult`: `outcome`, `content_hash`, CanonicalTrack or null, ordered diagnostics, `observation_sources`, original source-location indices and parse/normalizer name/version/parameters; unsuccessful import remains a first-class snapshot | Source revision + raw digest + exact parser/normalizer/environment identity |
| M2B QualityProjection/verification | Complete policy, `QualityAlgorithm` name/version/parameters, original `evidence_digest`, canonical parent reference, ordered usable/excluded intervals, gaps, gap constraints and all original-edge diagnostics; verification outcome/structured issues | Exact M2A snapshot digest and CanonicalTrack ref; same source revision |
| M2C SpatialRelationProof/verification | Full spatial authority, target definition/revision/**content digest**, quality projection digest, GIS engine/interpolation version, relation, completeness, assessability, observed coverage/outside/stationary and gap relevance; verifier status/issues | Exact M2B + M2A + TargetArea snapshots; not just geometry equality |
| M2D assembly/verification | Canonical serialized SpatialAssessment **and all** TargetSegments, individual identity/revision, ordinal, lineage, reciprocal references, gap uncertainties, algorithm/version/seed policy and verifier outcome | Exact verified M2C proof, M2B, M2A and target snapshots |
| M2E GeoJSON/map | Export content or regeneration recipe, `include_outside` and renderer/version plus its own digest; separately mark these as **presentational, not spatial authority** | Exact accepted M2D/verified parents |
| Optional M2F metrics/map | Every original-parent-edge fragment, metric and null status, `duration_basis`, `speed_screen_result`, `speed_screen_reason`, cap scope, clip fractions, full original-edge lineage, temporal algorithm/version/mode and display info | Exact M2D/M2E/M2B and original M2A observations; never substitute device speed or observed crossing time |

A `failed`, `non_assessable`, `unsupported` or `unavailable` stage must be persisted as an explicit typed outcome with issues and input fingerprint; it cannot be collapsed into an apparently successful empty result.

**Important:** M2B verification currently needs the full M2A snapshot including diagnostics and observation sources, not only its CanonicalTrack. M2C needs exact area *content* and authoritative projection; M2D needs a verified proof and canonical snapshot. M2F is derived presentation and must never become a fresh source of evidence or self-authenticating authority.

## 3. Versioned directed evidence manifest

Before M3 implementation, freeze the strict canonical encoding and hash algorithm for every manifest node. **Two distinct signed append-only receipts are required**, because the original byte intake exists before later target-specific derivations. SourceAdmission alone is NOT a commitment to any later derived snapshot.

```text
SourceAdmissionReceipt (signed, append-only, chained):
  canonical_track_source_snapshot: full frozen TrackSource object
  full_track_source_sha256: SHA256(canonical(full TrackSource))
  original_activity_ref: TrackSource.activity     # mandatory, not optional
  raw: {sha256, byte_length, immutable_blob_locator}
  source_kind, intake_provenance, intake_outcome
  receipt_sequence, previous_receipt_hash, signer_key_id, signature

DerivedSnapshot (immutable typed DAG node):
  type, schema_version, outcome + structured issues
  payload_digest: SHA256(canonical(payload))
  parent_snapshot_digests[]       # ordered, typed, verified; includes root receipt
  input_refs[]                    # exact id + revision + content digest
  algorithm: {name, version, exact_parameters}
  executable_artifact_manifests[] # actual wheel/module/native-binary digest + OS/ABI
  verification_record             # verifier outcome/engine + its artifact digest
  immutable_payload_location

GraphCommitReceipt (signed, append-only, chained):
  source_admission_receipt_digest
  graph_root_manifest_digest: SHA256(canonical(closed typed DAG manifest))
  graph_manifest_location
  exact_target_area_snapshot_digest, policy_digest, algorithm_artifact_set_digest
  ordered_verified_derived_node_digests[] / closure digest
  outcome, committed_at, receipt_sequence, previous_receipt_hash
  signer_key_id, signature
```

**Critical binding rule:** the signer validates a closed, acyclic derivation manifest, its original SourceAdmission, full TrackSource payload (including Activity, origin and representation), every raw/target/policy/algorithm input and all required independent verifiers **before** signing/publishing GraphCommit. The **graph-root manifest digest is published into the separately protected signed append-only trust anchor**; it is not merely a mutable `sha256` column next to the cached graph. If the user requests an accepted assessment, reload resolves an **explicit expected GraphCommit receipt ID/digest** from the trusted log or from a separately trusted caller. It cannot simply choose the most convenient currently present, internally valid graph.

The original bytes can legitimately generate multiple different *separately signed* commits under distinct TargetArea revisions, quality policies, algorithm builds or runs. Those are **different immutable derived results**, not indistinguishable replacements. Each commit is bound to its exact request/policy/target selectors; never choose a result using only source hash or closest geometry. If the requested selectors match multiple authorized histories, return all identities or an explicit ambiguity requiring a caller choice, not a silent last-write-wins selection. A coordinated rewrite of TargetArea + policy + all descendants now fails because it cannot reproduce the **externally signed original graph-root manifest digest** without the independent signer.

**The signed SourceAdmission AND the signed GraphCommit and every typed node must be bound to the same complete TrackSource revision, source Activity reference and original raw bytes**. A target-specific result additionally requires the *exact TargetArea definition content digest*, not merely an area name or revision string. A stable graph/manifest **commit identity** and exact caller selectors are required for unambiguous reload. The graph is acyclic; derived outputs never become observations or authenticate their own ancestors. Persist explicit user decisions and later cross-source reconciliations as independently append-only auditable records (ADR-0009/0008); neither can mutate TrackSource.activity or silently rewrite algorithm results.

Revision rules:

- `(id, revision_id)` points to **one immutable content**; identical replay is idempotent, different content is a conflict. Check source and target revisions **independently**.
- Parser/normalizer, M2B, M2C, M2D and M2F algorithm/version/parameters and relevant runtime libraries are part of exact reproducibility authority. **Names and semantic versions are insufficient:** bind a signed or separately anchored immutable **executable artifact manifest** with SHA-256 hashes of Python wheels, project modules, independent verifier implementations, dependency lock, native GEOS/shared libraries and required OS/ABI/runtime build identity. A same-version-but-rebuilt/patched binary is a distinct artifact and must never silently validate old commitments. Upgrading any one yields a new derived snapshot/GraphCommit rather than rewriting previous evidence.
- CanonicalTrack IDs derived from a TrackSource reference are **not** necessarily stable cross-source or cross-revision Activity identifiers. TargetSegment IDs include assessment seed and are **not** persistent physical road-link IDs; M7/M8 must create a separate network identity model.
- `SHA-256(raw_bytes)` content identity is not the same thing as a source revision, Activity identity, entity schema version, algorithm version or snapshot digest.
- A cache hit is allowed **only** for exact immutable root and complete dependency closure; a matching coordinate sequence or approximate activity metadata is insufficient.

## 4. Trustworthy reload protocol — must fail closed

Reload is a graph-verification operation, not `SELECT ...; json.loads(...)`:

1. From the independent checkpoint and trusted Ed25519 public key, verify the monotonic append-only **signed receipt chain** (sequence, previous entry hash, checkpoint log head and signer rotation). Require a **specific signed GraphCommit ID/digest** and signed SourceAdmission ID/digest for the requested output; a mutable DB-selected manifest digest or an older truncated log is not authority.
2. Verify SourceAdmission's complete frozen TrackSource bytes/digest, `activity`, `origin`, `representation`, raw byte locator, byte count and independently recomputed SHA-256. Changed Activity affiliation **without a distinct signed reconciliation record** or changed source revision is an integrity/identity conflict. Preserve original source associations even after separately audited reconciliation.
3. Verify **GraphCommit.graph_root_manifest_digest** by canonicalizing the *entire* closed DAG, typed parent and node hashes, exact request selectors, complete TargetArea payload hash, quality parameters, null/negative outcomes, verification records and executable artifact manifest. A coordinated replacement of ALL descendants (even if self-consistent and based on genuine unchanged raw) must be rejected against the **already signed expected graph digest**. Enforce no missing/extra parent edges and no substituted newer commit.
4. Load original bytes and re-ingest with the **exact attested parser/normalizer executable artifact hashes** and full original TrackSource reference; reconcile full `IngestionResult`, diagnostics, `observation_sources`, failures and CanonicalTrack. Check typed downstream nodes in topological order using stored canonical digests, source/target/policy selectors, required algorithm/runtime binary hashes and M2B/M2C/M2D independent verifiers; non-authoritative map never substitutes for proof.
5. If the exact historical implementation or native library binary with its committed digest is unavailable, return `historical_unverified` / `engine_unavailable` (or `artifact_digest_mismatch` when installed code differs). A patch/rebuild with the same version string is **not equivalent**. Retain old evidence but never silently verify/rewrite under the latest version.
6. Cache/reuse only a specific signed GraphCommit whose **complete closure** and requested selectors passed. On any root/manifest/receipt mismatch, quarantine the exact failed node and refuse authoritative downstream use. A newly desired policy, area or engine must produce **a newly signed append-only GraphCommit**, not mutate or silently replace the previous commit.
7. Re-derivation, parser migration or explicit Activity reconciliation produces fresh signed records referencing original immutable history. Never hide or delete the prior SourceAdmission or graph receipt.

## 5. Transaction, idempotency and interrupted work

- Implement atomic custody admission: persist the raw blob and trusted receipt before publishing any derived success; a crash before commit must leave no visible authoritative orphan claim. If storage spans DB and blob objects, use staged/pending→committed protocol with verification and garbage-collection rules; a DB transaction alone cannot atomically cover a remote filesystem/object store.
- Explicit lifecycle states include (names can be refined): `acquired / raw_verified / parsed / quality_verified / spatial_verified / assembled / exported`, `failed / non_assessable / interrupted / retryable / integrity_failure`; every transition binds exact predecessor and is auditable.
- Retry the same source/ref/algorithm/area: return the exact prior immutable snapshot when valid, no duplicate facts or changed IDs. Distinct source refs with identical bytes remain distinct unless explicitly linked.
- Concurrent writers trying to assign different content to one `(source.id,revision_id)` must deterministically produce one immutable commitment and a conflict for the other; database uniqueness alone is not sufficient if blobs could later be replaced.
- Publish mutually referencing SpatialAssessment/TargetSegments **atomically**. Interrupted assembly must never expose a half-complete "verified" result.
- Integrity failure is permanent/quarantined pending explicit authorized resolution; retryable network/environment failure remains distinct from success, empty or absent source evidence.

## 6. Mandatory independent attack and integration acceptance matrix

The tests below are **M3 exit blockers**, not optional documentation examples. Construct mutated persisted states *after a successful control run* and verify exact fail-closed outcomes; run against an installed, noneditable package and a disposable persistent store where feasible.

| ID | Attack / scenario | Required observable outcome |
|---|---|---|
| C01 | Flip one original FIT/GPX byte or substitute another valid raw file at same blob locator | Fail against separately trusted custody receipt before any downstream `verified` result |
| C02 | Rewrite canonical observations + internal `content_hash` + self-consistent revision/digests without changing immutable original raw/receipt | Reject on re-ingest/root lineage comparison; cannot report verified CanonicalTrack |
| C03 | Change raw + recompute **all** mutable DB hashes/derived snapshots, but leave independently anchored admission receipt untouched | Fail root receipt check. Document actor/key controls and limits: an attacker controlling the anchor too is out of the claimed detection scope |
| C04 | Reuse identical `(TrackSource.id,revision_id)` with different bytes; also test simultaneous conflicting writers | Hard identity conflict; never last-write-wins or silent revision replacement |
| C05 | Store identical blob under two distinct source refs; use similar time/distance metadata | Blob may dedup physically; TrackSource refs/Activity associations remain separate |
| C06 | Swap QualityProjection from another source or same source with changed policy; splice valid looking M2C proof/TargetArea from another revision | Reject exact typed parent digest, policy, target content and verifier checks |
| C07 | Replace one TargetSegment or its ordinal, gap, reciprocal reference; splice M2F speed diagnostics from another original parent edge | Reject immutable M2D snapshot and M2F parent-edge provenance; never draw a trusted cross-gap metric |
| C08 | Saved historic algorithm/runtime version unavailable on current worker | Preserve original bytes and historical snapshot; return `historical_unverified` / explicit unavailable rather than silently validate with latest |
| C09 | Crash between blob upload/receipt/DB commit, or between assessment and its segment publication | Staged/atomic recovery; no orphan "complete" or half verified entities |
| C10 | Re-import identical file/id/revision/policy/area; cache read after crash | Exact idempotence: same snapshots, no duplicate facts; cache hit only after successful root/lineage verification |
| C11 | Valid but no-position FIT, invalid GPX, corrupted raw evidence, missing timestamps | Explicit negative/unavailable outcomes and diagnostics persist/reload; never synthesize successful empty assessment or numeric speed |
| C12 | Apply F5 malformed/duplicate/underflow JSON through fixture vs runtime vs persistence input | Strict rejection parity with stable reason; no silent numeric or duplicate-key coercion |
| C13 | Apply F6 oversized file, extreme fragmentation/target complexity, output budget exceed | Explicit resource-limit failure and clean rollback; no silent truncation, memory runaway or partial trusted result |
| C14 | Persist F4 clipped edge with numeric `valid` but proportional duration and parent-screened cap different from clipped speed | Reload exact `duration_basis`, source parent refs and `speed_screen_result/reason`; do not turn into observed arrival time or certified local speed |
| C15 | FIT timer stop/start and large sparse Record gap under unchanged v0.1 policy | Retain exact raw source and declared continuity assumption; never relabel source coverage as physically certified without new policy/evidence |

**Required positive evidence:** at least one genuine synthetic FIT and one GPX must perform fresh import → durable root receipt → complete M2A/M2B/M2C/M2D → M2E/M2F optional export → process exit → reload in a new process → independent verify → deterministic same-result or explicitly recorded version migration. Must include gap/no-timestamp failures and source provenance, not only a 1-point happy path.

## 7. Implementation stages and completion rule

- **M3 design freeze:** agree immutable anchor and threat model, normalized manifest serialization, duplicate/conflict semantics, re-ingest strategy for historic parser versions, and staged transaction model; accept this document's requirements without changing frozen M0/M1 six entities.
- **M3A — custody foundation:** immutable source bytes, separately trusted admission receipt, stable TrackSource revision uniqueness, negative evidence and integrity-state storage, basic C01–C05 / C09.
- **M3B — snapshot graph and reload:** complete typed M2A–M2F dependency records, topology verification, deterministic re-ingest and independent M2B/M2C/M2D verifiers; C02/C06–C08/C11/C14/C15.
- **M3C — idempotent runtime:** retry/resume, crash recovery, concurrency, exact cache keys and manual decision audit C09/C10.
- **M3D — reliability gates:** [F5](post-m2-f3-f6-action-plan.md) strict JSON parity C12; [F6](post-m2-f3-f6-action-plan.md) budgets/performance/linearized scans C13, and measured load behavior before large historical ingestion.
- **M3 exit:** passing unit, adversarial, installed-wheel **and restart/reload persistent integration** tests, exact final-head CI and independent scrutiny of real attack behavior; ROADMAP may mark M3 DONE only after recorded evidence. **M3 is NOT STARTED until a subsequent implementation PR actually begins.**

**Rule of interpretation:** this document **establishes the required binding contract**; it does not claim that immutable custody, SQLite tables, independent anchor, reload verifier or M3 tests have already been implemented.
