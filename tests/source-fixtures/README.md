# Synthetic Raw Source Fixtures

This directory is the Milestone 1 raw parser-input baseline.

All files are synthetic and privacy-safe. No real activity location data is stored here.

## Files

- `equivalent/basic.gpx`
- `equivalent/basic.fit`

  Equivalent three-point route with identical UTC timestamps. Milestone 2 parsers must normalize them compatibly within the FIT semicircle coordinate tolerance declared in `manifest.json`.

- `gpx/no-timestamps.gpx`

  Spatially valid GPX with ordered positions and no timestamps. It establishes that missing timestamps do not invalidate spatial reconstruction.

- `gpx/discontinuity.gpx`

  One GPX track with two explicit `trkseg` elements. The expected canonical form contains two continuity parts with no inferred edge between them.

- `gpx/malformed.gpx`

  Intentionally malformed XML. Parsing must fail explicitly and must not synthesize a CanonicalTrack or spatial relation.

- `fit/no-position.fit`

  Structurally valid FIT activity containing timestamped Record messages but no position fields. It establishes that valid source evidence can still produce no usable CanonicalTrack and must never fall back to `outside`.

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
