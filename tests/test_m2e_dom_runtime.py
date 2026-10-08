"""Execute the generated offline SVG map script with DOM interaction witnesses."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from target_area_route_reconstruction import render_geojson_map
from test_geojson_export import make_export
from test_spatial_relation import arguments, route


class M2EDOMRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for DOM JS runtime smoke")
    def test_real_generated_map_script_controls_and_no_gap_chords(self):
        # Two separate accepted observed visits and one unresolved source gap.
        # A renderer adding a visual chord would introduce an extra SVG path.
        args = arguments(route([(1, 1), (1.5, 1)], [(1, 1), (1.5, 1)]))
        _, _, output = make_export(args)
        self.assertEqual(output.outcome, "produced", output.issues)
        page = render_geojson_map(output.geojson_json)
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "map.html"
            file.write_text(page, encoding="utf-8")
            process = subprocess.run(
                ["node", str(Path(__file__).parent / "map_dom_runtime_smoke.cjs"), str(file)],
                capture_output=True, text=True, timeout=30, check=False,
            )
        self.assertEqual(process.returncode, 0, process.stdout + "\n" + process.stderr)
        self.assertIn("PASS", process.stdout)


if __name__ == "__main__":
    unittest.main()
