# Normalized evidence and usable geometry

This is the deterministic hand-off contract for Milestone 2, established during M1 remediation. It does not add a core entity or change ADR-0004/0005/0007 ownership. Production quality algorithms are not implemented in M1.

## Evidence remains immutable

TrackSource retains the raw bytes/stream evidence. CanonicalTrack retains normalized positioned observations, including suspicious coordinates, repeated positions and optional telemetry. Quality rejection never deletes, sorts, moves or reindexes these observations. A new normalizer result is a new CanonicalTrack revision, never an edit of the old revision.

A FIT Record lacking a valid position cannot become a positioned canonical observation. The raw Record remains in TrackSource, and the normalizer's diagnostic result must retain its source location and the surrounding canonical positions. The mixed positioned → missing → positioned fixture requires an explicit continuity decision; filtering out the missing Record is not permission to add an edge. GPX trkseg boundaries already establish separate canonical parts.

## Minimum supporting value type

M2 should use an immutable `QualityProjection` result with these typed fields, supplied explicitly to assessment rather than hidden in entity extensions:

| Field | Required meaning |
|---|---|
| `canonical_track` | Exact parent identity and revision |
| `algorithm` | Name, version and deterministic parameters |
| `usable_intervals` | Ordered, non-overlapping same-part start/end TrackPositions into that revision |
| `excluded_intervals` | Ordered parent ranges, stable reason codes and diagnostic/source evidence references |
| `gaps` | Adjacent-part endpoint pairs or excluded same-part ranges, provenance, and unresolved constraints |
| `gap_constraints` (optional) | Independently justified admissible spatial bounds, with proof method/version/parameters and referenced evidence; absence means unbounded |

This is a result/value type, not a seventh identity-bearing entity: it owns no Activity or raw evidence and its indices are always those of its parent revision. Persistence, IDs, adapter quotas and reconciliation do not belong in this interface. M2 must define its serialization and implement its verifier alongside the first quality algorithm; none of the six core schemas needs to be redesigned to carry it.

For identical inputs, version and parameters, every decision and interval is deterministic. A verifier must reject out-of-bounds, overlapping or cross-part usable intervals and gaps with unsupported proofs. Every original candidate edge is accounted for as usable or excluded. Zero-distance edges remain auditable observations. Rejected edges create usable-geometry breaks; adjacent retained points must never be joined across a rejection. Neither usable geometry nor TrackPosition is expressed against a compacted observation array.

TargetSegment lineage is regenerated from the original parent interval. A segment cannot span excluded geometry or a continuity break. Maximality is measured within each continuous usable interval; repeated visits remain distinct by parent position. If quality leaves no positive-length usable geometry, assessment is unavailable, never `outside`. Assessment uncertainty references the affected original ranges and quality provenance.

## Relation proof and completeness proof

Derive reliable positive-length inside and outside facts first. Both facts force `partial`, even with unresolved gaps. An unresolved gap cannot erase observed evidence. It can prevent exhaustive reconstruction.

For a gap with a verified admissible bound disjoint from TargetArea, target coverage may remain complete. For a bound entirely covered by TargetArea, relation may remain `inside` while the route through that bound is unreconstructed and coverage is incomplete. Merely observing two endpoints inside a local polygon establishes neither bound. A prose relevance statement or submitted relation is not such a proof. Any physically motivated bound must state its independent assumptions; a speed cap cannot silently be inferred from observed speed.

The existing CoverageUncertainty schema identifies affected range, relevance and provenance. It does **not** encode a mechanically verifiable spatial bound. This is a real limitation of the current fixture interface, not a new domain restriction. General local-area `inside + incomplete` and target-irrelevant-gap `outside + complete` require the supporting result above in M2.

M1 contains a noncircular `inside + incomplete` witness: `audit-inside_incomplete_world`. Its TargetArea covers the entire canonical CRS84 coordinate domain, so an unobserved route cannot leave the target, yet the exact geometry remains unknown. M1's fixture oracle assumes all supplied observation edges are reliable; it never treats arbitrary CanonicalTrack data as already quality-approved production input. It fails closed with `COVERAGE_COMPLETENESS_UNPROVEN` on multi-part complete claims because this interface supplies no gap proof. That is an oracle capability limit. ADR-0007's target-relative completeness remains unchanged; **M2 must not copy that guard as a universal domain rule**.

## M2 implementation acceptance tests

- Reject an interior GPS jump without deleting its observations; preserve exact TrackPosition indices and record why adjacent edges are excluded.
- Reproduce the same result and diagnostic ordering for identical evidence and parameters.
- Never bridge GPX parts, a missing-position run, or excluded geometry; demonstrate this with a mutation test.
- Verify a bounded gap inside a local target yields `inside + incomplete`, and a bound disjoint from the target permits `outside + complete`.
- Reject the same assertions with missing, stale or unsupported bound evidence. Test partial evidence before declarations.
- Keep speed unavailable across missing/non-increasing timestamps or quality breaks while preserving spatial evidence.

These are M2 algorithm acceptance tests, not claims of implemented M1 runtime behavior. The six metric input fixtures and raw sentinel/segmentation fixtures supply the evidence shapes now.

## Checkpoint ownership and current implementation

Under the current ROADMAP, M2B implements the supporting quality values, explicit gaps and verifier; M2C consumes those verified values for target-relative conclusions. The local-target relation/completeness acceptance tests above belong to M2C and require an independently supported local-bound method before such claims are made. They do not authorize M2B to infer a route or a local bound.

See [the M2B implementation record](milestone2b-quality-projection.md) for the exact immutable value structure, whole-edge original-parent ranges, explicit caller quality policy, pinned WGS84 screening distance, unavailable-rule diagnostics and independent verifier. The initial optional proof method is the complete CRS84 coordinate-domain bound only; all gaps remain unreconstructed. M2B is DONE after independent review and merge. [M2C supporting spatial proof](milestone2c-spatial-relation.md) is ACTIVE for independent review; M2D entity extraction/assembly remains NOT STARTED. M2C returns non-assessable without a relation when no usable positive-length geometry exists. The useful local-bound acceptance obligation remains open under the corrected ROADMAP; the implemented domain-only witness does not satisfy it.
