# Real-World Evidence Cases

This document records anonymized observations from representative real activity data used to resolve the evidence questions in `docs/evidence-plan.md`.

It is intentionally **not** a raw-track archive.

## Privacy rule

Do not commit private FIT/GPX files or unnecessary precise location/time data merely to support the design review.

Public records should contain only the minimum structural facts needed to justify a domain-model decision.

## Observation rule

Separate facts from interpretation.

- **Observed facts** describe only what the source contains or what can be deterministically measured.
- **Interpretation** compares candidate models only after the observations are recorded.

No domain-model decision should be changed while an observation card is still being filled.

## Current status

No real-world evidence cases have been recorded yet.

The first evidence pass should prioritize:

1. EP-02 — continuity / multipart behavior;
2. EP-03 — GPS outliers and canonical observation semantics;
3. EP-04 — FIT versus GPX representation;
4. EP-05 — TargetSegment lineage;
5. EP-01 — minimum CanonicalTrack.

## Case template

### RC-XX — Short descriptive title

**Why selected**

Describe which unresolved design question this case is intended to illuminate.

**Source format(s)**

- FIT / GPX / other
- anonymized source reference only

**Observed structure**

- point count:
- position record count:
- timestamp continuity:
- distance continuity:
- pause/resume events:
- source segment/part breaks:
- largest relevant time gap:
- largest relevant spatial jump:
- other relevant source facts:

**Observed facts**

- fact 1
- fact 2
- fact 3

Do not put model interpretation in this section.

**Affected evidence questions**

- EP-XX
- EP-YY

**Candidate comparison**

Candidate A:

- explains:
- fails to explain:

Candidate B:

- explains:
- fails to explain:

Candidate C, if relevant:

- explains:
- fails to explain:

**Contradictions / limitations**

Record anything that prevents the case from cleanly supporting one candidate.

**Evidence strength**

- weak / moderate / strong

**Decision impact**

- supports
- contradicts
- inconclusive

**Public-data note**

State whether any coordinates, timestamps, identifiers, screenshots, or file excerpts were omitted or transformed for privacy.

---

## Case index

| Case | Evidence question(s) | Source | Result | Status |
|---|---|---|---|---|
| — | — | — | — | awaiting evidence |
