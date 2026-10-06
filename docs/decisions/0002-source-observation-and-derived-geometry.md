# ADR-0002 — Preserve source evidence and separate normalized observations from cleaned geometry

**Status:** Accepted  
**Date:** 2026-10-06  
**Evidence:** EP-03 scope-limited support; EP-04; FIT/GPX paired cases

## Context

Paired FIT and GPX representations of the same Activity are not lossless equivalents.

Observed differences included:

- point selection;
- segment structure;
- timer/event information;
- initial/final point treatment;
- position representation;
- telemetry availability.

Real trail data also showed that position observations can resume after a gap with temporarily implausible geometric movement relative to device telemetry.

If parsing or cleaning overwrites source evidence, later review cannot distinguish:

- what the source actually contained;
- what normalization changed;
- what a quality algorithm judged to be unreliable.

## Decision

TrackSource and CanonicalTrack remain separate layers.

TrackSource preserves original source evidence and provenance.

CanonicalTrack preserves normalized observation evidence and parser/normalizer provenance.

Judgment-based cleaning, quality filtering, or usable geometry is derived evidence and must not erase or silently replace normalized observations.

Derived quality output must be attributable to a named algorithm/version.

## Consequences

- FIT and GPX may produce separate canonical derivations even when they belong to the same Activity.
- Canonical-source preference is policy, not Activity identity.
- A later parser version may produce a new canonical result from the same immutable TrackSource.
- A valid source position is not automatically equivalent to trusted cleaned geometry.

The exact schema for cleaned/usable geometry remains deferred.

## Alternatives rejected

### Treat FIT and GPX as interchangeable files

Rejected because material source semantics differ.

### Clean before canonicalization and discard the original normalized observations

Rejected because the cleaning decision is algorithmic judgment and must remain auditable.

## Follow-up

EP-03 may continue to collect additional anomaly morphologies, but Milestone 0 does not require an exhaustive GPS anomaly taxonomy.
