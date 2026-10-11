# M2 final exit audit — numerical authority and snapshot codecs

**Decision: PASS_WITH_LIMITATIONS. M2 exit criteria are satisfied for the bounded local FIT/GPX pipeline. M3 remains NOT STARTED; no release/tag is created.**

Audit date: 2026-10-11 UTC. Exact audited production commit:
`82e62b5e033ae4a0dfaff7828103fe989c468ca6`, PR #21.
This report supersedes previous M2 exit decisions as current authority; their
failed baselines and historical results remain preserved.

## Method and independence

A fresh detached clone, dependency environments and noneditable wheel were
created outside the repair checkout. All M2A–M2F authority/data paths were
reviewed against M0/M1, ROADMAP, the numerical policy and support boundaries.
The reviewer is the same assistant/session that repaired the code, not a
separate human or newly spawned agent. Independence of correctness evidence
comes from new inputs and independent rational/declaration oracles, not that
identity. Green CI and prior reports were not used as expected answers.

The new geometry oracle uses exact `Fraction(float)` operands, winding-number
point membership and segment intersection; it imports neither production
geometry helper nor GEOS as its reference. Class declarations and unchanged
attribute values, rather than production validation, define the namespace
mutation oracle. Real FIT/GPX bytes and public API calls exercise the complete
pipeline. Source and installed-wheel results agree.

## Closed failures

| Failure | Final evidence |
|---|---|
| F1 nonmaximal quality split | Illegal adjoining splits rejected; real parts/exclusions remain separate; source/wheel regressions retained |
| F2 lost parent screening uncertainty | Original-edge indeterminate/unavailable/not-screened status and reason survive metrics and Node map styling |
| R2-01 tiny GEOS intersection A/B | Exact positive reference retained; unsupported clipping fails explicitly, never false outside/complete; wholly interior subnormal edges survive |
| R2-02 zero / TrackPosition subclasses | Canonical zero constructors and exact typed admission retained |
| R3 sloped-boundary P1 | Exact local quarter-length/absolute/ULP bounds check fraction and regenerated coordinate; Polygon/hole/MultiPolygon witnesses fail closed |
| Diagnostic code/field and nested Gap P2 | Original primitive/subclass/index alias attacks rejected before accepted downstream identity |
| Native dataclass codec P2 | Instance fields, metadata and methods cannot choose the serialized/hash field set; original 14 variants rejected; t1/t2 cannot share an assessment revision with different payload |
| Wrong-root evidence_digest P3 | Stable QUALITY_EVIDENCE_INVALID before hashing, rather than AttributeError |

## Codec correction

Exact model type alone was insufficient: an instance could shadow
`__dataclass_fields__`, `to_dict` or `to_json`, while retaining every declared
attribute and dataclass equality. Field validation now uses the complete class
field set. Instance namespaces must be native dictionaries with native string
keys drawn only from those fields. Required missing fields fail closed.
Quality algorithm and final snapshot admission precede codec invocation.
Caller policies/references receive the same admission; targets must be native
finite JSON before copying/conversion. No caller-defined copy/number behavior
can substitute for that input contract.

This corrects unsupported admission without changing legal snapshot semantics.
Quality/spatial algorithm versions remain 0.1.3; the legal motivating baseline's
JSON, evidence/quality digest, proof and M2D payload/identities are unchanged.
The frozen schemas and six-entity domain model are unchanged.

## Executed evidence

| Gate | Result |
|---|---|
| Full Python discovery, source / fresh installed wheel | **317/317 in each environment**, including mutation and actual Node wrappers |
| Schema / semantic / edge / original source | **260/260**, **56/56**, **29/29**, **12/12**; two equivalence groups |
| Geometry matrix / environment | **2,580 cases**: 1,457 produced, 1,092 numerical failures, 31 invalid topology controls; zero wrong certified results |
| Existing independent type matrix | **2,422 mutations**, 23 models; two legal field=None controls, 2,420 invalid forms rejected |
| Original native-codec witnesses | **14/14 rejected**, no identity drift or revision collision |
| New namespace / codec matrix | **240 cases**, 22 models; all rejected without calling shadow callbacks |
| New identity / UTC / gap controls | **18 cases passed**: policy numeric normalization, bundle canonical identity, ordinal/subclass rejection, exact offset/fractional time, world-domain holes |
| Installed-wheel integration | Both original smokes plus standalone sloped-boundary and codec regression files passed |
| Exact code-head CI | [38182432308](https://github.com/lysion/target-area-route-reconstruction/actions/runs/38182432308), SUCCESS for 82e62b5 |

Sixteen paired source/wheel JSON groups are identical. Both original P2 minimal
witness properties are false after repair; malformed M2A metadata causes zero
SHA-256 calls. Stable serialization of a malformed debug object alone is never
admission. Expected invalid/numerical outcomes are not mislabeled as certified
geometry. This finite suite is not a proof for every conceivable polygon/input.

External reproducible delivery: `/workspace/m2-codec-exit-audit`, including
scripts, inputs, wheel, logs, environment, exact commit checks and Chinese
report. The source snapshot is read-only; the following repository changes are
acceptance documentation only. Final PR-head and merged-main CI/merge records
are to be retained in that delivery; production bytes must match the audited
commit before and after merge.

## Accepted limits and future gates

- F3: sparse samples/FIT timer events do not prove real-world route continuity.
- F4: clipped time is proportional allocation, not observed crossing time;
  derived metrics are the declared numerical model, not motion-truth evidence.
- F5: fixture/runtime strict JSON byte-admission differences remain an explicit
  M3 pre-persistence gate; no byte-equivalence guarantee is added here.
- F6: fragmented processing/resource budgets remain an M3 batch-readiness gate;
  no large-history performance guarantee is made.
- F7: trusted in-memory M2A hand-off is not cryptographic raw-evidence custody;
  M3 must implement immutable receipts, complete derivation graphs and verified
  restart/reload, including co-forged/mixed-snapshot rejection.
- Useful local gap bounds, periodic/geodesic clipping, vendor FIT exhaustiveness,
  multi-Activity inference and missing-route centerlines are unsupported.
- No real-browser/cross-OS/vendor-complete matrix or fixed-hardware scale budget
  was executed. Linux/Python 3.12 independent runs and Python 3.11 CI are evidence,
  not a compatibility guarantee.

These limits do not permit incorrect certified geometry or incomplete snapshot
hashes. Those demonstrated M2 blockers are closed in the audited scope.
M2 is DONE with these limits; any new supported behavior needs its own contract
and tests. M3 can be considered next but has not been started by this task.
