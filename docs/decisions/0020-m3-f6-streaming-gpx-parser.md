# ADR-0020 — Stream GPX parsing under the F6 source budget

Status: implementation decision pending PR review. Date: 2026-10-15.

## Context

The initial F6 limits bounded raw GPX bytes, point count, and continuity-part count, but `parse_gpx` first built a complete lxml document tree and only then counted observations. A byte cap bounds the input but still permits a second, substantially larger retained tree. This undermines the intended admission behavior for a source with many small XML nodes.

## Decision

GPX ingestion performs a streaming well-formedness preflight so malformed XML keeps its existing `MALFORMED_SOURCE` result and DTDs keep `UNSUPPORTED_GPX_DTD`. It then runs schema-validating `iterparse`, retains only the raw location/coordinate/elevation/time fields needed for the capped canonical result, and clears completed point, segment, track, and top-level nodes. Domain normalization happens after schema validation, preserving schema-error precedence over invalid coordinate/time interpretation. Existing part and observation limits remain fail-closed; no input is truncated and no continuity is inferred.

This reduces the XML tree to the active parser frontier and current subtree, while the retained canonical records are bounded by the existing observation/part limits. It is not a process RSS or CPU-time guard: a large individual subtree remains bounded by source bytes, and the well-formedness pass scans the complete source before point admission. Wall-time/RSS enforcement and workload scaling acceptance remain outstanding F6 requirements.

## Consequences

- GPX source parsing no longer materializes and retains a complete source document tree.
- Raw source bytes, normalized observations, source order, track/segment/point indexes, empty segments, timestamps, diagnostics, and all existing identities remain unchanged for admitted input.
- Parsing uses two streaming passes to preserve historical XML and XSD error behavior; this is an intentional CPU tradeoff for bounded XML-tree retention.
- Tests must cover real GPX fixtures, malformed and schema-invalid inputs, DTD rejection, exact source lineage, configured observation/part boundaries, and proof that source bytes are not passed to whole-tree `fromstring`.

This ADR is a partial F6 implementation and does not complete M3 or permit M4.
