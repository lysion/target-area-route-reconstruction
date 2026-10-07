# Milestone 1 Remediation Record

**Opened:** 2026-10-07  
**Base commit:** `141dc092f5a3c7845066156cafd26b3879e99137`  
**Status:** ACTIVE; Milestone 2 BLOCKED

The independent adversarial audit found that the previous Milestone 1 green gate was insufficient to prove the frozen v0.1 contract. It demonstrated acceptance of omitted or reordered repeated traversals, nonmaximal known segments, and a wrong relation under incomplete coverage. It also demonstrated a valid diagonal clipping result rejected because of floating-point noise, negative fixtures passing for unrelated reasons, linked semantic objects bypassing schema validation, and raw FIT/GPX baseline weaknesses.

The historical PASS in `milestone1-exit-review.md` remains a record of what was checked at the time. It is no longer the current readiness decision. None of these findings requires a change to the six frozen core entities or their domain semantics.

Re-exit requires reason-specific negative expectations, Layer A validation of every linked component, ordered parent-track interval checks for TargetSegment lineage and exhaustive coverage, evidence-first relation checks, a consistent numerical policy, mutation-sensitive continuity tests, strict JSON and common-schema conformance, meaningful EC-01..EC-29 contract mapping, independent raw-source conformance checks, and a fresh exit review. Production Milestone 2 parsing and spatial implementation remain out of scope during this remediation.
