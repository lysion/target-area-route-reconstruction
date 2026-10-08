"""Independent PR #8 adversarial probes; intentionally fails on demonstrated contracts.

Runs only on a separate review branch. No PR #8 production code is altered.
"""
import copy
import math
import unittest

from shapely.geometry import shape

from target_area_route_reconstruction import (
    assemble_spatial_entities, prove_spatial_relation, verify_spatial_entities,
)
from target_area_route_reconstruction._m2d_common import canonical_json
from target_area_route_reconstruction.spatial_entities_models import SpatialEntityBundle
from test_spatial_relation import arguments, route
from validate_semantic_fixtures import validate_segment_against_parent


class PR8AdversarialReview(unittest.TestCase):
    def assembled(self):
        args = arguments(route([(-1, 1), (3, 1)]))
        proof = prove_spatial_relation(**args).proof
        result = assemble_spatial_entities(proof=proof, **args)
        self.assertEqual(result.outcome, "produced", result.issues)
        self.assertEqual(
            verify_spatial_entities(result.bundle, proof=proof, **args).outcome, "valid")
        return args, proof, result.bundle

    def test_bounded_ulp_coordinate_equivalent_to_parent_should_validate(self):
        """Existing numerical policy allows small ULP error; M1 validates it."""
        args, proof, bundle = self.assembled()
        segments = copy.deepcopy(list(bundle.segments))
        line = segments[0]["geometry"]["coordinates"]
        self.assertEqual(line[0], [0.0, 1.0])
        line[0][0] = math.nextafter(line[0][0], math.inf)
        self.assertEqual(
            validate_segment_against_parent(
                segments[0], args["evidence"].canonical_track,
                shape(args["target_area"]["geometry"])), [],
            "Independent frozen M1 oracle should accept equivalent geometry")
        altered = SpatialEntityBundle(
            bundle.assessment_json,
            tuple(canonical_json(s) for s in segments))
        check = verify_spatial_entities(altered, proof=proof, **args)
        self.assertEqual(
            check.outcome, "valid",
            "M2D must use documented bounded comparison rather than strict binary64 equality")

    def test_duplicate_json_member_must_fail_closed(self):
        """Two conflicting relations in immutable raw JSON cannot be authority."""
        args, proof, bundle = self.assembled()
        altered = SpatialEntityBundle(
            '{"relation":"outside",' + bundle.assessment_json[1:],
            bundle.segment_json)
        self.assertNotEqual(altered.assessment_json, bundle.assessment_json)
        self.assertEqual(
            verify_spatial_entities(altered, proof=proof, **args).outcome, "invalid",
            "Duplicate authoritative JSON keys must not pass a strict verifier")


if __name__ == "__main__":
    unittest.main()
