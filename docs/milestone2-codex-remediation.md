# M2 Codex independent audit: F1/F2 remediation and re-exit evidence

**Status: REMEDIATION IN REVIEW. M2 is REOPENED; the original October 8 M2 exit PASS at `7059953c` was superseded by independent audit CHANGES_REQUIRED.** Do not start M3 or re-mark M2 DONE based only on a green PR CI run.

**Audit baseline:** `7059953c0229cde14028b0018dd366c097e7ffd1`. The independent full-repository Codex Remote audit was supplied by the project owner, with 271 original tests passing but 2 of 17 separately constructed adversarial attacks failing. The original audit's `/workspace/audit-artifacts` files were produced in the auditor's workspace and are not claimed to exist in this repository. The review evidence is transcribed here; new committed independent counterexamples are reproducible within repository CI.

## Classification and scope

| Finding | Original outcome | Fix / accepted limitation |
|---|---|---|
| F1 (P1) | Independently valid quality claims could arbitrarily split one admitted continuous interval into two; M2D then returned two purported maximal TargetSegments | **Required repair:** M2B independent verifier rejects adjacent end-to-start admitted intervals in the same source part, under `USABLE_INTERVAL_NOT_MAXIMAL`. True source part changes and independently rejected whole edges still separate intervals. Producer already emits maximal runs. `QualityAlgorithm.version` advances `0.1.0 → 0.1.1` to mark strengthened admissibility contract. |
| F2 (P1) | M2B correctly recorded `SPEED_NUMERICALLY_INDETERMINATE`, but M2F displayed mathematically valid extreme velocity as though speed screened and passed | **Required repair:** verified M2B edge diagnostics are indexed by original part/edge; exported metric fragments and stationary records carry both `speed_screen_result` and `speed_screen_reason`. `passed` occurs only when an explicit enabled cap has no diagnostic for that admitted edge. `indeterminate`, `unavailable` and `not_screened` remain distinguishable. Actual map JS renders colored numeric **solid** only for `passed`; **short-dashed** for indeterminate, **long-dashed** for no screen, and **neutral gray dashed** for invalid metrics. Missing/legacy status is never silently treated as passed. `temporal-overlay.version` advances `0.1.0 → 0.1.1`. |
| F3 (P2) | FIT timer stop/start and long sparse sampling gaps may not become inferred spatial discontinuities | **Documented current limitation**, not an implicit new GPS quality policy. FIT parser relies on positioned Record order and explicit missing records; timer events and long time gaps are NOT evidence of a missing path under this v0.1 continuity policy. |
| F4 (P2) | Clipped elapsed time is proportionally **allocated**, not observed; parent-edge WGS84 screened speed may differ from clipped fragment speed | **Required semantic disclosure:** each metric has `duration_basis = observed_parent_endpoints | proportional_parent_edge_allocation`, with metadata `clipped_duration_semantics` and `parent_speed_cap_scope`. Parents have WGS84 shortest geodesic implied screening; target clipping is planar CRS84. A `passed` parent cap does **not** assert the derived subinterval speed is below the parent cap. Runtime legend must disclose the two meanings. |
| F5 (P2) | Fixture JSON and runtime JSON reject different underflow/duplicate key inputs | Track as separate engineering consistency work; no known committed fixture is incorrect, but don't call fixture-level JSON equivalence fully proved. |
| F6 (P2) | Worst-case fragmentation exposes quadratic extraction and verifier scans; ingest reads entire raw file | M3 batch readiness must add indexed/single-pass extraction, workload budgets and benchmark coverage before claiming large historical throughput. |
| F7 (P2, M3 responsibility) | Caller can supply mutually forged CanonicalTrack and hash that passes downstream consistency tests | M3 must bind immutable raw blob and source revision, complete IngestionResult and diagnostics, parser version and derived snapshots on reload, reject same identity/revision with different content, and defend replacement/mixed-snapshot attacks. Current in-memory verified snapshot is a caller trust boundary, not a cryptographic proof of original raw GPS bytes. |

## Reproduction and proof of fix

- `tests/test_m2_codex_p1_regression.py` directly builds a *different* `QualityProjection` with identical admitted edges, parent evidence, diagnostics and policy but adjacent `[(0,0)→(0,1)], [(0,1)→(0,2)]` intervals. It must be rejected by the independent quality verifier *before M2C* and by the M2C/verifier admission path. True exclusion and source-part discontinuities remain valid.
- Same test constructs a physical delta smaller than M2B's numerical guard: `(0,0) → (10⁻¹²°,0)` in `10⁻¹² s`, with explicit cap `1 m/s`. M2B retains `SPEED_NUMERICALLY_INDETERMINATE`; downstream keeps finite derived velocity **and** exact screening uncertainty, rather than claiming screened pass.
- Mandatory Node execution of **actual generated map JS** in `tests/m2_codex_screening_dom.cjs` validates four runtime states: numeric indeterminate, screened pass, no speed screening, and invalid time. It verifies SVG dash arrays, detail provenance, cap scope, time allocation legend, and pace-mode consistency.
- Independent high-latitude clipped parent example: original `(-89,80)→(89,80)`, 86,400 s, cap 30 m/s. Parent screening is `passed` while computed clipped velocity may exceed 30 m/s: the two quantities have different geometry/time semantics. The test asserts this **non-equivalence is explicit** without quietly changing M2B policies.
- `tests/m2_exit_wheel_smoke.py` independently repeats F1 and F2 attacks using **noneditable installed wheel outside checkout**, not merely checked-in Python source.
- Existing frozen M0/M1 schemas, M2A ingestion, M2C proof logic, M2D entity authority, and M2E original map geometry remain unchanged. The updated support/result semantics are explicitly versioned. The old PASS reports remain as historical records, not silently erased.

## Re-exit requirements

1. Exact-head CI passes all Python, schema/semantic/source, Node runtime, contract mutation, source raw integrity and both isolated-wheel suites.
2. Explicit F1/F2 reproducible attacks PASS **on the installed package**, not only on source.
3. An independent Codex code review of the final remediation PR verifies the final diff and probes the substantive edge cases. A GitHub bot status of `Running` or thumbs-up on an unrelated documentation PR is NOT review completion.
4. Close remaining P1 objections and verify F3/F4 visible/documented limits. Do not expand this repair into implicit FIT timer gap inference, unsound speed capping or a new missing-path model.
5. **Only then** reopen the separate M2 comprehensive exit review, record its exact revision/CI/reviewer evidence, change ROADMAP back to DONE, and proceed to M3 planning. This remediation PR should leave M2 status **ACTIVE — REOPENED** until that decision.

A green CI alone cannot supersede the independent external findings. No v0.1.0 tag, artifact publication, or M3 implementation is authorized by this remediation.
