import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).parents[1] / "harness_blueprint.py"
SPEC = importlib.util.spec_from_file_location("harness_blueprint", MODULE_PATH)
harness = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = harness
SPEC.loader.exec_module(harness)


class HarnessBlueprintTests(unittest.TestCase):
    def test_round_trip_and_semantics(self):
        data = harness.build_blueprint()
        harness.validate(data)
        harness.validate(harness.decode(harness.encode(data)))

    def test_exact_chunk_bounds_and_zero_offset(self):
        blueprint = harness.build_blueprint()["blueprint"]
        self.assertEqual(blueprint["position-relative-to-grid"], {"x": 0, "y": 0})
        self.assertEqual(blueprint["snap-to-grid"], {"x": 32, "y": 32})

    def test_blueprint_opens_with_concrete_crusher_recipe(self):
        blueprint = harness.build_blueprint()["blueprint"]
        self.assertNotIn("parameters", blueprint)
        self.assertNotIn("parameter-", harness.json.dumps(blueprint))
        self.assertEqual(
            {entity.get("recipe") for entity in blueprint["entities"] if "recipe" in entity},
            {"crusher"},
        )


if __name__ == "__main__":
    unittest.main()
