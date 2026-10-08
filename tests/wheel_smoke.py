"""Copy outside the checkout and run using an isolated installed-wheel Python."""

import sys
import json
import math
from dataclasses import replace
from importlib.resources import files
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
        assembled = core.assemble_spatial_entities(proof=result.proof, **arguments)
        assert assembled.outcome == "produced", assembled
        assert core.verify_spatial_entities(assembled.bundle, proof=result.proof, **arguments).outcome == "valid"
        assert assembled.to_json() == core.assemble_spatial_entities(proof=result.proof, **arguments).to_json()
        # M2E release gate: exercise both new public modules from the installed
        # (non-editable) wheel against real FIT and GPX fixture ingestion.
        exported = core.export_geojson(bundle=assembled.bundle, proof=result.proof, **arguments)
        assert exported.outcome == "produced", exported.issues
        geojson = json.loads(exported.geojson_json)
        assert geojson["type"] == "FeatureCollection"
        assert geojson["metadata"]["relation"] == result.proof.relation
        assert geojson["metadata"]["coverage_completeness"] == expected_completeness
        target_features = [
            feature for feature in geojson["features"]
            if feature["properties"]["layer"] == "target_segment"
        ]
        assert len(target_features) == len(assembled.bundle.segments)
        assert [f["geometry"] for f in target_features] == [
            segment["geometry"] for segment in assembled.bundle.segments
        ]
        # A gap can only create Point endpoints; never a missing-route LineString.
        assert all(
            feature["geometry"]["type"] == "Point"
            for feature in geojson["features"]
            if feature["properties"]["layer"] == "gap_endpoint"
        )
        assert not any(
            feature["properties"]["layer"] == "gap"
            for feature in geojson["features"]
        )
        html = core.render_geojson_map(exported.geojson_json)
        assert '<svg id="map"' in html and 'id="evidence"' in html
        assert 'data-layer="gap_endpoint"' in html
        assert "Missing GPS sections are not drawn" in html
        assert html == core.render_geojson_map(exported.geojson_json)
        # Installed M2F proof: run the new exporter and offline coloring renderer
        # using real FIT/GPX data, not only source-tree tests or import checks.
        metric_export = core.export_temporal_geojson(
            bundle=assembled.bundle, proof=result.proof, **arguments
        )
        assert metric_export.outcome == "produced", metric_export
        metric_fc = json.loads(metric_export.geojson_json)
        assert metric_fc["features"][:len(geojson["features"])] == geojson["features"]
        temporal = metric_fc["metadata"]["temporal_overlay"]
        assert temporal["algorithm"]["version"] == "0.1.0"
        metric_features = [
            feature for feature in metric_fc["features"]
            if feature["properties"]["layer"] == "target_metric_edge"
        ]
        assert all(feature["geometry"]["type"] == "LineString" for feature in metric_features)
        assert all(feature["properties"]["metric"]["status"] != "valid" or
                   feature["properties"]["metric"]["duration_s"] > 0
                   for feature in metric_features)
        assert all(feature["properties"]["metric"]["status"] == "valid" or
                   feature["properties"]["metric"]["speed_mps"] is None
                   for feature in metric_features)
        assert temporal["counts"]["valid"] + temporal["counts"]["unavailable"] == len(metric_features)
        metric_html = core.render_geojson_map(metric_export.geojson_json)
        assert 'data-layer="target_metric_edge"' in metric_html
        assert 'id="metric-mode"' in metric_html
        assert "metricColor(" in metric_html
        assert metric_html == core.render_geojson_map(metric_export.geojson_json)
        pace_export = core.export_temporal_geojson(
            bundle=assembled.bundle, proof=result.proof,
            metric_mode="pace_s_per_km", **arguments
        )
        assert pace_export.outcome == "produced", pace_export
        assert json.loads(pace_export.geojson_json)["metadata"]["temporal_overlay"]["mode"] == "pace_s_per_km"
        # Exercise installed M2D modules and offline JSON schemas, not just
        # successful imports that might accidentally read the checkout.
        for schema in ("common", "canonical-track", "target-area", "spatial-assessment", "target-segment"):
            resource = files(core).joinpath("spec", schema + ".schema.json")
            assert json.loads(resource.read_text())["$schema"].endswith("2020-12/schema")
        bundle = assembled.bundle
        forged = replace(bundle, assessment_json='{"relation":"outside",' + bundle.assessment_json[1:])
        checked = core.verify_spatial_entities(forged, proof=result.proof, **arguments)
        assert [i.code for i in checked.issues] == ["M2D_DUPLICATE_JSON_MEMBER"], checked
        rejected_export = core.export_geojson(
            bundle=forged, proof=result.proof, **arguments
        )
        assert rejected_export.outcome == "invalid_input", rejected_export
        assert rejected_export.geojson_json is None
        segments = list(bundle.segments)
        segments[0]["geometry"]["coordinates"][0][0] = math.nextafter(
            segments[0]["geometry"]["coordinates"][0][0], math.inf)
        forged = replace(bundle, segment_json=tuple(json.dumps(s) for s in segments))
        checked = core.verify_spatial_entities(forged, proof=result.proof, **arguments)
        assert "M2D_CANONICAL_SNAPSHOT_MISMATCH" in [i.code for i in checked.issues], checked
        assert "M2D_GEOMETRY_REGEN_MISMATCH" not in [i.code for i in checked.issues], checked
    invalid = core.ingest_file(fixtures / "gpx/invalid-version.gpx", source_kind="gpx",
                               track_source={"id": "wheel-source", "revision_id": "r1"})
    assert invalid.outcome == "failure", invalid
    print("Installed wheel: 3 M2A→M2F FIT/GPX-to-temporal-GeoJSON/map cases, M2E identity preservation, 9 JSON/snapshot/export attacks, 5 packaged schemas + invalid-GPX XSD rejection PASS")


if __name__ == "__main__":
    main()
