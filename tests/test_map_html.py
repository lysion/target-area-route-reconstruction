"""M2E offline map security and evidence rendering smoke tests."""
import json
import unittest
from target_area_route_reconstruction import render_geojson_map


class M2EMapTests(unittest.TestCase):
    def test_offline_map_controls_and_no_gap_line(self):
        fc={"type":"FeatureCollection","metadata":{"relation":"unknown","coverage_completeness":"incomplete"},
            "features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[1,2]},
                "properties":{"layer":"gap_endpoint","gap_index":0}}]}
        page=render_geojson_map(json.dumps(fc))
        self.assertIn('data-layer="gap_endpoint"',page)
        self.assertIn('id="reset"',page)
        self.assertIn('No inferred routes',page)
        self.assertNotIn("https://",page)
        self.assertIn('svg.addEventListener("wheel"',page)

    def test_provenance_and_title_do_not_inject_script(self):
        attack='</script><script>alert("owned")</script>'
        fc={"type":"FeatureCollection","features":[{"type":"Feature",
            "geometry":{"type":"Point","coordinates":[0,0]},
            "properties":{"layer":"gap_endpoint","text":attack}}]}
        page=render_geojson_map(json.dumps(fc),title=attack)
        self.assertNotIn(attack,page)
        self.assertIn("&lt;/script&gt;",page)
        self.assertIn("u003c",page)
        self.assertEqual(page.count("<script"),2)

    def test_bad_collection_or_layer_rejected(self):
        for doc in ('{}','{"type":"FeatureCollection","features":{}}',
                    '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"layer":"untrusted"}}]}'):
            with self.subTest(doc=doc),self.assertRaises(ValueError):
                render_geojson_map(doc)


if __name__=="__main__":
    unittest.main()
