# M2D open-ended uncertainty reproducer

These are synthetic **contract probes**, not accepted M2D output or additions to the M1 linked-scenario manifest.

- `leading-gap.gpx`: empty source segment, then two outside positioned observations.
- `trailing-gap.gpx`: two outside positioned observations, then an empty source segment.
- `bounded-gap-control.gpx`: two nonempty outside parts; both real gap neighbors exist.
- `target-area.json`: valid local rectangle; the observed edges are outside it.

Run:

```sh
python -m unittest discover -s tests -p 'test_m2d_contract.py' -v
```

Each case goes through actual M2A ingestion, M2B producer/verifier and M2C producer/verifier. Leading/trailing cases legitimately produce assessable `unknown + incomplete` with a missing gap endpoint. Test-only candidate assessments faithfully retain that endpoint; the frozen SpatialAssessment schema rejects exactly its `type`. Omitting the endpoint fails `required`. The bounded control passes.

The tests also reproduce FIT missing-position prefix/suffix cases using the existing synthetic generator; reject dropping uncertainty and out-of-parent sentinels; and expose the false-green duplicate-known-endpoint workaround. No production assembler, new interpretation of point ranges, or accepted entity fixture is introduced. A passing test means the blocker was reproduced for the documented reason, not that M2D is implemented.

See [Proposed ADR-0011](../../docs/decisions/0011-open-ended-coverage-uncertainty.md) and [the M2D blocker record](../../docs/milestone2d-target-segments.md).
