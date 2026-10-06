# ADR-0008 — Cross-source Activity identity is explicit, never similarity-implied

**Status:** Accepted  
**Date:** 2026-10-06  
**Evidence:** EC-02 architectural compatibility review; EP-04 paired-source evidence

## Context

The same real-world activity may appear in multiple external systems or exports.

Different sources can have:

- different source-native identifiers;
- similar but not identical start times;
- slightly different distances or durations;
- different point counts and track geometry;
- different FIT/GPX export semantics.

Paired-source evidence already shows that two TrackSources belonging to one known Activity can differ structurally. The reverse also matters: two records that look similar are not automatically the same real-world event.

The v0.1 local-file workflow must therefore remain compatible with future multi-source adapters without embedding unsafe approximate deduplication into Activity identity.

## Decision

Activity has a stable project-local identity.

Source-native identifiers belong to source provenance and are namespaced by their source; they are not globally valid Activity identifiers.

v0.1 never infers cross-source Activity identity solely from approximate similarity in:

- timestamp;
- duration;
- distance;
- route geometry;
- activity type;
- any weighted combination of those fields.

When two TrackSources are already explicitly known to describe the same real-world event, they may belong to one Activity.

When identity has not been explicitly established, the records remain separate Activities.

Cross-source reconciliation is an explicit, auditable process outside the v0.1 spatial core. A future adapter/runtime may propose candidate matches, but candidate similarity cannot itself merge Activities.

No cross-source reconciliation entity is added to the v0.1 core.

## Reconciliation compatibility

A future reconciliation mechanism must preserve:

- the original Activity records/identities or their audit lineage;
- all TrackSource provenance;
- the basis and provenance of the equivalence decision;
- the ability to distinguish proposed, accepted, and rejected matches.

The exact reconciliation object, merge/link strategy, and persistence model are deferred to the source-adapter / persistent-runtime milestones.

## Consequences

- local-file v0.1 does not need approximate Activity deduplication;
- source adapters can be added later without changing CanonicalTrack or spatial semantics;
- one Activity may still own multiple TrackSources when sameness is explicit;
- similarity search may assist review but cannot mutate identity;
- repeated ingestion of the same source evidence remains a separate idempotency concern from cross-source equivalence.

## Alternatives rejected

### Merge by approximate start time and distance

Rejected because similar metadata is not identity proof and source exports can differ materially.

### Use source-native activity ID as global Activity identity

Rejected because identifiers are source-scoped.

### Add a reconciliation entity to the v0.1 spatial core

Rejected because the current local-file workflow does not require it and cross-source reconciliation has an independent adapter/runtime lifecycle.

## Follow-up

When multi-source adapters are introduced, add an explicit reconciliation contract before any automated cross-source merge is allowed.
