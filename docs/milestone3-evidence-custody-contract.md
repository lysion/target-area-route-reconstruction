# Milestone 3 — immutable evidence custody and verifiable derived-snapshot reload contract

**Status: REQUIRED M3 DESIGN / IMPLEMENTATION NOT STARTED.** This is a normative engineering and acceptance contract for the next milestone, not an existing persistence feature, schema release, database implementation, cryptographic proof of vendor authenticity or new seventh M0 core entity.

**Non-negotiable goal:** establish an **immutable original-evidence → complete derived-snapshot binding that can be reloaded, independently verified and never confused with another source, revision, policy, area or algorithm**. A database that merely saves current dictionaries and hashes and can re-hash forged values does **not** satisfy M3.

See [ROADMAP M3](../ROADMAP.md), [post-M2 F3–F6 action owners](post-m2-f3-f6-action-plan.md), [M2 re-exit](milestone2-codex-reexit-review.md), ADR-0002, ADR-0008, ADR-0012 and the frozen M0 six-entity contract. The new custody manifest/receipts are **supporting storage records**, not invented domain core entities.

## 1. Trust and immutability boundary (freeze before writing tables)

1. **At admission, the exact original FIT/GPX byte stream is authoritative.** Compute and verify its `SHA-256(raw_bytes)` when admitting it, not from canonical JSON. Preserve the byte sequence unchanged, including malformed sources with explicit parse failure.
2. **Capture a trusted append-only admission receipt** containing source reference and revision, format, raw byte length, raw digest, intake identifier/time/provenance, and the immutable storage locator. Uniqueness: one `(TrackSource.id, TrackSource.revision_id)` must bind to exactly one raw content digest and custody receipt. Reuse with divergent content is **CONFLICT**, never overwrite, late reassignment or automatic deduplication.
3. **Content deduplication is separate from identity.** Multiple TrackSource revisions may explicitly reference the *same* content-addressed raw blob; their identity and Activity association remain separate. The inverse is not allowed: a single source revision must not silently reference a different blob. Similar time/distance/route does not establish same Activity (ADR-0008).
4. **Blob and receipt cannot share a completely unconstrained mutable trust boundary.** A DB row and its digest, both editable by the same attacker/process, do not detect mutually rewritten raw/source metadata. Choose and test an actual immutability mechanism such as write-once object storage plus restricted append-only receipt/audit log, or a separately anchored signed/HMAC receipt with keys held outside the mutable worker state. State precisely which actor cannot rewrite the trusted receipt. Ordinary SQLite transaction isolation/UNIQUE constraints help consistency but alone do not supply a tamper-resistant trust anchor.
5. **Threat-model honesty:** hashing detects corruption/replacement relative to an independently trusted receipt; it does **not** authenticate whether the original COROS/provider/user-uploaded bytes were genuine at intake, nor resist an attacker who controls both raw storage and the trusted anchoring root. Document this residual limitation, do not overstate `cryptographically verified`.

## 2. Persist the complete evidence graph, not just six entity dictionaries

The storage design must provide durable, versioned, **detached byte-for-byte or canonical-serialization snapshots** for every state that downstream verifiers actually consume, including negative outcomes:

| Node | Mandatory retained content | Exact parent binding |
|---|---|---|
| Raw TrackSource custody | Original bytes, source format, source ref/revision, SHA-256, byte length, immutable admission receipt, intake/acquisition provenance if known | Trust-root receipt; optional explicit Activity association |
| M2A ingestion result | **Complete** `IngestionResult`: `outcome`, `content_hash`, CanonicalTrack or null, ordered diagnostics, `observation_sources`, original source-location indices and parse/normalizer name/version/parameters; unsuccessful import remains a first-class snapshot | Source revision + raw digest + exact parser/normalizer/environment identity |
| M2B QualityProjection/verification | Complete policy, `QualityAlgorithm` name/version/parameters, original `evidence_digest`, canonical parent reference, ordered usable/excluded intervals, gaps, gap constraints and all original-edge diagnostics; verification outcome/structured issues | Exact M2A snapshot digest and CanonicalTrack ref; same source revision |
| M2C SpatialRelationProof/verification | Full spatial authority, target definition/revision/**content digest**, quality projection digest, GIS engine/interpolation version, relation, completeness, assessability, observed coverage/outside/stationary and gap relevance; verifier status/issues | Exact M2B + M2A + TargetArea snapshots; not just geometry equality |
| M2D assembly/verification | Canonical serialized SpatialAssessment **and all** TargetSegments, individual identity/revision, ordinal, lineage, reciprocal references, gap uncertainties, algorithm/version/seed policy and verifier outcome | Exact verified M2C proof, M2B, M2A and target snapshots |
| M2E GeoJSON/map | Export content or regeneration recipe, `include_outside` and renderer/version plus its own digest; separately mark these as **presentational, not spatial authority** | Exact accepted M2D/verified parents |
| Optional M2F metrics/map | Every original-parent-edge fragment, metric and null status, `duration_basis`, `speed_screen_result`, `speed_screen_reason`, cap scope, clip fractions, full original-edge lineage, temporal algorithm/version/mode and display info | Exact M2D/M2E/M2B and original M2A observations; never substitute device speed or observed crossing time |

A `failed`, `non_assessable`, `unsupported` or `unavailable` stage must be persisted as an explicit typed outcome with issues and input fingerprint; it cannot be collapsed into an apparently successful empty result.

**Important:** M2B verification currently needs the full M2A snapshot including diagnostics and observation sources, not only its CanonicalTrack. M2C needs exact area *content* and authoritative projection; M2D needs a verified proof and canonical snapshot. M2F is derived presentation and must never become a fresh source of evidence or self-authenticating authority.

## 3. Versioned directed evidence manifest

Before M3 implementation, document a canonical encoding and hash algorithm for each manifest node, preserving strict JSON raw input rules. A provisional logical record (NOT a frozen new M0 entity or finalized SQL table) is:

```text
CustodyRoot:
  source_ref: {id, revision_id}
  raw: {sha256, byte_length, immutable_blob_locator}
  admission_receipt_id / immutable_anchor
  source_kind, intake_provenance, intake_outcome

DerivedSnapshot:
  type, schema_version
  outcome + structured issues
  content_digest and canonical_serialization_method
  parent_snapshot_digests[]   # ordered, typed, verified
  input_refs[]                # exact id + revision + where relevant content digest
  algorithm: {name, version, exact_parameters}
  execution_environment      # e.g. parser, normalizer, GeographicLib, Shapely, GEOS
  immutable_payload_location
  verification_record         # verifier identity/version/status, separately bound
```

**The receipt and every node must be bound to the same root source**. A target-specific result also requires the *exact TargetArea definition content digest*, not merely a reusable area name or revision string. The graph is acyclic; derived outputs never become observations or authenticate their own ancestors. Persist only explicit user decisions as separate auditable actions (ADR-0009); manual overrides cannot silently rewrite algorithm outcomes.

Revision rules:

- `(id, revision_id)` points to **one immutable content**; identical replay is idempotent, different content is a conflict. Check source and target revisions **independently**.
- Parser/normalizer, M2B, M2C, M2D and M2F algorithm/version/parameters and relevant runtime libraries are part of exact reproducibility authority; upgrading any one may require a new snapshot/revision without rewriting previous evidence.
- CanonicalTrack IDs derived from a TrackSource reference are **not** necessarily stable cross-source or cross-revision Activity identifiers. TargetSegment IDs include assessment seed and are **not** persistent physical road-link IDs; M7/M8 must create a separate network identity model.
- `SHA-256(raw_bytes)` content identity is not the same thing as a source revision, Activity identity, entity schema version, algorithm version or snapshot digest.
- A cache hit is allowed **only** for exact immutable root and complete dependency closure; a matching coordinate sequence or approximate activity metadata is insufficient.

## 4. Trustworthy reload protocol — must fail closed

Reload is a graph-verification operation, not `SELECT ...; json.loads(...)`:

1. Load the trusted original custody receipt **from its declared immutable anchor**; verify source reference/revision, raw locator, byte count and computed raw SHA-256. Any mismatch is `integrity_failure`, quarantined and never upgraded to `success`.
2. Load the original preserved bytes. On an appropriate existing parser/runtime (or a declared historical compatible executable), **independently re-ingest those bytes** with the exact stored TrackSource reference, source kind and parser/normalizer version, and reconcile complete `IngestionResult` including diagnostics, ordered `observation_sources`, failure outcomes and CanonicalTrack content/revision. Never accept a self-consistently rewritten track merely because its embedded hash/revision was recomputed.
3. Load graph nodes in topological order, comparing the stored **canonical bytes/digests**, exact parent digests, refs, policy/parameters and accepted algorithm versions to the trusted root and preceding verified nodes. For each applicable stage invoke the M2B/M2C/M2D independent verifier **in addition to** checking digest lineage. A non-authoritative map is never a substitute for a valid proof.
4. Where full replay is unavailable because an old parser/GEOS version is not installed, produce explicit `historical_unverified` or `engine_unavailable`; retain original blobs and snapshots, but **do not** label the old output currently verified or silently recompute it under a new algorithm into the same identity. Offer separately recorded migration/reprocessing.
5. Cache/reuse only an exact root-verified closed dependency graph whose verification state is valid for the requested operation. On a failed/partial reload, preserve raw and historical audit evidence, refuse downstream success, and report the exact failed node/path.
6. Re-derivation after repair or migration produces **new versioned nodes** with provenance to the original immutable root. Previous snapshots remain readable as historical evidence. No in-place mutation or fabricated reconciliation.

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
