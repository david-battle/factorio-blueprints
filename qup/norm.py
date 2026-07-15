"""Generate the four-cell QUP Normal production bank test."""

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

    for center_x in (2.5, 5.5, 8.5, 11.5):
        assembler = add(
            "assembling-machine-3",
            center_x,
            3.5,
            recipe="crusher",
            recipe_quality="normal",
            control_behavior={"read_ingredients": True},
            items=MODULE_ITEMS,
        )
        requester = add(
            "requester-chest",
            center_x - 1,
            6.5,
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
        add("bulk-inserter", center_x - 1, 5.5, direction=8, mirror=True)
        add("bulk-inserter", center_x - 1, 1.5, direction=8, mirror=True)
        wires.append([requester["entity_number"], 2, assembler["entity_number"], 2])

    for x in [value + 0.5 for value in range(14)]:
        add("turbo-transport-belt", x, 0.5, direction=4)

    return {
        "blueprint": {
            "item": "blueprint",
            "label": "QUP Normal bank",
            "description": (
                "Four proven Normal Crusher cells with isolated recipe-driven "
                "requesters and a shared eastbound turbo output belt."
            ),
            "icons": [
                {"signal": {"name": "assembling-machine-3"}, "index": 1},
                {"signal": {"name": "crusher"}, "index": 2},
            ],
            "entities": entities,
            "wires": wires,
            "version": bp.TARGET_VERSION,
        }
    }


def validate(data: dict) -> None:
    blueprint = data["blueprint"]
    entities = blueprint["entities"]
    assert len(entities) == 30
    assert [entity["entity_number"] for entity in entities] == list(range(1, 31))
    assert sum(e["name"] == "assembling-machine-3" for e in entities) == 4
    assert sum(e["name"] == "requester-chest" for e in entities) == 4
    assert sum(e["name"] == "bulk-inserter" for e in entities) == 8
    assert sum(e["name"] == "turbo-transport-belt" for e in entities) == 14
    assemblers = [e for e in entities if e["name"] == "assembling-machine-3"]
    requesters = [e for e in entities if e["name"] == "requester-chest"]
    inserters = [e for e in entities if e["name"] == "bulk-inserter"]
    assert all(e["recipe"] == "crusher" for e in assemblers)
    assert all(e["recipe_quality"] == "normal" for e in assemblers)
    assert all(e["control_behavior"] == {"read_ingredients": True} for e in assemblers)
    assert all(len(e["items"][0]["items"]["in_inventory"]) == 4 for e in assemblers)
    assert all(e["control_behavior"]["read_contents"] is False for e in requesters)
    assert all(e["control_behavior"]["set_requests"] is True for e in requesters)
    assert all(e["request_filters"]["request_from_buffers"] is True for e in requesters)
    assert [e["position"]["x"] for e in assemblers] == [2.5, 5.5, 8.5, 11.5]
    assert all(e["direction"] == 8 and e["mirror"] is True for e in inserters)
    assert len(blueprint["wires"]) == 4
    assert len({tuple(wire) for wire in blueprint["wires"]}) == 4
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
