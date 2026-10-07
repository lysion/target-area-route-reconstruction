"""Copy outside the checkout and run using an isolated installed-wheel Python."""

import sys
from pathlib import Path

import target_area_route_reconstruction as core
from target_area_route_reconstruction.quality_models import ParentReference


def main():
    fixtures, checkout = (Path(value).resolve() for value in sys.argv[1:])
    assert not Path(core.__file__).resolve().is_relative_to(checkout), core.__file__
    assert not Path.cwd().is_relative_to(checkout)
    target = {
        "schema_version": "0.1.0", "id": "wheel-target", "revision_id": "r1",
        "spatial_reference": "OGC:CRS84",
        "geometry": {"type": "Polygon", "coordinates": [
            [[-180, -90], [180, -90], [180, 90], [-180, 90], [-180, -90]]]},
        "definition_provenance": {"description": "Synthetic full-domain wheel witness"},
    }
    policy = core.QualityPolicy(include_domain_bounds=True)
    for name, expected_completeness in (
        ("fit/complete-activity.fit", "complete"),
        ("equivalent/basic.gpx", "complete"),
        ("gpx/discontinuity.gpx", "incomplete"),
    ):
        evidence = core.ingest_file(fixtures / name, source_kind=Path(name).suffix[1:],
                                   track_source={"id": "wheel-source", "revision_id": "r1"})
        assert evidence.canonical_track is not None, evidence
        quality = core.project_quality(evidence, policy=policy)
        assert quality.outcome == "produced", quality
        verified = core.verify_quality(quality.projection, evidence, policy=policy)
        assert verified.outcome == "valid", verified
        arguments = dict(evidence=evidence, quality_projection=quality.projection, quality_policy=policy,
                         target_area=target, target_reference=ParentReference("wheel-target", "r1"))
        result = core.prove_spatial_relation(**arguments)
        assert result.outcome == "produced", result
        assert result.proof.assessable
        assert result.proof.relation == "inside"
        assert result.proof.coverage_completeness == expected_completeness
        verified = core.verify_spatial_relation(result.proof, **arguments)
        assert verified.outcome == "valid", verified
        assert result.to_json() == core.prove_spatial_relation(**arguments).to_json()
    invalid = core.ingest_file(fixtures / "gpx/invalid-version.gpx", source_kind="gpx",
                               track_source={"id": "wheel-source", "revision_id": "r1"})
    assert invalid.outcome == "failure", invalid
    print("Installed wheel: 3 end-to-end cases + invalid-GPX XSD rejection PASS")


if __name__ == "__main__":
    main()
