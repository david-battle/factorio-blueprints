import importlib.util
import math
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).parents[1] / "qup_analysis.py"
SPEC = importlib.util.spec_from_file_location("qup_analysis", MODULE_PATH)
qup_analysis = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = qup_analysis
SPEC.loader.exec_module(qup_analysis)


class QualityDistributionTests(unittest.TestCase):
    def test_normal_ten_percent_distribution(self):
        actual = qup_analysis.quality_distribution(0, 0.1)
        expected = (0.9, 0.09, 0.009, 0.0009, 0.0001)
        for observed, wanted in zip(actual, expected):
            self.assertAlmostEqual(observed, wanted)

    def test_epic_ten_percent_distribution(self):
        self.assertEqual(
            qup_analysis.quality_distribution(3, 0.1),
            (0.0, 0.0, 0.0, 0.9, 0.1),
        )

    def test_every_distribution_sums_to_one(self):
        for base in range(5):
            self.assertTrue(math.isclose(sum(qup_analysis.quality_distribution(base, 0.1)), 1.0))


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.scenario = qup_analysis.load_scenario()

    def test_target_build_crusher_recipe(self):
        self.assertEqual(
            self.scenario.ingredients,
            {"low-density-structure": 20, "steel-plate": 10, "electric-engine-unit": 10},
        )

    def test_verified_cycle_times(self):
        self.assertEqual(self.scenario.quality_assembler_cycle, 10.0)
        self.assertEqual(self.scenario.legendary_assembler_cycle, 8.0)
        self.assertEqual(self.scenario.recycler_cycle, 1.5625)

    def test_one_recycler_is_sufficient_in_expected_model(self):
        result = qup_analysis.expected_flow(self.scenario, recycler_count=1)
        self.assertEqual(result["minimum_recyclers"], 1)
        self.assertLess(result["recycler_utilization"], 1.0)
        self.assertAlmostEqual(result["assembler_utilization"]["normal"], 1.0)

    def test_two_recyclers_halve_utilization(self):
        one = qup_analysis.expected_flow(self.scenario, recycler_count=1)
        two = qup_analysis.expected_flow(self.scenario, recycler_count=2)
        self.assertAlmostEqual(two["recycler_utilization"], one["recycler_utilization"] / 2)


if __name__ == "__main__":
    unittest.main()
