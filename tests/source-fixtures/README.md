# Synthetic Raw Source Fixtures

This directory is the Milestone 1 raw parser-input baseline.

All files are synthetic and privacy-safe. No real activity location data is stored here.

## Files

- `equivalent/basic.gpx`
- `equivalent/basic.fit`

  Equivalent three-point route with identical UTC timestamps. `basic.fit` is a **minimal FIT message stream** containing FileId and Record, not a complete FIT Activity profile. Milestone 2 parsers must normalize them compatibly within the FIT semicircle coordinate tolerance declared in `manifest.json`.

- `fit/complete-activity.fit`

  Representative synthetic FIT Activity with FileId, three Records, Lap, Session, and Activity summary messages in event order. It is also coordinate/timestamp-equivalent to `equivalent/basic.gpx`.

- `gpx/no-timestamps.gpx`

  Spatially valid GPX with ordered positions and no timestamps. It establishes that missing timestamps do not invalidate spatial reconstruction.

- `gpx/discontinuity.gpx`

  One GPX track with two explicit `trkseg` elements. The expected canonical form contains two continuity parts with no inferred edge between them.

- `gpx/malformed.gpx`

  Intentionally malformed XML. Parsing must fail explicitly and must not synthesize a CanonicalTrack or spatial relation.

- `fit/no-position.fit`

  Minimal FIT message stream with timestamped Records but no position fields. It establishes that valid source evidence can still produce no usable CanonicalTrack and must never fall back to `outside`.

- `fit/invalid-position-sentinel.fit` and `fit/mixed-position.fit`

  FIT Records with the standard invalid `sint32` position sentinel, first in every Record and then between valid positioned Records. The mixed case preserves both valid positions while requiring an explicit continuity/quality decision before any connecting edge is trusted.

- `gpx/invalid-root.gpx`, `gpx/invalid-range.gpx`, and `gpx/invalid-version.gpx`

  Well-formed XML rejected by the vendored GPX 1.1 XSD. They distinguish XML parse success from GPX conformance. `gpx/malformed.gpx` remains the separate malformed-XML case.

## Machine-readable expectations

`manifest.json` records:

- SHA-256 for every raw fixture;
- source-level structural expectations;
- expected Milestone 2 normalization facts;
- the GPX/FIT equivalence contract.

Validate the baseline with:

```bash
python scripts/validate_source_fixture_baseline.py
```

Regenerate the deterministic raw files with:

```bash
python scripts/generate_synthetic_source_fixtures.py
```

The generator is fixture tooling only. It is not the production FIT/GPX parser.

The gate runs the repository's narrow FIT reader alongside pinned `fitdecode==0.11.0`, which independently checks FIT framing, CRC, profile field decoding, and invalid sentinels. The small pure-Python dependency is pinned so CI behavior is reproducible. GPX files are checked against the vendored official Topografix GPX 1.1 XSD (`spec/gpx-1.1.xsd`, SHA-256 `9e4d1988b862edbe556305b130f8f6f1b29864fefd0dc02d5dab04ccdd1f34d6`) using pinned `lxml==6.1.3`. The XSD is stored locally so CI never fetches it at test time.
