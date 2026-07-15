"""Generate the isolated QUP Legendary-extraction and recycler test."""

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

    # Feed test products east on the southern splitter lane.
    for x in (3.5, 4.5):
        add("turbo-transport-belt", x, 2.5, direction=4)

    # East-facing splitter: the left/north lane receives Legendary products.
    add(
        "turbo-splitter",
        5.5,
        2,
        direction=4,
        filter={"quality": "legendary", "comparator": "="},
        output_priority="left",
    )

    # Filtered Legendary branch into a passive provider chest.
    add("turbo-transport-belt", 6.5, 1.5, direction=4)
    add("bulk-inserter", 7.5, 1.5, direction=12)
    add("passive-provider-chest", 8.5, 1.5)

    # Unfiltered Normal-through-Epic branch into the recycler.
    add("turbo-transport-belt", 6.5, 2.5, direction=4)
    add("turbo-transport-belt", 7.5, 2.5, direction=4)
    add("bulk-inserter", 8.5, 2.5, direction=12)
    add("recycler", 10, 4, items=MODULE_ITEMS)

    # The recycler ejects directly onto the first belt; no output inserter.
    for x in (9.5, 10.5, 11.5):
        add("turbo-transport-belt", x, 1.5, direction=4)

    return {
        "blueprint": {
            "item": "blueprint",
            "label": "QUP recycler gate",
            "description": (
                "Feed mixed-quality Crushers from the west. Legendary goes to "
                "the provider; Normal through Epic goes through the quality-module recycler."
            ),
            "icons": [
                {"signal": {"name": "recycler"}, "index": 1},
                {"signal": {"name": "crusher"}, "index": 2},
            ],
            "entities": entities,
            "version": bp.TARGET_VERSION,
        }
    }


def validate(data: dict) -> None:
    blueprint = data["blueprint"]
    entities = blueprint["entities"]
    assert len(entities) == 13
    assert [entity["entity_number"] for entity in entities] == list(range(1, 14))
    assert sum(e["name"] == "recycler" for e in entities) == 1
    assert sum(e["name"] == "turbo-splitter" for e in entities) == 1
    assert sum(e["name"] == "passive-provider-chest" for e in entities) == 1
    assert sum(e["name"] == "bulk-inserter" for e in entities) == 2
    recycler = next(e for e in entities if e["name"] == "recycler")
    slots = recycler["items"][0]["items"]["in_inventory"]
    assert slots == [{"inventory": 4, "stack": stack} for stack in range(4)]
    assert recycler["position"] == {"x": 10, "y": 4}
    assert any(
        e["name"] == "turbo-transport-belt"
        and e["position"] == {"x": 9.5, "y": 1.5}
        for e in entities
    )
    splitter = next(e for e in entities if e["name"] == "turbo-splitter")
    assert splitter["filter"] == {"quality": "legendary", "comparator": "="}
    assert splitter["output_priority"] == "left"
    assert "name" not in splitter["filter"]
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
