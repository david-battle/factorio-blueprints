"""Generate the isolated five-quality recycler-output sorter test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_blueprint as bp


FILTER_QUALITIES = ("legendary", "epic", "rare", "uncommon")


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

    # One belt immediately adjacent to the first splitter input.
    add("turbo-transport-belt", 1.5, 2.5, direction=4)

    splitter_xs = (2.5, 5.5, 8.5, 11.5)
    for index, (x, quality) in enumerate(
        zip(splitter_xs, FILTER_QUALITIES, strict=True)
    ):
        add(
            "turbo-splitter",
            x,
            2,
            direction=4,
            filter={"quality": quality, "comparator": "="},
            output_priority="left",
        )

        # Filtered north output: adjacent curved belt, one straight belt,
        # then a proven north-moving inserter into the quality buffer.
        branch_x = x + 1
        add("turbo-transport-belt", branch_x, 1.5, direction=0)
        add("turbo-transport-belt", branch_x, 0.5, direction=0)
        add("bulk-inserter", branch_x, -0.5, direction=8, mirror=True)
        add("iron-chest", branch_x, -1.5)

        # Unfiltered south output stays eastbound. Two adjacent belts bridge
        # exactly to the next splitter; after the last splitter they lead to
        # the Normal remainder buffer.
        add("turbo-transport-belt", x + 1, 2.5, direction=4)
        add("turbo-transport-belt", x + 2, 2.5, direction=4)

    # Anything not extracted above is Normal quality.
    add("bulk-inserter", 14.5, 2.5, direction=12)
    add("iron-chest", 15.5, 2.5)

    return {
        "blueprint": {
            "item": "blueprint",
            "label": "QUP quality sorter",
            "description": (
                "Mixed recycler output enters from the west. Four connected "
                "quality-only splitters extract Legendary through Uncommon; "
                "the final remainder is Normal."
            ),
            "icons": [
                {"signal": {"name": "turbo-splitter"}, "index": 1},
                {"signal": {"name": "quality-module-3"}, "index": 2},
            ],
            "entities": entities,
            "version": bp.TARGET_VERSION,
        }
    }


def validate(data: dict) -> None:
    blueprint = data["blueprint"]
    entities = blueprint["entities"]
    assert len(entities) == 31
    assert [entity["entity_number"] for entity in entities] == list(range(1, 32))
    splitters = [e for e in entities if e["name"] == "turbo-splitter"]
    assert len(splitters) == 4
    assert [e["filter"]["quality"] for e in splitters] == list(FILTER_QUALITIES)
    assert all(e["output_priority"] == "left" for e in splitters)
    assert all("name" not in e["filter"] for e in splitters)
    assert sum(e["name"] == "iron-chest" for e in entities) == 5
    assert sum(e["name"] == "bulk-inserter" for e in entities) == 5
    positions = {
        (e["name"], e["position"]["x"], e["position"]["y"]) for e in entities
    }
    # Assert every splitter has adjacent south-lane input and output belts.
    for x in (2.5, 5.5, 8.5, 11.5):
        assert ("turbo-transport-belt", x - 1, 2.5) in positions
        assert ("turbo-transport-belt", x + 1, 2.5) in positions
        assert ("turbo-transport-belt", x + 1, 1.5) in positions
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
