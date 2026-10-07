"""Prove the six promised metric/quality inputs exhibit distinct evidence shapes."""

from __future__ import annotations

import json
import math
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from ordered_spatial_oracle import observed_edges


def load(name: str) -> dict:
    return json.loads((ROOT / "tests/fixtures/metrics" / f"{name}.json").read_text())


def speed_evidence(track: dict) -> list[tuple[float, float]]:
    """Fixture diagnostic only; M2 owns validated speed/pace semantics."""
    result = []
    for part in track["parts"]:
        for left, right in zip(part["observations"], part["observations"][1:]):
            if "timestamp" not in left or "timestamp" not in right:
                continue
            elapsed = (datetime.fromisoformat(right["timestamp"].replace("Z", "+00:00"))
                       - datetime.fromisoformat(left["timestamp"].replace("Z", "+00:00"))).total_seconds()
            dlon = math.radians(right["position"][0] - left["position"][0])
            metres = 6371000 * abs(dlon)  # all synthetic points are at latitude zero
            result.append((metres, elapsed))
    return result


class MetricFixtureInputs(unittest.TestCase):
    def test_all_six_inputs_are_registered(self) -> None:
        cases = json.loads((ROOT / "tests/fixtures/metric-scenarios.json").read_text())["cases"]
        registered = {entry["path"] for entry in json.loads((ROOT / "tests/fixtures/manifest.json").read_text())["fixtures"]}
        self.assertEqual({case["name"] for case in cases}, {
            "constant-speed", "acceleration-deceleration", "pause",
            "gps-jump", "discontinuity", "missing-timestamps",
        })
        self.assertTrue(all(case["path"] in registered for case in cases))

    def test_constant_speed_and_acceleration_shapes(self) -> None:
        constant = speed_evidence(load("constant-speed"))
        variable = speed_evidence(load("acceleration-deceleration"))
        self.assertAlmostEqual(constant[0][0] / constant[0][1], constant[1][0] / constant[1][1])
        self.assertGreater(variable[1][0] / variable[1][1], variable[0][0] / variable[0][1])
        self.assertLess(variable[2][0] / variable[2][1], variable[1][0] / variable[1][1])

    def test_pause_and_jump_are_distinct_anomalies(self) -> None:
        paused = speed_evidence(load("pause"))
        jump = speed_evidence(load("gps-jump"))
        self.assertEqual(paused[1], (0.0, 40.0))
        self.assertGreater(jump[1][0] / jump[1][1], 10000)

    def test_discontinuity_has_no_cross_part_edge(self) -> None:
        track = load("discontinuity")
        self.assertEqual(len(track["parts"]), 2)
        self.assertEqual(len(list(observed_edges(track))), 2)

    def test_missing_timestamps_preserves_spatial_observations(self) -> None:
        track = load("missing-timestamps")
        self.assertEqual(len(track["parts"][0]["observations"]), 2)
        self.assertTrue(all("timestamp" not in observation for observation in track["parts"][0]["observations"]))
        self.assertEqual(speed_evidence(track), [])


if __name__ == "__main__":
    unittest.main()
