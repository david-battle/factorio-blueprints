"""Generate one buffered Epic-quality QUP assembler tier test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_blueprint as bp


MODULE_ITEMS = [
    {
        "id": {"name": "quality-module-3"},
        "items": {
            "in_inventory": [
                {"inventory": 4, "stack": stack} for stack in range(4)
            ]
        },
    }
]


def build_blueprint() -> dict:
    entities: list[dict] = []

    def add(name: str, x: float, y: float, **extra: object) -> dict:
        entity = {
            "entity_number": len(entities) + 1,
            "name": name,
            "position": {"x": x, "y": y},
        }
        entity.update(extra)
        entities.append(entity)
        return entity

    assembler = add(
        "assembling-machine-3",
        2.5,
        3.5,
        recipe="crusher",
        recipe_quality="epic",
        items=MODULE_ITEMS,
    )
    add("steel-chest", 1.5, 6.5)

    # Steel buffer -> assembler, using the proven north-moving geometry.
    add("bulk-inserter", 1.5, 5.5, direction=8, mirror=True)
    # Epic ingredient belt -> steel buffer.
    add("bulk-inserter", 1.5, 7.5, direction=8, mirror=True)
    for x in (-0.5, 0.5, 1.5):
        add("turbo-transport-belt", x, 8.5, direction=4)

    # Assembler -> shared-product-belt interface, copied from the proven cell.
    add("bulk-inserter", 1.5, 1.5, direction=8, mirror=True)
    for x in (1.5, 2.5, 3.5):
        add("turbo-transport-belt", x, 0.5, direction=4)

    return {
        "blueprint": {
            "item": "blueprint",
            "label": "QUP Epic tier",
            "description": (
                "Feed mixed Epic Crusher ingredients from the west. A steel "
                "buffer supplies an Epic-recipe AM3 with four Quality Module 3s."
            ),
            "icons": [
                {"signal": {"name": "assembling-machine-3"}, "index": 1},
                {"signal": {"name": "quality-module-3", "quality": "epic"}, "index": 2},
            ],
            "entities": entities,
            "version": bp.TARGET_VERSION,
        }
    }


def validate(data: dict) -> None:
    blueprint = data["blueprint"]
    entities = blueprint["entities"]
    assert len(entities) == 11
    assert [entity["entity_number"] for entity in entities] == list(range(1, 12))
    assert sum(e["name"] == "assembling-machine-3" for e in entities) == 1
    assert sum(e["name"] == "steel-chest" for e in entities) == 1
    assert sum(e["name"] == "bulk-inserter" for e in entities) == 3
    assert sum(e["name"] == "turbo-transport-belt" for e in entities) == 6
    assembler = next(e for e in entities if e["name"] == "assembling-machine-3")
    assert assembler["recipe"] == "crusher"
    assert assembler["recipe_quality"] == "epic"
    assert assembler["items"][0]["items"]["in_inventory"] == [
        {"inventory": 4, "stack": stack} for stack in range(4)
    ]
    inserters = [e for e in entities if e["name"] == "bulk-inserter"]
    assert all(e["direction"] == 8 and e["mirror"] is True for e in inserters)
    assert "requester-chest" not in json.dumps(blueprint)
    assert "parameter-" not in json.dumps(blueprint)


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
