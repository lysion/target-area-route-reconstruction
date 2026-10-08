# ADR-0011 — Explicit open-ended CoverageUncertainty ranges

**Status:** Proposed — NOT accepted or implemented

**Date:** 2026-10-08

**Checkpoint:** M2D contract blocker

**Evidence:** `tests/test_m2d_contract.py`, `tests/m2d-contract/`

## Context and confirmed failure

Accepted M2A/M2B/M2C preserve leading and trailing source gaps without inventing a positioned endpoint. With positive outside observed geometry, a local target and no gap constraint, both cases produce a verified assessable `unknown + incomplete` proof. The gap has respectively `start=None` or `end=None`.

The frozen SpatialAssessment schema requires every CoverageUncertainty to contain `affected_track_range`, referring to `common.schema.json#/$defs/trackRange`. That value requires two non-null TrackPositions on the parent. Its definition is an inclusive ordered interval, not a source-boundary anchor. `docs/schema-conventions.md` sections 5, 12 and 19 forbid missing-value sentinels, give TrackPosition concrete parent-location semantics, and prohibit hiding necessary core semantics in extensions.

Faithfully copying either accepted gap into the assessment fails Layer A at:

- `/coverage_uncertainties/0/affected_track_range/start`, keyword `type` (leading);
- `/coverage_uncertainties/0/affected_track_range/end`, keyword `type` (trailing).

Omitting the absent endpoint fails `required`. A real two-ended gap passes the same assessment probe, demonstrating that the failure is specifically the missing endpoint, not malformed unrelated fields. FIT missing-position runs reproduce the same issue as GPX empty leading/trailing parts.

This is a representation gap between accepted supporting evidence and the frozen entity schema. ADR-0004 assessability and ADR-0007 uncertainty requirements remain sound. The problem does not authorize changing relation, completeness, source evidence or segment lineage.

## Existing-contract alternatives examined

1. **Duplicate the known endpoint (`start == end`).** This can pass current schema and M1 local semantic checks. It represents a point interval on observed evidence, not the open prefix/suffix in the M2C gap. No accepted ADR, schema convention or fixture assigns an open-ended meaning to that point interval. Treating it as an anchor would need a new explicit representation convention; it is not an existing authorized mapping.
2. **Use the whole observed track.** This supplies real endpoints but describes a different interval; it does not represent the unknown leading/trailing extent. Attaching the original null endpoint in prose/parameters does not change the core range's defined meaning.
3. **Store the gap in provenance or extensions only.** Provenance may retain the exact source cause/evidence references, but it does not override required range semantics. An extension cannot supply missing core-required meaning.
4. **Use a negative/out-of-range index, terminal fraction, or virtual CanonicalTrack part.** These violate TrackPosition bounds or mutate parent evidence. The test demonstrates that an apparently schema-valid sentinel fails parent validation.
5. **Drop the uncertainty, mark complete, or make the track non-assessable.** These contradict the already verified M2C facts and ADR-0004/0007.
6. **Keep M2D permanently unable to assemble these legal assessable proofs.** Explicit failure is correct while blocked, but cannot satisfy M2D acceptance for the committed leading/trailing cases.

The conclusion is not that no JSON object can pass the current schema. Point-anchor substitutions can pass it. The missing contract is a **lossless, explicitly defined representation of the open affected extent**. Green schema validation alone cannot authorize that reinterpretation.

## Proposed amendment (requires independent acceptance)

Introduce a dedicated shared supporting value, tentatively `coverageUncertaintyRange`, used only by CoverageUncertainty. Preserve existing `trackRange` and TrackPosition semantics for closed observed intervals and TargetSegment lineage.

The proposed range has required `start` and `end` fields and exactly three forms:

| Form | start | end | Meaning |
|---|---|---|---|
| bounded | TrackPosition | TrackPosition | Existing ordered affected extent |
| leading | null | TrackPosition | Unpositioned source prefix before the known parent neighbor |
| trailing | TrackPosition | null | Unpositioned source suffix after the known parent neighbor |

Both-null is invalid for this assessable-entity interface. Null explicitly means **no positioned source neighbor is available**, not negative/positive infinity, an infinite duration, a route coordinate, a TrackPosition, or proof of motion. This is evidence extent, never geometry.

The corresponding proposed schema amendment would change only CoverageUncertainty's range reference to this dedicated definition, with a closed object and a mutually exclusive bounded/leading/trailing union. This PR deliberately contains no such schema change.

Required semantic verification after approval:

- every present endpoint is a valid original-parent TrackPosition;
- bounded endpoints are ordered and match the exact verified unresolved M2C gap;
- leading/trailing absence and present neighbor exactly match the M2C gap and M2A source diagnostics;
- no arbitrary interior null endpoint or both-null range is accepted;
- every unresolved target-relevant gap appears exactly once, and irrelevant/resolved gaps appear zero times;
- source versus quality causes and exact evidence/algorithm provenance survive;
- absent endpoints authorize no extra TargetSegment, interpolation or boundary-crossing geometry.

This preserves six entity identities/ownership and all frozen evidence/spatial invariants. It changes public schema nullability/instance meaning, so schema change-control is still required even though the domain already allows the source state.

## Compatibility and acceptance gate

Do not widen `schema_version=0.1.0` silently. Before implementation, review an explicit schema-version/compatibility decision under `docs/schema-conventions.md` section 3: select a new contract version for the amended representation, retain validation of historical 0.1.0 instances, and specify version dispatch for entities and packaged schemas. No version number is adopted by this Proposed ADR.

Acceptance must update ROADMAP and the schema conventions, add reason-specific schema/semantic fixtures for all three forms, update schema/package copies and their conformance checks, and preserve all existing closed-range history. Only then may M2D resume entity assembly against the accepted contract. The blocker tests will then need a deliberate legacy/new-version split, not deletion or weakening.

No implementation of this proposal, segment extraction, missing-route reconstruction, M2E, or M7 is authorized by this document. M2D remains blocked until an independently accepted amendment or equally explicit, reviewed alternative mapping resolves the gap.
