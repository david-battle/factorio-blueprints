"""Generate and validate the one-chunk QUP parameterization harness."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import zlib


TARGET_VERSION = 562954249109504  # 2.1.11.0
QUALITIES = ("normal", "uncommon", "rare", "epic", "legendary")


def _entity(number: int, name: str, x: float, y: float, **extra: object) -> dict:
    result = {"entity_number": number, "name": name, "position": {"x": x, "y": y}}
    result.update(extra)
    return result


def build_blueprint() -> dict:
    entities: list[dict] = []
    number = 1

    # Corner markers make the nominal design bounds exactly one 32x32 chunk.
    for x, y in ((0.5, 0.5), (31.5, 0.5), (0.5, 31.5), (31.5, 31.5)):
        entities.append(_entity(number, "stone-wall", x, y))
        number += 1

    for index, quality in enumerate(QUALITIES):
        entities.append(
            _entity(
                number,
                "assembling-machine-3",
                5.5 + 4 * index,
                5.5,
                recipe="crusher",
                recipe_quality=quality,
            )
        )
        number += 1

    entities.append(
        _entity(
            number,
            "requester-chest",
            5.5,
            9.5,
        )
    )
    number += 1

    for index in range(5):
        entities.append(
            _entity(
                number,
                "turbo-splitter",
                5 + 4 * index,
                13.5,
                direction=4,
            )
        )
        number += 1

    entities.append(_entity(number, "substation", 16, 18))

    return {
        "blueprint": {
            "item": "blueprint",
            "label": "QUP parameterization harness",
            "description": (
                "One-chunk Factorio 2.1.11 test. Replace the crusher recipe with cargo-bay, "
                "place it, then make and export a NEW blueprint from the placed entities."
            ),
            "icons": [
                {"signal": {"name": "assembling-machine-3"}, "index": 1},
                {"signal": {"name": "crusher"}, "index": 2},
            ],
            "entities": entities,
            "snap-to-grid": {"x": 32, "y": 32},
            "absolute-snapping": True,
            "position-relative-to-grid": {"x": 0, "y": 0},
            "version": TARGET_VERSION,
        }
    }


def encode(data: dict) -> str:
    compact = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "0" + base64.b64encode(zlib.compress(compact, level=9)).decode("ascii")


def decode(value: str) -> dict:
    if not value.startswith("0"):
        raise ValueError("blueprint string must start with format byte 0")
    return json.loads(zlib.decompress(base64.b64decode(value[1:])).decode("utf-8"))


def validate(data: dict) -> None:
    blueprint = data["blueprint"]
    assert blueprint["version"] == TARGET_VERSION
    assert blueprint["snap-to-grid"] == {"x": 32, "y": 32}
    assert blueprint["absolute-snapping"] is True
    assert blueprint["position-relative-to-grid"] == {"x": 0, "y": 0}
    entities = blueprint["entities"]
    assert len(entities) == 16
    assert [entity["entity_number"] for entity in entities] == list(range(1, 17))
    assert sum(entity["name"] == "assembling-machine-3" for entity in entities) == 5
    assert sum(entity["name"] == "turbo-splitter" for entity in entities) == 5
    assert sum(entity["name"] == "requester-chest" for entity in entities) == 1
    assert {entity.get("recipe_quality") for entity in entities if "recipe" in entity} == set(QUALITIES)
    assert "parameters" not in blueprint
    assert {entity.get("recipe") for entity in entities if "recipe" in entity} == {
        "crusher"
    }
    assert "parameter-" not in json.dumps(blueprint)

    footprints = {
        "stone-wall": (1, 1),
        "assembling-machine-3": (3, 3),
        "requester-chest": (1, 1),
        "turbo-splitter": (2, 1),
        "substation": (2, 2),
    }
    bounds = []
    for entity in entities:
        width, height = footprints[entity["name"]]
        # The splitters face east, so their nominal 2x1 footprint is unrotated.
        x, y = entity["position"]["x"], entity["position"]["y"]
        bounds.append((x - width / 2, y - height / 2, x + width / 2, y + height / 2))
    assert min(bound[0] for bound in bounds) == 0
    assert min(bound[1] for bound in bounds) == 0
    assert max(bound[2] for bound in bounds) == 32
    assert max(bound[3] for bound in bounds) == 32
    assert all(0 <= coordinate <= 32 for bound in bounds for coordinate in bound)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    data = build_blueprint()
    validate(data)
    value = encode(data)
    validate(decode(value))
    args.output.write_text(value + "\n", encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
