"""Generate the integrated QUP beta blueprint."""

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

    # One compact row: four Normal cells, then the four higher-quality cells.
    normal_centers = (2.5, 5.5, 8.5, 11.5)
    high_specs = (
        (14.5, "legendary"),
        (17.5, "epic"),
        (20.5, "rare"),
        (23.5, "uncommon"),
    )

    for center_x in normal_centers:
        assembler = add(
            "assembling-machine-3",
            center_x,
            5.5,
            recipe="crusher",
            recipe_quality="normal",
            control_behavior={"read_ingredients": True},
            items=MODULE_ITEMS,
        )
        requester = add(
            "requester-chest",
            center_x - 1,
            8.5,
            control_behavior={
                "read_contents": False,
                "set_requests": True,
                "circuit_condition_enabled": False,
            },
            request_filters={
                "sections": [{"index": 1}],
                "request_from_buffers": True,
            },
        )
        add("bulk-inserter", center_x - 1, 7.5, direction=8, mirror=True)
        add("bulk-inserter", center_x - 1, 3.5, direction=8, mirror=True)
        # Recovered Normal ingredients are inserted from the return belt.
        add("bulk-inserter", center_x - 1, 9.5, direction=8, mirror=True)
        wires.append([requester["entity_number"], 2, assembler["entity_number"], 2])

    for center_x, quality in high_specs:
        add(
            "assembling-machine-3",
            center_x,
            5.5,
            recipe="crusher",
            recipe_quality=quality,
            **({} if quality == "legendary" else {"items": MODULE_ITEMS}),
        )
        add("steel-chest", center_x - 1, 8.5)
        add("bulk-inserter", center_x - 1, 7.5, direction=8, mirror=True)
        add("bulk-inserter", center_x - 1, 3.5, direction=8, mirror=True)
        # Sorter branch -> steel buffer.
        add("bulk-inserter", center_x - 1, 9.5, direction=8, mirror=True)

    # Shared product belt for all eight assemblers.
    for value in range(26):
        belt(value + 0.5, 2.5, 4)

    # Proven east-facing Legendary extraction geometry.
    add(
        "turbo-splitter",
        26.5,
        2,
        direction=4,
        filter={"quality": "legendary", "comparator": "="},
        output_priority="left",
    )
    belt(27.5, 1.5, 4)
    add("bulk-inserter", 28.5, 1.5, direction=12)
    add("passive-provider-chest", 29.5, 1.5)

    # Normal-through-Epic product queue follows the outer perimeter to the
    # recycler input, avoiding every machine and sorter branch.
    belt(27.5, 2.5, 4)
    belt(28.5, 2.5, 4)
    belt(29.5, 2.5, 4)
    belt(30.5, 2.5, 8)
    for y in [value + 0.5 for value in range(3, 19)]:
        belt(30.5, y, 8)
    belt(30.5, 19.5, 12)
    for x in [value + 0.5 for value in range(9, 30)]:
        belt(x, 19.5, 12)
    # Turn west -> north at the far-left corner.
    belt(8.5, 19.5, 0)
    for y in (18.5, 17.5, 16.5, 15.5, 14.5):
        belt(8.5, y, 0)
    # Turn north -> east into the recycler input.
    belt(8.5, 13.5, 4)
    belt(9.5, 13.5, 4)
    add("bulk-inserter", 10.5, 13.5, direction=12)

    # Proven recycler core. It ejects directly at (11.5, 12.5).
    add("recycler", 12, 15, items=MODULE_ITEMS)
    belt(11.5, 12.5, 4)

    # Quality-only ladder aligned with the higher-quality steel buffers.
    filter_specs = (
        (12.5, "legendary"),
        (15.5, "epic"),
        (18.5, "rare"),
        (21.5, "uncommon"),
    )
    for x, quality in filter_specs:
        add(
            "turbo-splitter",
            x,
            12,
            direction=4,
            filter={"quality": quality, "comparator": "="},
            output_priority="left",
        )
        branch_x = x + 1
        belt(branch_x, 11.5, 0)
        belt(branch_x, 10.5, 0)
        # The branch-loading inserter at y=9.5 was created with its cell.
        belt(x + 1, 12.5, 4)
        belt(x + 2, 12.5, 4)

    # Normal remainder buffer.
    add("bulk-inserter", 24.5, 12.5, direction=12)
    add("steel-chest", 25.5, 12.5)
    add("bulk-inserter", 25.5, 13.5, direction=0, mirror=True)

    # Return recovered Normal ingredients around the lower-left perimeter and
    # beneath the four requester chests.
    for y in (14.5, 15.5, 16.5, 17.5):
        belt(25.5, y, 8)
    add("turbo-underground-belt", 25.5, 18.5, direction=8, type="input")
    add("turbo-underground-belt", 25.5, 20.5, direction=8, type="output")
    belt(25.5, 21.5, 12)
    for x in [value + 0.5 for value in range(0, 25)]:
        belt(x, 21.5, 12)
    # Turn west -> north at the recovered-Normal return corner.
    belt(-0.5, 21.5, 0)
    for y in (20.5, 19.5, 18.5, 17.5, 16.5, 15.5, 14.5, 13.5, 12.5, 11.5):
        belt(-0.5, y, 0)
    belt(-0.5, 10.5, 4)
    for x in [value + 0.5 for value in range(0, 11)]:
        belt(x, 10.5, 4)

    # Side/edge substations leave every belt corridor extensible.
    substations = [
        add("substation", x, y)
        for x, y in ((3, -1), (19, -1), (3, 14), (19, 16), (29, 8))
    ]
    # Explicit copper-wire graph (pole connector ID 5). This prevents the
    # blueprint from preserving the substations as isolated networks.
    for left, right in ((0, 1), (0, 2), (1, 3), (1, 4)):
        wires.append(
            [
                substations[left]["entity_number"],
                5,
                substations[right]["entity_number"],
                5,
            ]
        )

    # Central logistic/construction coverage, powered by both upper substations.
    add("roboport", 11, -1)

    # Place the complete compacted design inside local chunk coordinates.
    for entity in entities:
        entity["position"]["x"] += 1
        entity["position"]["y"] += 4

    return {
        "blueprint": {
            "item": "blueprint",
            "label": "QUP integrated beta",
            "description": (
                "Integrated Crusher quality upcycler: four Normal AM3s, four "
                "higher tiers, Legendary extraction, recycler, quality sorter, "
                "steel buffers, recovered-Normal return, and power."
            ),
            "icons": [
                {"signal": {"name": "assembling-machine-3"}, "index": 1},
                {"signal": {"name": "crusher"}, "index": 2},
                {"signal": {"name": "recycler"}, "index": 3},
            ],
            "entities": entities,
            "wires": wires,
            "snap-to-grid": {"x": 32, "y": 32},
            "absolute-snapping": True,
            "position-relative-to-grid": {"x": 0, "y": 0},
            "version": bp.TARGET_VERSION,
        }
    }


def validate(data: dict) -> None:
    blueprint = data["blueprint"]
    entities = blueprint["entities"]
    assert [e["entity_number"] for e in entities] == list(range(1, len(entities) + 1))
    assemblers = [e for e in entities if e["name"] == "assembling-machine-3"]
    assert len(assemblers) == 8
    assert [e["recipe_quality"] for e in assemblers] == [
        "normal", "normal", "normal", "normal",
        "legendary", "epic", "rare", "uncommon",
    ]
    assert all(e["recipe"] == "crusher" for e in assemblers)
    assert sum(e["name"] == "requester-chest" for e in entities) == 4
    assert sum(e["name"] == "steel-chest" for e in entities) == 5
    assert sum(e["name"] == "recycler" for e in entities) == 1
    assert sum(e["name"] == "passive-provider-chest" for e in entities) == 1
    assert sum(e["name"] == "substation" for e in entities) == 5
    assert sum(e["name"] == "roboport" for e in entities) == 1
    assert sum(e["name"] == "turbo-underground-belt" for e in entities) == 2
    splitters = [e for e in entities if e["name"] == "turbo-splitter"]
    assert len(splitters) == 5
    assert all("name" not in e["filter"] for e in splitters)
    assert len(blueprint["wires"]) == 8
    assert sum(wire[1] == wire[3] == 5 for wire in blueprint["wires"]) == 4
    requesters = [e for e in entities if e["name"] == "requester-chest"]
    assert all(e["control_behavior"]["read_contents"] is False for e in requesters)
    assert all(e["request_filters"]["request_from_buffers"] is True for e in requesters)
    legendary = next(e for e in assemblers if e["recipe_quality"] == "legendary")
    assert "items" not in legendary
    assert "parameter-" not in json.dumps(blueprint)
    assert blueprint["snap-to-grid"] == {"x": 32, "y": 32}
    assert blueprint["absolute-snapping"] is True
    assert blueprint["position-relative-to-grid"] == {"x": 0, "y": 0}
    centers = [(e["position"]["x"], e["position"]["y"]) for e in entities]
    assert len(centers) == len(set(centers))
    footprints = {
        "assembling-machine-3": (3, 3),
        "bulk-inserter": (1, 1),
        "passive-provider-chest": (1, 1),
        "recycler": (4, 4),
        "requester-chest": (1, 1),
        "roboport": (4, 4),
        "steel-chest": (1, 1),
        "substation": (2, 2),
        "turbo-splitter": (1, 2),
        "turbo-transport-belt": (1, 1),
        "turbo-underground-belt": (1, 1),
    }
    bounds = []
    for entity in entities:
        width, height = footprints[entity["name"]]
        x, y = entity["position"]["x"], entity["position"]["y"]
        bounds.append((x - width / 2, y - height / 2, x + width / 2, y + height / 2))
    assert min(bound[0] for bound in bounds) >= 0
    assert min(bound[1] for bound in bounds) >= 0
    assert max(bound[2] for bound in bounds) <= 32
    assert max(bound[3] for bound in bounds) <= 32


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
