# Milestone 2 — second Codex full-repository audit: fresh post-R2 re-exit review

**Decision: PENDING — do not promote M2 to DONE until all exact-merged-main gates below have been proven.**

**Audit and review date:** 2026-10-10 (Asia/Tokyo). Times on GitHub are UTC.

## Authority and review scope

- Baseline independently audited in the second Codex Remote full-repository audit: `d86414f25b15c40da20bb354a69a7e609b4f5e25`, outcome **CHANGES_REQUIRED** despite the previous green M2 exit. The original `PASS_WITH_LIMITATIONS` at [milestone2-codex-reexit-review.md](milestone2-codex-reexit-review.md) is historical, not current release authority.
- Corrective PR [#21](https://github.com/lysion/target-area-route-reconstruction/pull/21) is scoped to R2-01 spatial numerical classification P1, R2-02 equivalent zero/parent identity P2, and R2-03 documentation P3. Independent GitHub Codex diff reviews also found diagnostic-endpoint, upstream M2A source-position and nested M2C gap-relevance P2 representation bypasses. M0/M1 schema shapes and prior F1/F2 regressions must remain unchanged.
- **The second independent full-repository audit, the corrective PR Codex diff review, project CI, and this post-merge release decision are separate forms of evidence.** No green test suite substitutes for a known failing independent counterexample.

## R2 repairs and independently falsifiable tests

| Finding | Original counterexample / violated boundary | Required corrective evidence |
| --- | --- | --- |
| R2-01, P1 | A valid extreme-but-finite real GPX segment intersected a thin target region, yet GEOS yielded a false `outside + complete` or a fragment exceeding a 5e-324-wide region; producer and the old GEOS-backed verification oracle both agreed on the wrong answer. | `_spatial_geometry.py` conservatively fails closed on unresolved tiny-edge boundary segment envelopes and numerical warnings, without deleting genuine positive-length fully inside edges. Independent `Fraction(float)` rectangle/Liang–Barsky witness, real decimal GPX ingestion, forged-proof verifier refusal, and installed-wheel reproduction are required. |
| R2-02, P2 | `TrackPosition.fraction_to_next` values `0`, `0.0`, and `-0.0` represented the same point but could create different snapshots and spatial identities. | Constructor canonicalizes equivalent zeros to positive float zero; verifier rejects bypassed constructors, including quality diagnostics, M2A observation mappings, ingestion diagnostics and nested M2C gap-relevance endpoints, before digest or proof admission. The regenerated exact identity must be invariant for typed valid input. |
| Additional Codex PR-review P2 | A forged `EdgeDiagnostic.interval` endpoint still passed the old dataclass-equality diagnostic comparison while changing serialized quality identity. | Validate both diagnostic endpoints independently, test integer zero and negative zero, require `TRACK_POSITION_INVALID` and downstream M2C refusal, repeat attacks in noneditable installed wheel. |
| R2-03, P3 | Stage documentation described old M2 state. | Document second audit reopening, preserve historical review records, and publish a **separate post-R2 re-exit** rather than relabeling a PR CI run as approval. |
| Prior F1/F2 | Nonmaximal quality partition and lost speed-screening uncertainty. | Retain original regression witnesses and installed-wheel attacks; no regression is accepted. |

## Exact-head and merged-main verification ledger

- Corrective PR #21 last examined head: `26721118d68179ab5d4c83dc3fbf1adcd990db6d`.
- Exact-head workflow [38010635293](https://github.com/lysion/target-area-route-reconstruction/actions/runs/38010635293): **SUCCESS**, 287 Python tests, source/schema/semantic/edge-case/mutation gates, Node map checks, and independently installed wheel. Log explicitly reports R2-01 exact Fraction GPX numerics, R2-02 diagnostic bypass, and prior F1/F2 attacks PASS.
- **Outstanding prior to an acceptance decision:** complete independent Codex review of *this exact repaired source diff* with all actionable findings closed; merge with expected head; successful independent CI against the exact merged-main SHA, not only the PR checkout; final audit of current README, ROADMAP and source-support disclosures.
- M2 acceptance cannot be inferred from test count or a review that applies only to an earlier PR head.

## M2 release boundary, if final gates pass

Acceptance is strictly for the **deterministic local, one-Activity-at-a-time FIT/GPX → CanonicalTrack → quality → spatial proof → TargetSegment/SpatialAssessment → GeoJSON/offline map → optional speed/pace display** pipeline. A trusted caller-supplied M2A snapshot remains a declared premise of downstream verification. No source acquisition adapters, persistence/restart, multi-activity reconstruction, route network, agent Skill, PyPI distribution, or v0.1.0 public tag is included.

Maintain M2 limitations: F3 FIT timer/sparse-sampling cannot certify true traversed routes; F4 clipped fragment time is a proportional allocation and parent WGS84 speed cap is not local observed motion; F5 strict JSON loader parity and F6 bounded scalability/benchmarks remain M3 obligations; F7 immutable external source/whole-graph trust anchor is not implemented until M3. Current CI is Ubuntu/Python 3.11 and Node minimal-DOM plus isolated wheel, not a full platform matrix. Never relabel numerical failure, missing track, or gap as `outside + complete`.

## Final exit decision

**PENDING.** Complete the outstanding evidence ledger above, record the exact PR-review outcome, merge SHA, merged-main CI run and final known limitations, then change this section and the status of M2 in README/ROADMAP and support documentation in a distinct reviewed closeout PR. M3 remains NOT STARTED until this decision is accepted.
