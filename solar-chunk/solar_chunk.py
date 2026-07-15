#!/usr/bin/env python3
"""Search, validate, and export one-chunk Factorio solar layouts.

Geometry uses twice-tile integer coordinates so boundary decisions do not
depend on floats.
"""

from __future__ import annotations

import argparse
import base64
import json
import zlib
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Iterator, Sequence


# ---------------------------------------------------------------------------
# FACTORIO-SPECIFIC CONFIGURATION
#
# "documented" means supported by the official general documentation cited in
# SPEC.md.  "assumed" means NOT verified against effective Space Age 2.1.11
# prototypes/engine behavior.  An optimality claim is prohibited while any
# value affecting the result remains assumed.
# ---------------------------------------------------------------------------

FACTORIO_VERSION = "2.1.11"
# Factorio packs major, minor, patch, and build into four unsigned 16-bit words.
BLUEPRINT_VERSION = (2 << 48) | (1 << 32) | (11 << 16)
CHUNK_TILES = 32
CHUNK_STATUS = "documented"
# Keep entity coordinates in the local chunk interval [0, 32). Factorio's
# global chunk boundaries are multiples of 32, so absolute snapping must use a
# zero offset. A (16, 16) offset puts these bounds half a chunk off the world
# grid and makes the layout straddle four chunks.
BLUEPRINT_CENTER_OFFSET = 0
ABSOLUTE_GRID_OFFSET = {"x": 0, "y": 0}
QUALITY = "normal"
QUALITY_STATUS = "project-choice"
COVERAGE_RULE = "nominal-footprint-intersects-closed-supply-square"
COVERAGE_RULE_STATUS = "assumed"
WIRE_RULE = "euclidean-center-distance-at-most-minimum-endpoint-reach"
WIRE_RULE_STATUS = "assumed"


@dataclass(frozen=True)
class Prototype:
    name: str
    kind: str
    width: int
    height: int
    supply_distance2: int | None = None
    wire_distance2: int | None = None
    geometry_status: str = "assumed"
    electrical_status: str = "not-applicable"


PROTOTYPES: dict[str, Prototype] = {
    "solar-panel": Prototype("solar-panel", "solar-panel", 3, 3),
    "small-electric-pole": Prototype(
        "small-electric-pole", "electric-pole", 1, 1, 5, 15,
        electrical_status="assumed",
    ),
    "medium-electric-pole": Prototype(
        "medium-electric-pole", "electric-pole", 1, 1, 7, 18,
        electrical_status="assumed",
    ),
    "big-electric-pole": Prototype(
        "big-electric-pole", "electric-pole", 2, 2, 4, 60,
        electrical_status="assumed-untrusted",
    ),
    "substation": Prototype(
        "substation", "electric-pole", 2, 2, 18, 36,
        electrical_status="assumed",
    ),
}


@dataclass(frozen=True)
class Entity:
    entity_id: int
    prototype: str
    left: int
    top: int

    @property
    def spec(self) -> Prototype:
        return PROTOTYPES[self.prototype]

    @property
    def right(self) -> int:
        return self.left + self.spec.width

    @property
    def bottom(self) -> int:
        return self.top + self.spec.height

    @property
    def center2(self) -> tuple[int, int]:
        return 2 * self.left + self.spec.width, 2 * self.top + self.spec.height

    @property
    def bounds2(self) -> tuple[int, int, int, int]:
        return 2 * self.left, 2 * self.top, 2 * self.right, 2 * self.bottom

    @property
    def kind(self) -> str:
        return self.spec.kind


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]
    wire_edges: tuple[tuple[int, int], ...]
    supplied_by: tuple[tuple[int, tuple[int, ...]], ...]


@dataclass(frozen=True)
class SearchResult:
    entities: tuple[Entity, ...]
    validation: ValidationResult
    search_status: str
    candidates_checked: int
    method: str

    @property
    def panel_count(self) -> int:
        return sum(entity.kind == "solar-panel" for entity in self.entities)

    @property
    def pole_count(self) -> int:
        return sum(entity.kind == "electric-pole" for entity in self.entities)


def in_bounds(entity: Entity) -> bool:
    return (
        entity.left >= 0
        and entity.top >= 0
        and entity.right <= CHUNK_TILES
        and entity.bottom <= CHUNK_TILES
    )


def overlaps(first: Entity, second: Entity) -> bool:
    """Return whether nominal half-open tile footprints overlap."""
    return not (
        first.right <= second.left
        or second.right <= first.left
        or first.bottom <= second.top
        or second.bottom <= first.top
    )


def pole_supplies(pole: Entity, panel: Entity) -> bool:
    distance = pole.spec.supply_distance2
    if pole.kind != "electric-pole" or panel.kind != "solar-panel" or distance is None:
        return False
    cx, cy = pole.center2
    left, top, right, bottom = panel.bounds2
    # Assumed rule: closed supply square intersects the closed nominal panel box.
    return not (
        right < cx - distance
        or left > cx + distance
        or bottom < cy - distance
        or top > cy + distance
    )


def poles_can_connect(first: Entity, second: Entity) -> bool:
    if first.kind != "electric-pole" or second.kind != "electric-pole":
        return False
    if first.spec.wire_distance2 is None or second.spec.wire_distance2 is None:
        return False
    reach2 = min(first.spec.wire_distance2, second.spec.wire_distance2)
    ax, ay = first.center2
    bx, by = second.center2
    return (ax - bx) ** 2 + (ay - by) ** 2 <= reach2**2


def substation_supply_in_bounds(entity: Entity) -> bool:
    """Return whether a substation's entire electric supply square is in-chunk."""
    if entity.prototype != "substation":
        return True
    distance = entity.spec.supply_distance2
    assert distance is not None
    center_x, center_y = entity.center2
    chunk_size2 = 2 * CHUNK_TILES
    return (
        center_x - distance >= 0
        and center_y - distance >= 0
        and center_x + distance <= chunk_size2
        and center_y + distance <= chunk_size2
    )


def validate(entities: Sequence[Entity]) -> ValidationResult:
    errors: list[str] = []
    ids = [entity.entity_id for entity in entities]
    if len(ids) != len(set(ids)):
        errors.append("entity IDs are not unique")

    known_entities: list[Entity] = []
    for entity in entities:
        if entity.prototype not in PROTOTYPES:
            errors.append(f"entity {entity.entity_id} has unknown prototype")
            continue
        known_entities.append(entity)
        if not in_bounds(entity):
            errors.append(f"entity {entity.entity_id} is outside the chunk")
        if not substation_supply_in_bounds(entity):
            errors.append(
                f"substation {entity.entity_id} supply area extends outside the chunk"
            )

    for index, first in enumerate(known_entities):
        for second in known_entities[index + 1 :]:
            if overlaps(first, second):
                errors.append(f"entities {first.entity_id} and {second.entity_id} overlap")

    panels = [entity for entity in known_entities if entity.kind == "solar-panel"]
    poles = [entity for entity in known_entities if entity.kind == "electric-pole"]
    supplied: list[tuple[int, tuple[int, ...]]] = []
    for panel in panels:
        suppliers = tuple(pole.entity_id for pole in poles if pole_supplies(pole, panel))
        supplied.append((panel.entity_id, suppliers))
        if not suppliers:
            errors.append(f"solar panel {panel.entity_id} is not supplied")

    edges = tuple(
        (first.entity_id, second.entity_id)
        for index, first in enumerate(poles)
        for second in poles[index + 1 :]
        if poles_can_connect(first, second)
    )
    if panels and not poles:
        errors.append("layout has panels but no electric poles")
    if poles:
        adjacency = {pole.entity_id: set() for pole in poles}
        for first_id, second_id in edges:
            adjacency[first_id].add(second_id)
            adjacency[second_id].add(first_id)
        visited: set[int] = set()
        pending = [poles[0].entity_id]
        while pending:
            current = pending.pop()
            if current not in visited:
                visited.add(current)
                pending.extend(adjacency[current] - visited)
        if len(visited) != len(poles):
            errors.append("electric poles do not form one connected network")

    return ValidationResult(not errors, tuple(errors), edges, tuple(supplied))


def _axis_lattice(count: int, size: int, shift: int) -> tuple[int, ...] | None:
    """Evenly distribute top-left positions, rounded to legal tile locations."""
    positions = []
    for index in range(count):
        center = (index + 0.5) * CHUNK_TILES / count + shift
        left = round(center - size / 2)
        left = max(0, min(CHUNK_TILES - size, left))
        positions.append(left)
    result = tuple(sorted(set(positions)))
    return result if len(result) == count else None


def _pole_lattices(prototype: str) -> Iterator[tuple[Entity, ...]]:
    spec = PROTOTYPES[prototype]
    seen: set[tuple[tuple[int, int], ...]] = set()
    for columns, rows in product(range(1, 5), repeat=2):
        for shift_x, shift_y in product(range(-3, 4), repeat=2):
            xs = _axis_lattice(columns, spec.width, shift_x)
            ys = _axis_lattice(rows, spec.height, shift_y)
            if xs is None or ys is None:
                continue
            points = tuple(product(xs, ys))
            if points in seen:
                continue
            seen.add(points)
            yield tuple(
                Entity(index + 1, prototype, left, top)
                for index, (left, top) in enumerate(points)
            )


def _panel_grid(poles: Sequence[Entity], offset_x: int, offset_y: int) -> tuple[Entity, ...]:
    panels: list[Entity] = []
    next_id = len(poles) + 1
    for top in range(offset_y, CHUNK_TILES - 2, 3):
        for left in range(offset_x, CHUNK_TILES - 2, 3):
            panel = Entity(next_id, "solar-panel", left, top)
            if any(overlaps(panel, pole) for pole in poles):
                continue
            if not any(pole_supplies(pole, panel) for pole in poles):
                continue
            panels.append(panel)
            next_id += 1
    return tuple(panels)


# A reflection-symmetric packing around substations whose 18x18 supply squares
# touch the four chunk corners.  Unlike _panel_grid, central rows are staggered
# where needed to recover space around the 2x2 substation footprints.
SYMMETRIC_PANEL_POSITIONS = (
    (0,0),(3,0),(7,0),(10,0),(13,0),(16,0),(19,0),(22,0),(26,0),(29,0),
    (3,3),(6,3),(10,3),(19,3),(23,3),(26,3),(0,4),(13,4),(16,4),(29,4),
    (0,7),(5,7),(10,7),(13,7),(16,7),(19,7),(24,7),(29,7),
    (0,10),(3,10),(7,10),(10,10),(13,10),(16,10),(19,10),(22,10),(26,10),(29,10),
    (0,13),(3,13),(6,13),(9,13),(12,13),(17,13),(20,13),(23,13),(26,13),(29,13),
    (0,16),(3,16),(6,16),(9,16),(12,16),(17,16),(20,16),(23,16),(26,16),(29,16),
    (0,19),(3,19),(7,19),(10,19),(13,19),(16,19),(19,19),(22,19),(26,19),(29,19),
    (0,22),(5,22),(10,22),(13,22),(16,22),(19,22),(24,22),(29,22),
    (0,25),(13,25),(16,25),(29,25),(3,26),(6,26),(10,26),(19,26),(23,26),(26,26),
    (0,29),(3,29),(7,29),(10,29),(13,29),(16,29),(19,29),(22,29),(26,29),(29,29),
)


def _symmetric_substation_candidate() -> tuple[Entity, ...]:
    substations = tuple(
        Entity(index + 1, "substation", left, top)
        for index, (left, top) in enumerate(((8, 8), (22, 8), (8, 22), (22, 22)))
    )
    panels = tuple(
        Entity(index + 5, "solar-panel", left, top)
        for index, (left, top) in enumerate(SYMMETRIC_PANEL_POSITIONS)
    )
    return substations + panels


def search() -> SearchResult:
    """Return the best candidate in a bounded heuristic family, not a proof."""
    symmetric_entities = _symmetric_substation_candidate()
    symmetric_validation = validate(symmetric_entities)
    if not symmetric_validation.valid:
        raise RuntimeError("built-in symmetric candidate is invalid")
    checked = 1
    best: SearchResult | None = SearchResult(
        symmetric_entities,
        symmetric_validation,
        "best-found-not-proven-optimal",
        checked,
        "accumulator-space-optimized reflection-symmetric four-substation packing plus regular pole lattices",
    )
    for prototype in (
        "small-electric-pole",
        "medium-electric-pole",
        "big-electric-pole",
        "substation",
    ):
        for poles in _pole_lattices(prototype):
            # Reject disconnected pole sets before trying panel offsets.
            if not validate(poles).valid:
                continue
            for offset_x, offset_y in product(range(3), repeat=2):
                panels = _panel_grid(poles, offset_x, offset_y)
                entities = tuple(poles) + panels
                result = validate(entities)
                checked += 1
                if not result.valid:
                    continue
                candidate = SearchResult(
                    entities,
                    result,
                    "best-found-not-proven-optimal",
                    checked,
                    "regular pole lattices (1-4 per axis, shifted -3..3) and 3x3 panel grids",
                )
                score = (candidate.panel_count, -candidate.pole_count)
                if best is None or score > (best.panel_count, -best.pole_count):
                    best = candidate
    if best is None:
        raise RuntimeError("search found no valid layout")
    return SearchResult(
        best.entities, best.validation, best.search_status, checked, best.method
    )


def render_ascii(entities: Sequence[Entity]) -> str:
    grid = [["." for _ in range(CHUNK_TILES)] for _ in range(CHUNK_TILES)]
    symbols = {
        "solar-panel": "S",
        "small-electric-pole": "s",
        "medium-electric-pole": "m",
        "big-electric-pole": "B",
        "substation": "U",
    }
    for entity in entities:
        symbol = symbols[entity.prototype]
        for y in range(entity.top, entity.bottom):
            for x in range(entity.left, entity.right):
                grid[y][x] = symbol
    ruler = "    " + "".join(str(index // 10 or " ")[-1] for index in range(CHUNK_TILES))
    ruler2 = "    " + "".join(str(index % 10) for index in range(CHUNK_TILES))
    rows = [ruler, ruler2]
    rows.extend(f"{index:02d}  {''.join(row)}" for index, row in enumerate(grid))
    rows.append("Legend: S=solar panel, s=small pole, m=medium pole, B=big pole, U=substation, .=empty")
    return "\n".join(rows) + "\n"


def normalized_json(result: SearchResult) -> str:
    supplied = dict(result.validation.supplied_by)
    neighbours: dict[int, list[int]] = {entity.entity_id: [] for entity in result.entities}
    for first_id, second_id in result.validation.wire_edges:
        neighbours[first_id].append(second_id)
        neighbours[second_id].append(first_id)
    document = {
        "format": "solar-chunk-layout-v1",
        "target_factorio_version": FACTORIO_VERSION,
        "chunk": {"width": CHUNK_TILES, "height": CHUNK_TILES, "status": CHUNK_STATUS},
        "coordinate_system": {"origin": "northwest", "x_positive": "east", "y_positive": "south"},
        "factorio_configuration": {
            "quality": {"value": QUALITY, "status": QUALITY_STATUS},
            "coverage_rule": {"value": COVERAGE_RULE, "status": COVERAGE_RULE_STATUS},
            "wire_rule": {"value": WIRE_RULE, "status": WIRE_RULE_STATUS},
            "prototypes": [asdict(PROTOTYPES[name]) for name in sorted(PROTOTYPES)],
        },
        "search": {
            "status": result.search_status,
            "method": result.method,
            "candidates_checked": result.candidates_checked,
            "panel_count": result.panel_count,
            "pole_count": result.pole_count,
        },
        "validation": {"valid": result.validation.valid, "errors": list(result.validation.errors)},
        "entities": [
            {
                "id": entity.entity_id,
                "prototype": entity.prototype,
                "kind": entity.kind,
                "quality": QUALITY,
                "top_left": {"x": entity.left, "y": entity.top},
                "center": {"x": entity.center2[0] / 2, "y": entity.center2[1] / 2},
                "nominal_bounds": {
                    "left": entity.left,
                    "top": entity.top,
                    "right": entity.right,
                    "bottom": entity.bottom,
                },
                "supplied_by": list(supplied.get(entity.entity_id, ())),
                "copper_neighbours": sorted(neighbours[entity.entity_id]),
            }
            for entity in sorted(result.entities, key=lambda item: item.entity_id)
        ],
        "wire_edges": [list(edge) for edge in result.validation.wire_edges],
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def blueprint_json(result: SearchResult) -> dict:
    """Build a Factorio 2.1.11 blueprint document for *result*."""
    if not result.validation.valid:
        raise ValueError("cannot export an invalid layout")
    return {
        "blueprint": {
            "item": "blueprint",
            "label": "32x32 solar chunk",
            "version": BLUEPRINT_VERSION,
            "snap-to-grid": {"x": CHUNK_TILES, "y": CHUNK_TILES},
            "absolute-snapping": True,
            "position-relative-to-grid": dict(ABSOLUTE_GRID_OFFSET),
            "entities": [
                {
                    "entity_number": entity.entity_id,
                    "name": entity.prototype,
                    "position": {
                        "x": entity.center2[0] / 2 - BLUEPRINT_CENTER_OFFSET,
                        "y": entity.center2[1] / 2 - BLUEPRINT_CENTER_OFFSET,
                    },
                    "quality": QUALITY,
                }
                for entity in sorted(result.entities, key=lambda item: item.entity_id)
            ],
        }
    }


def encode_blueprint(document: dict) -> str:
    """Encode a blueprint document in Factorio's ``0`` + base64(zlib(JSON)) format."""
    payload = json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "0" + base64.b64encode(zlib.compress(payload, level=9)).decode("ascii")


def decode_blueprint(value: str) -> dict:
    """Decode a Factorio blueprint string and return its JSON document."""
    if not value or value[0] != "0":
        raise ValueError("unsupported Factorio blueprint string version")
    try:
        payload = zlib.decompress(base64.b64decode(value[1:], validate=True))
        document = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeError, zlib.error, json.JSONDecodeError) as error:
        raise ValueError("invalid Factorio blueprint string") from error
    if not isinstance(document, dict) or "blueprint" not in document:
        raise ValueError("blueprint string does not contain a blueprint")
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="write normalized layout JSON")
    parser.add_argument("--ascii", type=Path, help="write ASCII grid")
    parser.add_argument("--blueprint", type=Path, help="write Factorio blueprint string")
    args = parser.parse_args(argv)

    result = search()
    ascii_grid = render_ascii(result.entities)
    json_text = normalized_json(result)
    blueprint_text = encode_blueprint(blueprint_json(result)) + "\n"
    if args.ascii:
        args.ascii.write_text(ascii_grid, encoding="utf-8")
    else:
        print(ascii_grid, end="")
    if args.json:
        args.json.write_text(json_text, encoding="utf-8")
    else:
        print(json_text, end="")
    if args.blueprint:
        args.blueprint.write_text(blueprint_text, encoding="ascii")
    print(
        f"Result: {result.panel_count} panels, {result.pole_count} poles; "
        f"{result.search_status}; {result.candidates_checked} candidates checked",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
