# M2 R3 D-01 — source diagnostic and declared-type admission repair

> Historical remediation record. Current acceptance is the [final numerical/codec exit audit](milestone2-final-exit-audit.md), PASS_WITH_LIMITATIONS. The pending/REOPENED statements below describe the repair-time state and are retained as history. M3 remains NOT STARTED.


**M2 remains REOPENED. This is a repair record, not an independent exit acceptance, merge approval, release or M3 start. A new full-repository audit must review the final repair SHA.**

## Failed baseline and retained upstream repair

The independent R3 audit of `7d50b7ca430e05f9fa46848ce504441d372e1c15` returned CHANGES_REQUIRED. A real GPX timestamp without a timezone produces `TIMESTAMP_TIMEZONE_MISSING`. Replacing only its `Diagnostic.field` or `code` with `False`, `0`, `0.0` or `-0.0` was accepted by the M2A hand-off, quality producer/verifier and spatial/entity pipeline. Unchanged raw hash, CanonicalTrack revision and geometry then acquired different evidence/quality digests, proof JSON, assessment revisions and TargetSegment identities.

The producer and verifier both relied on `_quality_evidence.evidence_issues`, which checked exact Diagnostic classes, source indices and endpoint lineage but omitted the primitive `code: str` and `field: str | None` declarations. M2B/M2C's closed declaration checker did not include the M2A evidence that it fingerprinted. Independent replay reproduced the original failure before changes.

Upstream `a28e834ef27c3dd6a13ce0ce323206d98ce12eab` already adds exact primitive checks with `SOURCE_DIAGNOSTIC_TYPE_INVALID` and real-GPX/source/wheel witnesses. This repair retains that commit and closes the rest of the source shape admission boundary.

## Admission boundary

- Extend the existing declaration-based checker to a closed M2A registry: IngestionResult, Diagnostic, ObservationSource, SourceLocation and TrackPosition. Dataclass extensions and incomplete instances do not become evidence via `asdict()`.
- Require the declared tuple containers, exact primitive/index types and exact dictionary key/value types. `dict[str, Any]` means native finite JSON: only None, native string/integer/bool/finite float, lists and string-keyed dictionaries. It does not permit arbitrary objects, dataclasses hidden inside a canonical entity, container subclasses or tuples masquerading as JSON arrays.
- Retain the specific source mapping, diagnostic source, diagnostic primitive and endpoint error codes. Structural admission precedes parent/evidence hashing. For structurally valid parent edits, parent revision mismatch keeps precedence over ensuing geometric/lineage errors.
- Guard `evidence_digest` itself, so a direct helper call cannot give a malformed snapshot a fingerprint. Unsupported/incomplete/cyclic shapes fail closed. This does not authenticate the raw source; semantic and provenance checks still run independently of structural admission.
- Preserve authentic parser diagnostics and their sources. `field=None` remains legal; malformed values are rejected, not normalized to None or a string.

This fixes acceptance of inputs outside the already declared source contract. It does not change valid parsing, spatial geometry, temporal models, canonical serialization or algorithm parameter values; supported QualityAlgorithm stays 0.1.3 and SpatialAlgorithm stays 0.1.2. Unmodified valid evidence must retain identical output identities. No frozen entity schema is changed.

## Executable evidence

`tests/test_m2a_evidence_types.py` uses new real GPX bytes and manual declared-type expectations, not the production matcher as an oracle. Eight tests cover primitive aliases/nonfinite values, illegal or extended dataclass instances, string/container subclasses, equal-JSON list/tuple substitutions, remaining hash-bearing source fields, missing fields/cycles and positive string/None controls. Every negative witness verifies all public stages, including M2D verification and M2F export, and spies on the hash boundary to establish rejection before any source hash.

`tests/test_m2_r2_numerical_gate.py` retains upstream's authentic warning and thirteen invalid primitive spellings. `tests/m2_exit_wheel_smoke.py` retains all original F1/F2/R2/R3 witnesses, repeats diagnostic primitive attacks on the installed noneditable wheel, and now tests the closed source shape boundary before hashing.

Required verification for a repair completion: full Python/mutation suite; schema, semantic, edge-case and raw baseline gates; explicit Node map interactions; rebuilt isolated noneditable wheel with the new tests and both smoke suites; original independent D-01 reproduction returning rejection; valid FIT/GPX cross-stage output comparison; and successful GitHub CI for the pushed final SHA. Results and final GitHub SHA belong in the task's external repair report, not an inferred M2 exit claim.

## Remaining boundaries

This repair is not a substitute for the next independent audit. Diagnostic code vocabulary/event multiplicity is not redefined: distinct real missing/empty events remain separately referenced, and duplicate-event canonicalization needs a separate contract if desired. Fully co-forged snapshots/raw receipts and trusted persisted reload remain subject to M3's immutable evidence-custody gate. FIT sampling/timer, clipped-time allocation, resource budgets and browser/vendor coverage retain their disclosed limits. No source uncertainty is converted into observed route geometry.
