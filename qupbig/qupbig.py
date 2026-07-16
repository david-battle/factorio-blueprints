"""Generate a two-chunk foundry pipe quality farm for Factorio 2.1.11."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "qup"))
import harness_blueprint as bp


MODULE_ITEMS = [{
    "id": {"name": "quality-module-3"},
    "items": {"in_inventory": [
        {"inventory": 4, "stack": stack} for stack in range(4)
    ]},
}]


def build_blueprint() -> dict:
    entities: list[dict] = []
    wires: list[list[int]] = []

    def add(name: str, x: float, y: float, **extra: object) -> dict:
        entity = {
            "entity_number": len(entities) + 1,
            "name": name,
            "position": {"x": x, "y": y},
        }
        entity.update(extra)
        entities.append(entity)
        return entity

    def belt(x: float, y: float, direction: int) -> None:
        add("turbo-transport-belt", x, y, direction=direction)

    # Two 5x5 foundries. Their north-side inserters feed one eastbound belt.
    # At the target rates, one quality-module recycler has comfortable capacity
    # for these two foundries while keeping the crossings inspectable.
    foundry_x = (5.5, 12.5)
    for x in foundry_x:
        add(
            "foundry", x, 12.5,
            recipe="casting-pipe",
            recipe_quality="normal",
            items=MODULE_ITEMS,
        )
        add("bulk-inserter", x, 9.5, direction=8, mirror=True)

    for x in [value + 0.5 for value in range(4, 32)]:
        belt(x, 8.5, 4)

    # Molten iron header. Each foundry's southwest input is directly adjacent
    # to this line at (center_x - 1, center_y + 3).
    for x in [value + 0.5 for value in range(1, 31)]:
        add("pipe", x, 15.5)

    # Exhaustive Legendary extraction; both belt lanes are protected.
    add(
        "turbo-splitter", 32.5, 8,
        direction=4,
        filter={"quality": "legendary", "comparator": "="},
        output_priority="left",
    )
    belt(33.5, 7.5, 4)
    add("bulk-inserter", 34.5, 7.5, direction=12)
    add("passive-provider-chest", 35.5, 7.5)

    # All lower qualities continue to a shared recycler feed.
    for x in [value + 0.5 for value in range(33, 47)]:
        belt(x, 8.5, 4)
    belt(47.5, 8.5, 8)
    for y in (9.5, 10.5):
        belt(47.5, y, 8)
    belt(47.5, 11.5, 12)
    for x in (46.5, 45.5, 44.5, 43.5, 42.5, 41.5, 40.5):
        belt(x, 11.5, 12)
    belt(39.5, 11.5, 8)
    belt(39.5, 12.5, 8)
    belt(39.5, 13.5, 4)

    # Verified-orientation recycler core. The input arm is at -1.5,-1.5
    # from its center and recovered iron plates eject automatically at
    # -0.5,-2.5 onto the westbound recovery belt.
    add("recycler", 42, 15, items=MODULE_ITEMS)
    add("bulk-inserter", 40.5, 13.5, direction=12)

    # Recovery belt runs east, away from the reject-input turn.
    belt(41.5, 12.5, 4)
    belt(42.5, 12.5, 4)
    add("bulk-inserter", 43.5, 12.5, direction=12)
    add("active-provider-chest", 44.5, 12.5)

    substations = [
        add("substation", x, y)
        for x, y in ((3, 5), (17, 5), (31, 5), (45, 5), (59, 5),
                     (10, 20), (30, 20), (50, 20))
    ]
    for left, right in ((0, 1), (1, 2), (2, 3), (3, 4),
                        (0, 5), (2, 6), (3, 7)):
        wires.append([
            substations[left]["entity_number"], 5,
            substations[right]["entity_number"], 5,
        ])

    add("roboport", 40, 22)

    return {"blueprint": {
        "item": "blueprint",
        "label": "QUPBIG foundry pipe quality farm",
        "description": (
            "Two foundries cast pipes from molten iron with Quality Module 3s; "
            "Legendary pipes are extracted and all lower qualities are recycled "
            "to quality iron plates. Factorio 2.1.11."
        ),
        "icons": [
            {"signal": {"name": "foundry"}, "index": 1},
            {"signal": {"name": "pipe"}, "index": 2},
            {"signal": {"name": "quality-module-3"}, "index": 3},
        ],
        "entities": entities,
        "wires": wires,
        "snap-to-grid": {"x": 64, "y": 32},
        "absolute-snapping": True,
        "position-relative-to-grid": {"x": 0, "y": 0},
        "version": bp.TARGET_VERSION,
    }}


FOOTPRINTS = {
    "active-provider-chest": (1, 1),
    "bulk-inserter": (1, 1),
    "foundry": (5, 5),
    "passive-provider-chest": (1, 1),
    "pipe": (1, 1),
    "recycler": (4, 4),
    "roboport": (4, 4),
    "substation": (2, 2),
    "turbo-splitter": (1, 2),
    "turbo-transport-belt": (1, 1),
}


def validate(data: dict) -> None:
    blueprint = data["blueprint"]
    entities = blueprint["entities"]
    assert [e["entity_number"] for e in entities] == list(range(1, len(entities) + 1))
    foundries = [e for e in entities if e["name"] == "foundry"]
    assert len(foundries) == 2
    assert all(e["recipe"] == "casting-pipe" for e in foundries)
    assert all(e["recipe_quality"] == "normal" for e in foundries)
    assert all(e["items"] == MODULE_ITEMS for e in foundries)
    assert not any(e["name"] == "pump" for e in entities)
    recyclers = [e for e in entities if e["name"] == "recycler"]
    assert len(recyclers) == 1
    assert all(e["items"] == MODULE_ITEMS for e in recyclers)
    splitters = [e for e in entities if e["name"] == "turbo-splitter"]
    assert len(splitters) == 1
    assert splitters[0]["filter"] == {"quality": "legendary", "comparator": "="}
    assert splitters[0]["output_priority"] == "left"
    by_center = {
        (e["position"]["x"], e["position"]["y"]): e for e in entities
    }
    for foundry in foundries:
        x, y = foundry["position"]["x"], foundry["position"]["y"]
        assert by_center[(x, y - 4)]["name"] == "turbo-transport-belt"
        assert by_center[(x, y - 4)]["direction"] == 4
        assert by_center[(x, y - 3)]["name"] == "bulk-inserter"
        assert by_center[(x - 1, y + 3)]["name"] == "pipe"
        assert by_center[(x + 1, y + 3)]["name"] == "pipe"
    recycler = recyclers[0]
    rx, ry = recycler["position"]["x"], recycler["position"]["y"]
    assert by_center[(rx - 2.5, ry - 1.5)]["name"] == "turbo-transport-belt"
    assert by_center[(rx - 2.5, ry - 1.5)]["direction"] == 4
    assert by_center[(rx - 1.5, ry - 1.5)]["name"] == "bulk-inserter"
    assert by_center[(rx - 0.5, ry - 2.5)]["name"] == "turbo-transport-belt"
    assert blueprint["snap-to-grid"] == {"x": 64, "y": 32}
    assert blueprint["absolute-snapping"] is True
    assert blueprint["position-relative-to-grid"] == {"x": 0, "y": 0}
    centers = [(e["position"]["x"], e["position"]["y"]) for e in entities]
    duplicates = sorted({center for center in centers if centers.count(center) > 1})
    assert not duplicates, f"duplicate entity centers: {duplicates}"
    for entity in entities:
        width, height = FOOTPRINTS[entity["name"]]
        x, y = entity["position"]["x"], entity["position"]["y"]
        assert 0 <= x - width / 2 and x + width / 2 <= 64
        assert 0 <= y - height / 2 and y + height / 2 <= 32


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    data = build_blueprint()
    validate(data)
    value = bp.encode(data)
    validate(bp.decode(value))
    args.output.write_text(value + "\n", encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
