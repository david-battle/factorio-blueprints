import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solar_chunk import (  # noqa: E402
    ABSOLUTE_GRID_OFFSET,
    BLUEPRINT_CENTER_OFFSET,
    Entity,
    BLUEPRINT_VERSION,
    blueprint_json,
    decode_blueprint,
    encode_blueprint,
    in_bounds,
    normalized_json,
    overlaps,
    pole_supplies,
    poles_can_connect,
    search,
    substation_supply_in_bounds,
    validate,
)


class BoundsTests(unittest.TestCase):
    def test_panel_inside_and_outside(self):
        self.assertTrue(in_bounds(Entity(1, "solar-panel", 29, 29)))
        self.assertFalse(in_bounds(Entity(1, "solar-panel", 30, 29)))
        self.assertFalse(in_bounds(Entity(1, "solar-panel", -1, 0)))


class OverlapTests(unittest.TestCase):
    def test_overlap_and_edge_contact(self):
        first = Entity(1, "solar-panel", 0, 0)
        self.assertTrue(overlaps(first, Entity(2, "small-electric-pole", 2, 2)))
        self.assertFalse(overlaps(first, Entity(2, "solar-panel", 3, 0)))


class CoverageTests(unittest.TestCase):
    def test_assumed_intersection_rule(self):
        pole = Entity(1, "small-electric-pole", 3, 3)
        self.assertTrue(pole_supplies(pole, Entity(2, "solar-panel", 6, 3)))
        self.assertFalse(pole_supplies(pole, Entity(3, "solar-panel", 7, 3)))

    def test_validator_rejects_unsupplied_panel(self):
        entities = (
            Entity(1, "small-electric-pole", 0, 0),
            Entity(2, "solar-panel", 20, 20),
        )
        self.assertIn("solar panel 2 is not supplied", validate(entities).errors)

    def test_substation_supply_area_must_stay_inside_chunk(self):
        edge = Entity(1, "substation", 0, 0)
        inside = Entity(1, "substation", 8, 8)
        self.assertFalse(substation_supply_in_bounds(edge))
        self.assertTrue(substation_supply_in_bounds(inside))
        self.assertIn(
            "substation 1 supply area extends outside the chunk",
            validate((edge,)).errors,
        )

    def test_search_keeps_all_substation_supply_areas_inside(self):
        result = search()
        self.assertTrue(
            all(substation_supply_in_bounds(entity) for entity in result.entities)
        )


class ConnectivityTests(unittest.TestCase):
    def test_reach_and_disconnected_network(self):
        near = Entity(1, "small-electric-pole", 0, 0)
        self.assertTrue(poles_can_connect(near, Entity(2, "small-electric-pole", 7, 0)))
        far = Entity(2, "small-electric-pole", 20, 0)
        self.assertFalse(poles_can_connect(near, far))
        self.assertIn(
            "electric poles do not form one connected network",
            validate((near, far)).errors,
        )

    def test_connected_chain(self):
        poles = tuple(Entity(i + 1, "small-electric-pole", i * 7, 0) for i in range(3))
        self.assertTrue(validate(poles).valid)


class SearchTests(unittest.TestCase):
    def test_search_returns_valid_best_found_layout(self):
        result = search()
        self.assertTrue(result.validation.valid)
        self.assertGreater(result.panel_count, 0)
        self.assertEqual(96, result.panel_count)
        self.assertEqual(4, result.pole_count)
        self.assertEqual(result.search_status, "best-found-not-proven-optimal")

    def test_winning_layout_has_corner_reaching_substations_and_reflection_symmetry(self):
        result = search()
        substations = [e for e in result.entities if e.prototype == "substation"]
        self.assertEqual(
            {(9, 9), (23, 9), (9, 23), (23, 23)},
            {(e.center2[0] / 2, e.center2[1] / 2) for e in substations},
        )
        footprints = {
            (e.prototype, e.left, e.top) for e in result.entities
        }
        for entity in result.entities:
            self.assertIn((entity.prototype, 32 - entity.right, entity.top), footprints)
            self.assertIn((entity.prototype, entity.left, 32 - entity.bottom), footprints)

    def test_checked_in_layout_json_is_current(self):
        layout_path = Path(__file__).resolve().parents[1] / "layout.json"
        self.assertEqual(
            json.loads(normalized_json(search())),
            json.loads(layout_path.read_text(encoding="utf-8")),
        )


class BlueprintTests(unittest.TestCase):
    def test_encode_decode_round_trip_and_schema(self):
        result = search()
        document = blueprint_json(result)
        encoded = encode_blueprint(document)
        decoded = decode_blueprint(encoded)
        self.assertEqual(document, decoded)

        blueprint = decoded["blueprint"]
        self.assertEqual(BLUEPRINT_VERSION, blueprint["version"])
        self.assertEqual({"x": 32, "y": 32}, blueprint["snap-to-grid"])
        self.assertTrue(blueprint["absolute-snapping"])
        self.assertEqual(ABSOLUTE_GRID_OFFSET, blueprint["position-relative-to-grid"])
        self.assertEqual(len(result.entities), len(blueprint["entities"]))
        for source, exported in zip(result.entities, blueprint["entities"]):
            self.assertEqual(source.prototype, exported["name"])
            self.assertEqual("normal", exported["quality"])
            self.assertEqual(
                source.center2[0] / 2 - BLUEPRINT_CENTER_OFFSET,
                exported["position"]["x"],
            )
            self.assertEqual(
                source.center2[1] / 2 - BLUEPRINT_CENTER_OFFSET,
                exported["position"]["y"],
            )

    def test_exported_nominal_bounds_fill_one_chunk_snap_cell(self):
        result = search()
        document = blueprint_json(result)
        exported_by_id = {
            entity["entity_number"]: entity for entity in document["blueprint"]["entities"]
        }
        for source in result.entities:
            position = exported_by_id[source.entity_id]["position"]
            left = position["x"] - source.spec.width / 2
            right = position["x"] + source.spec.width / 2
            top = position["y"] - source.spec.height / 2
            bottom = position["y"] + source.spec.height / 2
            self.assertGreaterEqual(left, 0)
            self.assertLessEqual(right, 32)
            self.assertGreaterEqual(top, 0)
            self.assertLessEqual(bottom, 32)

        # Heavy world chunk lines lie at coordinates divisible by 32.
        self.assertEqual({"x": 0, "y": 0}, ABSOLUTE_GRID_OFFSET)

    def test_checked_in_blueprint_is_current_and_decodable(self):
        blueprint_path = Path(__file__).resolve().parents[1] / "blueprint.txt"
        encoded = blueprint_path.read_text(encoding="ascii").strip()
        expected = blueprint_json(search())
        self.assertEqual(expected, decode_blueprint(encoded))


if __name__ == "__main__":
    unittest.main()
