"""Independent diamond algebra: exact local budget, not a GEOS oracle.

Self-contained so the identical tests also run outside the checkout on a wheel.
"""
import math
import unittest
from fractions import Fraction as F
from unittest.mock import patch

from target_area_route_reconstruction import (
    TrackPosition, ingest_bytes, project_quality, prove_spatial_relation,
    verify_spatial_relation, assemble_spatial_entities,
    export_geojson, export_temporal_geojson,
)
from target_area_route_reconstruction.quality_models import ParentInterval, ParentReference


def arguments(kind="polygon", width=None, y=.375):
    center = .1
    width = math.ulp(center) if width is None else width
    diamond = [[center-width, 0.], [center, 1.], [center+width, 0.],
               [center, -1.], [center-width, 0.]]
    outer = [[0., -2.], [.2, -2.], [.2, 2.], [0., 2.], [0., -2.]]
    remote = [[170., 80.], [171., 80.], [171., 81.], [170., 81.], [170., 80.]]
    geometry = {"type": "Polygon", "coordinates": [diamond]}
    if kind == "hole":
        geometry["coordinates"] = [outer, diamond]
    elif kind == "multi":
        geometry = {"type": "MultiPolygon", "coordinates": [[diamond], [remote]]}
    area = dict(schema_version="0.1.0", id="sloped-budget", revision_id="r1",
                spatial_reference="OGC:CRS84", geometry=geometry,
                definition_provenance={"description": "independent diamond budget"})
    raw = (f'<gpx version="1.1" creator="budget" xmlns="http://www.topografix.com/GPX/1/1">'
           f'<trk><trkseg><trkpt lon="0.099" lat="{y}"/>'
           f'<trkpt lon="0.101" lat="{y}"/></trkseg></trk></gpx>').encode()
    evidence = ingest_bytes(raw, source_kind="gpx",
                            track_source={"id": "budget-source", "revision_id": "r1"})
    from target_area_route_reconstruction import QualityPolicy
    policy = QualityPolicy()
    quality = project_quality(evidence, policy=policy)
    assert evidence.outcome == "success" and quality.projection is not None
    return dict(evidence=evidence, quality_projection=quality.projection,
                quality_policy=policy, target_area=area,
                target_reference=ParentReference(area["id"], area["revision_id"]))


class SlopedBoundaryBudget(unittest.TestCase):
    def test_exact_positive_diamond_and_hole_fail_closed(self):
        # |x-center|/ulp(center) + |y| <= 1: no production geometry helper.
        c, u, y = F(.1), F(math.ulp(.1)), F(.375)
        low, high = c - (1-y)*u, c + (1-y)*u
        self.assertLess(low, high)
        self.assertEqual((u-(1-y)*u)/(high-low), F(3, 10))
        fractions = [(x-F(.099))/(F(.101)-F(.099)) for x in (low, high)]
        self.assertLess(float(fractions[0]), float(fractions[1]))
        for kind in ("polygon", "hole", "multi"):
            with self.subTest(kind=kind):
                result = prove_spatial_relation(**arguments(kind))
                self.assertEqual(result.outcome, "numerical_failure", result)
                self.assertIsNone(result.proof)
                self.assertIn("SPATIAL_EXACT_BOUNDARY_MISMATCH", [i.code for i in result.issues])

    def test_forged_old_extent_is_rejected_independently_and_downstream(self):
        args = arguments()
        low = float(F(9007199254740867, 18014398509481984))
        high = float(F(2251799813685279, 4503599627370496))
        start, end = TrackPosition(0, 0), TrackPosition(0, 1)
        a, b = TrackPosition(0, 0, low), TrackPosition(0, 0, high)
        old_spans = ((ParentInterval(a, b),), (ParentInterval(start, a), ParentInterval(b, end)))
        # Only bypass the producer. The verifier must recompute admission.
        with patch("target_area_route_reconstruction.spatial.clip_edge", return_value=old_spans):
            forged = prove_spatial_relation(**args).proof
        self.assertIsNotNone(forged)
        self.assertEqual(verify_spatial_relation(forged, **args).outcome, "invalid")
        assembled = assemble_spatial_entities(proof=forged, **args)
        self.assertNotEqual(assembled.outcome, "produced")
        self.assertIsNone(assembled.bundle)
        for export in (export_geojson, export_temporal_geojson):
            self.assertNotEqual(export(bundle=None, proof=forged, **args).outcome, "produced")

    def test_representable_sloped_crossing_and_boundary_remain_accepted(self):
        # Ordinary widths and exact vertices should not become unsupported.
        for y in (0., .375, 1.):
            with self.subTest(y=y):
                args = arguments(width=.0005, y=y)
                result = prove_spatial_relation(**args)
                self.assertEqual(result.outcome, "produced", result)
                self.assertEqual(verify_spatial_relation(result.proof, **args).outcome, "valid")
                if y < 1:
                    bundle = assemble_spatial_entities(proof=result.proof, **args).bundle
                    self.assertIsNotNone(bundle)
                    coordinates = bundle.segments[0]["geometry"]["coordinates"]
                    vertices = args["target_area"]["geometry"]["coordinates"][0]
                    # Use represented ring vertices, not an assumed decimal width.
                    x0 = F(.1) + (F(vertices[0][0])-F(.1))*(1-F(y))
                    x1 = F(.1) + (F(vertices[2][0])-F(.1))*(1-F(y))
                    for actual, expected in ((coordinates[0][0], x0), (coordinates[-1][0], x1)):
                        self.assertLessEqual(abs(F(actual)-expected), (x1-x0)/4)


if __name__ == "__main__":
    unittest.main()
