"""Execute the M2F optional metric overlay in the actual offline SVG JS runtime."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from target_area_route_reconstruction import export_temporal_geojson, render_geojson_map
from test_spatial_relation import arguments, rectangle
from test_quality_projection import ingest_parts
from test_geojson_export import make_export


class M2FMapRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js required (CI runs an explicit required Node gate)")
    def test_valid_and_missing_time_have_distinct_display_without_gap_chord(self):
        rows = [
            [{"position": (1, 1), "timestamp": "2026-10-07T00:00:00Z"},
             {"position": (1.5, 1), "timestamp": "2026-10-07T00:01:00Z"}],
            [{"position": (1, 1)},
             {"position": (1.5, 1)}],
        ]
        args = arguments(ingest_parts(rows), rectangle())
        proof, m2d, _ = make_export(args)
        exported = export_temporal_geojson(bundle=m2d.bundle, proof=proof, **args)
        self.assertEqual(exported.outcome, "produced", exported.issues)
        fc = json.loads(exported.geojson_json)
        self.assertEqual(fc["metadata"]["relation"], "unknown")
        self.assertEqual(fc["metadata"]["coverage_completeness"], "incomplete")
        edges = [f for f in fc["features"] if f["properties"]["layer"] == "target_metric_edge"]
        self.assertEqual([e["properties"]["metric"]["status"] for e in edges],
                         ["valid", "missing_timestamp"])
        html = render_geojson_map(exported.geojson_json)
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "map.html"
            dest.write_text(html, encoding="utf-8")
            cmd = ["node", str(Path(__file__).parent / "map_dom_runtime_smoke.cjs"), str(dest)]
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    check=False, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
