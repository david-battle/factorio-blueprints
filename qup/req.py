"""Generate the final recipe-driven requester validation blueprint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_blueprint as base


def build_blueprint() -> dict:
    data = base.build_blueprint()
    blueprint = data["blueprint"]
    blueprint["label"] = "QUP requester gate"
    blueprint["description"] = (
        "Parameterize Crusher to Cargo bay. The wired requester obtains its "
        "requests from the Normal assembler's recipe ingredients."
    )

    chest = next(
        entity for entity in blueprint["entities"] if entity["name"] == "requester-chest"
    )
    assembler = next(
        entity
        for entity in blueprint["entities"]
        if entity["name"] == "assembling-machine-3"
        and entity["recipe_quality"] == "normal"
    )
    chest["control_behavior"] = {
        "set_requests": True,
        "circuit_condition_enabled": False,
    }
    chest["request_filters"] = {"sections": [{"index": 1}]}
    assembler["control_behavior"] = {"read_ingredients": True}
    blueprint["wires"] = [
        [chest["entity_number"], 2, assembler["entity_number"], 2]
    ]
    return data


def validate(data: dict) -> None:
    blueprint = data["blueprint"]
    assert "parameters" not in blueprint
    assert "parameter-" not in json.dumps(blueprint)
    chest = next(
        entity for entity in blueprint["entities"] if entity["name"] == "requester-chest"
    )
    assembler = next(
        entity
        for entity in blueprint["entities"]
        if entity["name"] == "assembling-machine-3"
        and entity["recipe_quality"] == "normal"
    )
    assert chest["control_behavior"] == {
        "set_requests": True,
        "circuit_condition_enabled": False,
    }
    assert chest["request_filters"] == {"sections": [{"index": 1}]}
    assert assembler["control_behavior"] == {"read_ingredients": True}
    assert blueprint["wires"] == [
        [chest["entity_number"], 2, assembler["entity_number"], 2]
    ]
    base.validate({
        "blueprint": {
            **blueprint,
            "entities": [
                {
                    key: value
                    for key, value in entity.items()
                    if key not in ("control_behavior", "request_filters")
                }
                for entity in blueprint["entities"]
            ],
            **({} if "wires" not in blueprint else {}),
        }
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    data = build_blueprint()
    validate(data)
    value = base.encode(data)
    validate(base.decode(value))
    args.output.write_text(value + "\n", encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
