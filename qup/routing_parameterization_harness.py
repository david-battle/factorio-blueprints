"""Generate the concrete Crusher routing-parameterization test artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_blueprint as base


INGREDIENTS = (
    ("electric-engine-unit", 10),
    ("steel-plate", 10),
    ("low-density-structure", 20),
)


def build_blueprint() -> dict:
    data = base.build_blueprint()
    blueprint = data["blueprint"]
    blueprint["label"] = "QUP routing parameterization gate"
    blueprint["description"] = (
        "Development gate: concrete Crusher requester settings plus five "
        "recipe-agnostic quality-only splitter filters."
    )

    requester = next(
        entity for entity in blueprint["entities"] if entity["name"] == "requester-chest"
    )
    requester["request_filters"] = {
        "sections": [
            {
                "index": 1,
                "filters": [
                    {
                        "index": index,
                        "name": name,
                        "quality": "normal",
                        "comparator": "=",
                        "count": count * 2,
                    }
                    for index, (name, count) in enumerate(INGREDIENTS, start=1)
                ],
            }
        ]
    }

    splitters = [
        entity for entity in blueprint["entities"] if entity["name"] == "turbo-splitter"
    ]
    for splitter, quality in zip(splitters, base.QUALITIES, strict=True):
        splitter["filter"] = {
            "quality": quality,
            "comparator": "=",
        }
        splitter["output_priority"] = "left"
    return data


def validate(data: dict) -> None:
    base.validate(base.build_blueprint())
    blueprint = data["blueprint"]
    assert "parameters" not in blueprint
    assert len(blueprint["entities"]) == 16
    assert all(
        entity.get("recipe") == "crusher"
        for entity in blueprint["entities"]
        if entity["name"] == "assembling-machine-3"
    )
    encoded = json.dumps(blueprint)
    for name, _count in INGREDIENTS:
        assert name in encoded
    assert "parameter-" not in encoded
    splitter_filters = [
        entity["filter"]
        for entity in blueprint["entities"]
        if entity["name"] == "turbo-splitter"
    ]
    assert splitter_filters == [
        {"quality": quality, "comparator": "="} for quality in base.QUALITIES
    ]
    assert all("name" not in item for item in splitter_filters)


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
