"""Generate the isolated QUP Normal assembler cell test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_blueprint as bp


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
        recipe_quality="normal",
        control_behavior={"read_ingredients": True},
        items=[
            {
                "id": {"name": "quality-module-3"},
                "items": {
                    "in_inventory": [
                        {"inventory": 4, "stack": stack} for stack in range(4)
                    ]
                },
            }
        ],
    )
    requester = add(
        "requester-chest",
        1.5,
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
    add("bulk-inserter", 1.5, 5.5, direction=8, mirror=True)
    add("bulk-inserter", 1.5, 1.5, direction=8, mirror=True)
    for x in (1.5, 2.5, 3.5):
        add("turbo-transport-belt", x, 0.5, direction=4)

    return {
        "blueprint": {
            "item": "blueprint",
            "label": "QUP normal cell",
            "description": (
                "Isolated flow test: wired recipe-driven requester -> input "
                "bulk inserter -> Normal AM3 -> output bulk inserter -> turbo belt."
            ),
            "icons": [
                {"signal": {"name": "assembling-machine-3"}, "index": 1},
                {"signal": {"name": "crusher"}, "index": 2},
            ],
            "entities": entities,
            "wires": [
                [assembler["entity_number"], 2, requester["entity_number"], 2]
            ],
            "version": bp.TARGET_VERSION,
        }
    }


def validate(data: dict) -> None:
    blueprint = data["blueprint"]
    entities = blueprint["entities"]
    assert len(entities) == 7
    assert [entity["entity_number"] for entity in entities] == list(range(1, 8))
    assert [entity["name"] for entity in entities].count("bulk-inserter") == 2
    assert [entity["name"] for entity in entities].count("turbo-transport-belt") == 3
    assert entities[0]["recipe"] == "crusher"
    assert entities[0]["control_behavior"] == {"read_ingredients": True}
    assert len(entities[0]["items"][0]["items"]["in_inventory"]) == 4
    assert entities[1]["control_behavior"]["read_contents"] is False
    assert entities[1]["control_behavior"]["set_requests"] is True
    assert entities[1]["request_filters"]["request_from_buffers"] is True
    assert entities[2]["direction"] == entities[3]["direction"] == 8
    assert entities[2]["mirror"] is entities[3]["mirror"] is True
    assert blueprint["wires"] == [[1, 2, 2, 2]]
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
