"""Generate the powered Uncommon-through-Legendary QUP bank test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_blueprint as bp


QUALITIES = ("uncommon", "rare", "epic", "legendary")
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

    centers = (2.5, 5.5, 8.5, 11.5)
    for center_x, quality in zip(centers, QUALITIES, strict=True):
        assembler_extra = {} if quality == "legendary" else {"items": MODULE_ITEMS}
        add(
            "assembling-machine-3",
            center_x,
            3.5,
            recipe="crusher",
            recipe_quality=quality,
            **assembler_extra,
        )
        add("steel-chest", center_x - 1, 6.5)
        add("bulk-inserter", center_x - 1, 5.5, direction=8, mirror=True)
        add("bulk-inserter", center_x - 1, 7.5, direction=8, mirror=True)
        # Two connected northbound tiles form this quality lane's interface.
        add("turbo-transport-belt", center_x - 1, 9.5, direction=0)
        add("turbo-transport-belt", center_x - 1, 8.5, direction=0)
        add("bulk-inserter", center_x - 1, 1.5, direction=8, mirror=True)

    # Shared eastbound product belt.
    for x in [value + 0.5 for value in range(14)]:
        add("turbo-transport-belt", x, 0.5, direction=4)

    # Covers the complete compact bank without occupying a material lane.
    add("substation", 7, 11)

    return {
        "blueprint": {
            "item": "blueprint",
            "label": "QUP high bank",
            "description": (
                "Powered Uncommon-through-Legendary Crusher bank. Separate "
                "quality-lane inputs feed steel buffers; products share one belt."
            ),
            "icons": [
                {"signal": {"name": "assembling-machine-3"}, "index": 1},
                {"signal": {"name": "quality-module-3", "quality": "legendary"}, "index": 2},
            ],
            "entities": entities,
            "version": bp.TARGET_VERSION,
        }
    }


def validate(data: dict) -> None:
    blueprint = data["blueprint"]
    entities = blueprint["entities"]
    assert len(entities) == 43
    assert [entity["entity_number"] for entity in entities] == list(range(1, 44))
    assemblers = [e for e in entities if e["name"] == "assembling-machine-3"]
    assert [e["recipe_quality"] for e in assemblers] == list(QUALITIES)
    assert all(e["recipe"] == "crusher" for e in assemblers)
    assert all("items" in e for e in assemblers[:3])
    assert "items" not in assemblers[3]
    assert sum(e["name"] == "steel-chest" for e in entities) == 4
    assert sum(e["name"] == "bulk-inserter" for e in entities) == 12
    assert sum(e["name"] == "substation" for e in entities) == 1
    assert sum(e["name"] == "turbo-transport-belt" for e in entities) == 22
    assert all(
        e["direction"] == 8 and e["mirror"] is True
        for e in entities
        if e["name"] == "bulk-inserter"
    )
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
