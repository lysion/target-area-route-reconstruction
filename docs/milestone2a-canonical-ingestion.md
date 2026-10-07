# M2A — deterministic canonical ingestion

**Date:** 2026-10-07

**Implementation hand-off:** M2A IMPLEMENTATION READY FOR INDEPENDENT REVIEW. This is not independent acceptance or a declaration that M2 is done. M2 remains ACTIVE; M2B quality projection is next.

## Reviewed M1 baseline

PR #1 was OPEN, non-draft and MERGEABLE with base `main`, head `codex/m1-audit-remediation`, and exact reviewed SHA `7f530c9234805b00ccddd88a39155341eb75e9bf`. Its check and workflow `37573883845` were successful. The worktree was clean and remote main remained at the audited `141dc092f5a3c7845066156cafd26b3879e99137`.

PR #1 was merged with a normal merge commit, preserving its 12 commits and branch. Resulting merge/main HEAD: `6b13c5333673fa41116cdfc50df8302cbe1eae00`. M2A branch `codex/m2a-canonical-ingestion` starts from that commit. Main was verified clean and contains the reviewed M1 SHA.

## Objective and ownership

M2A answers which positioned observations are present in a source, in original order and source continuity structure. It ends at CanonicalTrack and source/normalization diagnostics. It does not decide spatial trustworthiness.

There was no production package. The single production architecture is `src/target_area_route_reconstruction/`:

| Module | Ownership |
|---|---|
| `ingestion.py` | Public `ingest_bytes` / `ingest_file`, read-only acquisition of local bytes, hash verification and stable failure results |
| `fit.py` | FIT FileId/Record semantics through fitdecode; coordinate units, supported recorded telemetry and invalid sentinels |
| `gpx.py` | Offline GPX 1.1 validation and original track/segment/point traversal |
| `normalization.py` | Shared continuity-preserving canonical assembly, parent/source mapping, deterministic identity/revision and diagnostic neighbors |
| `models.py` | Supporting parser/result/diagnostic values; no new identity-bearing entity |
| `_values.py` | Finite numeric values and explicit UTC serialization |
| `spec/gpx-1.1.xsd` | Packaged local official GPX baseline, with whitespace-only normalization of the committed M1 XSD |

Runtime dependencies are pinned `fitdecode==0.11.0` and `lxml==6.1.3` in `pyproject.toml`, moved from development-only ownership because production uses them. `requirements-dev.txt` installs this package with `-e .` plus the existing schema/spatial testing dependencies. No production FIT decoder was copied from the fixture tooling. No production code imports `scripts/` or Shapely.

The packaged XSD is checked against the M1 copy after documented tab/line-ending/trailing-whitespace normalization, and against all committed XML-well-formed GPX valid/invalid cases. Ingestion never retrieves schemas or source data over a network. The wheel includes the schema, independent of checkout location.

## Public entry point

```python
from target_area_route_reconstruction import ingest_file

result = ingest_file(
    "activity.fit",
    source_kind="fit",
    track_source={"id": "source-123", "revision_id": "source-123-r1"},
    expected_sha256="<the TrackSource content_hash digest, when recorded>",
)
```

The caller supplies the exact existing TrackSource revision; Activity and TrackSource ownership/identity are not inferred. `expected_sha256` is optional and should be supplied from existing TrackSource content provenance when available. It must be exactly 64 lowercase hex characters and match the bytes read. No Activity metadata or identity is inferred from filename, time, geometry or similarity.

`ingest_bytes` accepts immutable bytes. `ingest_file` reads once without writing. Both return `IngestionResult`, with:

- `outcome`: `success`, `no_positioned_observations`, or `failure`;
- `content_hash`: the existing `{algorithm: sha256, digest: ...}` value shape, including on parse failure; absent only when reading the file fails;
- `canonical_track`: the frozen entity JSON shape or absent;
- ordered stable `diagnostics`;
- `observation_sources`: one original source location for each canonical observation, keyed by its original normalized TrackPosition.

`to_dict()` returns a detached JSON snapshot; `to_json()` sorts object keys and disallows non-finite numbers. Returned entity dictionaries are consumer-owned snapshots; persistence/immutability enforcement remains M3. The input bytes and caller's source reference are never mutated.

CanonicalTrack `id` hashes the exact TrackSource reference; revision hashes that reference, raw content hash, ordered parts and normalizer name/version with canonical JSON separators. Identical input/ref/version yields identical JSON and diagnostics. Changing source revision changes provenance and derived identity/revision, without reconciling Activities. Behavior changes must bump normalizer version. No path, current clock or randomness participates.

## Continuity and observations

GPX `trkseg` boundaries and track boundaries always create separate canonical parts. Source track/segment/point indices remain in `SourceLocation`; original traversal order is never sorted. Empty source parts cannot become schema-invalid empty canonical parts: they are diagnosed, their source indices retained, and surrounding nonempty parts remain separate.

Within a FIT stream, a Record missing either valid position coordinate does not become an observation. Its missing/sentinel reason is retained, and the next positioned Record starts a new part. Runs of missing Records each remain diagnostic; they neither delete neighbors nor authorize a connecting edge. Leading/trailing missing runs have absent previous/next neighbors as appropriate. A Record without GPS is not labeled a quality rejection.

The mixed FIT baseline produces two singleton parts. Those are valid normalized evidence, even though they cannot themselves form positive-length edges. `success` means positioned canonical evidence exists, not assessability or usability. An all-missing-position source yields no CanonicalTrack and no spatial assessment.

Repeated coordinates, repeated visits, zero-distance observations, apparent jumps and non-monotonic timestamps remain in source order. GPX decimal coordinates are converted to finite binary64 without epsilon, clamping or deduplication. Nonzero decimal underflow is rejected explicitly; 5e-13 and 1e-200 degree distinctions at zero survive. FIT semicircles use the format's exact `180 / 2**31` degree conversion; even one semicircle step survives.

## Diagnostics and future M2B

Diagnostic identity is an uppercase stable code, not library exception text. Optional source/field and previous/next parent positions identify the evidence. FIT `record_index` counts Records from zero (not summary/definition messages). GPX additionally records zero-based track, segment and point indices. Missing Records are source locations, never their own positioned TrackPositions.

| Class | Representative codes |
|---|---|
| Malformed bytes/XML or bad CRC | `MALFORMED_SOURCE`, `FIT_CRC_MISMATCH` |
| Invalid/unsupported source semantics | `INVALID_GPX_STRUCTURE`, `POSITION_OUT_OF_RANGE`, `UNSUPPORTED_FIT_FILE_TYPE`, `UNSUPPORTED_FIT_MULTIPLE_FILES` |
| Missing/invalid sentinel position | `POSITION_MISSING`, `POSITION_INVALID_SENTINEL` |
| Explicit source boundaries/empty parts | `SOURCE_CONTINUITY_BREAK`, `EMPTY_SOURCE_PART` |
| Unsupported timestamp evidence | `TIMESTAMP_RELATIVE`, `TIMESTAMP_TIMEZONE_MISSING`, `TIMESTAMP_UNREPRESENTABLE` |
| Unrepresentable values / hash guard | `NONFINITE_NUMERIC_VALUE`, `NUMERIC_PRECISION_UNREPRESENTABLE`, `SOURCE_HASH_MISMATCH` |

A positioned observation is explicitly represented in the canonical array and mapping rather than by a redundant success diagnostic. Diagnostics are emitted in source encounter order; nearest positioned neighbors are resolved afterward without changing canonical order.

M2B can reference the returned CanonicalTrack's exact `id/revision_id` and `ObservationSource.position` directly. For raw FIT Records 0 → missing 1 → 2, mappings are `(part=0, obs=0)` and `(part=1, obs=0)`; the missing diagnostic references those two parent positions. It does not create an edge. No quality-filtered array is substituted or reindexed. This supplies the normalized side of [the M1 quality-layer interface](quality-layer-interface.md); its QualityProjection algorithm remains unimplemented.

## FIT and GPX coverage

FIT accepts the original minimal FileId/Record inputs and complete Activity fixture. FileId must be first and type Activity; required summary-message presence is not imposed on the deliberately minimal fixtures. Chained FIT files fail explicitly rather than joining their tracks. fitdecode performs CRC/framing/profile decoding. Invalid sentinels are absent evidence; out-of-range coordinates are rejected rather than clamped.

Supported positioned FIT observations retain absolute UTC timestamp, altitude, cumulative distance and recorded/device speed where available. These are profile unit conversions, not geometric speed calculations. Native enhanced altitude/speed takes precedence over basic telemetry, falling back when unavailable. Tests caught fitdecode's expansion of basic fields into same-named enhanced components before native enhanced fields; production selection now uses the native decoded field when present. Relative FIT timestamps remain diagnostics rather than invented calendar dates.

GPX production validates the complete local 1.1 XSD before normalization. Malformed XML and XML-well-formed invalid root/version/range are distinct stable failures. DTDs are unsupported and entity/network resolution is disabled. UTC offsets are converted explicitly; arbitrary source fractional-second digits survive without datetime microsecond truncation. A timestamp with no zone is diagnosed and omitted instead of assuming UTC. Optional elevation is retained. Unknown extension telemetry remains in raw evidence and is not added to core observations.

M2A supports track-based GPX. Files containing route/waypoint geometry fail with `UNSUPPORTED_GPX_ROUTE_OR_WAYPOINT`; no unreviewed continuity rule is invented for them. This is an explicit parser support limit, not a change to core geometry semantics.

## Equivalence and independent oracle evidence

Both committed groups (`basic-route`, `complete-route`) produce matching ordered part/observation counts and exactly matching shared timestamps. Their ordered coordinates differ only by FIT semicircle quantization. The comparison uses the existing manifest tolerance and, more strictly, the known nearest-encoding bound of half one semicircle unit (`90 / 2**31` degrees). It is an encoding error bound, not Hausdorff/set equality or arbitrary fuzzy geometry similarity.

Source hashes, exact TrackSource references and derived IDs legitimately differ. FIT-only recorded telemetry, diagnostic source locators and raw metadata are not required to equal GPX data. All canonical results satisfy the existing schema with source-neutral fields.

Tests combine explicit manual facts, M1 raw manifest expectations, independent source-baseline decoding/XSD checks and the frozen canonical schema. Repeated-ingestion comparisons are only the determinism test; they do not stand in for correctness. Input-file hashes/bytes are checked before and after all 12 fixtures. Two actual source-code mutations in disposable package copies—removing the missing-position break and retaining the previous GPX part—make their respective unmodified integration witnesses fail with assertion errors.

## Self-review before staging

Verified no observation sorting, deduplication, coordinate repair, timestamp inference, missing-position bridge or GPX flattening. No quality rejection/smoothing, spatial relation, TargetSegment, speed derivation, GeoJSON or map path exists. Core schemas and all M1 fixture/manifests remain unchanged. Supporting parser/result types own no identity. Serialization uses explicit source refs and deterministic hashes.

Demonstrated defects corrected before staging were native-enhanced FIT field selection, relative-timestamp type handling, and preservation of GPX fractional precision. Adversarial tests also cover partial sentinels, multiple missing Records, empty segments, multiple tracks, corrupt FIT, explicit unsupported formats, absent timezone, non-finite/underflow values, repeated visits and apparent jumps. No frozen-contract blocker was found.

## Validation record

All commands below passed in isolated Python 3.11.16 with the workflow's development requirements (jsonschema 4.26.0, Shapely 2.1.2/GEOS 3.13.1, fitdecode 0.11.0, lxml 6.1.3). M1 fixture counts do not change because new coverage is conventional production tests.

| Command | Observed result |
|---|---|
| `python -m unittest discover -s tests -p 'test_canonical_ingestion.py' -v` | PASS: 39 focused M2A tests |
| `python scripts/validate_schema_fixtures.py --verbose` | PASS: 260/260 |
| `python scripts/validate_semantic_fixtures.py --verbose` | PASS: 56/56 |
| `python scripts/validate_edge_case_coverage.py` | PASS: 29/29; 13 owned non-file contracts |
| `python scripts/validate_source_fixture_baseline.py` | PASS: 12/12; two equivalence groups |
| `python -m unittest discover -s tests -p 'test_*.py' -v` | PASS: 64 tests (25 retained M1 + 39 M2A) |
| `git diff --check` | PASS: clean M2A diff |

Wheel build/install and GPX/local-XSD + mixed-FIT smoke tests also passed outside the checkout, with only runtime dependencies. The unchanged CI discovery automatically includes M2A tests after installing the package through `requirements-dev.txt`; its remote results will accompany the implementation PR.

## Limitations and non-goals

This is local, in-memory ingestion of one FIT Activity stream or supported GPX tracks. Additional FIT profiles/developer-field/compressed-record combinations are delegated to the library but not claimed to have comprehensive project acceptance coverage. GPX routes/waypoints and unrepresentable timestamps are explicitly unsupported/diagnosed. Optional telemetry not supported by the current observation schema remains raw evidence; binary64 coordinates have finite representation limits.

No QualityProjection, GPS-quality threshold, usable-geometry filtering, gap-bound proof, TargetArea assessment, TargetSegment, derived speed/pace, GeoJSON/map, clustering, network adapter, persistence, reconciliation or training analysis is included. M2B must consume unchanged canonical parent indices and independently validate usable geometry. Later M2 spatial/visual stages and M3+ remain unfinished.
