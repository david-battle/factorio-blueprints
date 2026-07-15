"""Expected-flow and discrete-event analysis for the QUP quality up-cycler."""

from __future__ import annotations

import argparse
import heapq
import json
import math
import random
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Iterable


QUALITIES = ("normal", "uncommon", "rare", "epic", "legendary")
DEFAULT_FACTS = Path(__file__).with_name("prototype_facts_2.1.11.json")


@dataclass(frozen=True)
class Scenario:
    recipe: str
    ingredients: dict[str, int]
    recipe_time: float
    recycling_time: float
    assembler_speed: float
    recycler_speed: float
    assembler_quality_chance: float
    recycler_quality_chance: float
    assembler_speed_modifier: float
    recycler_speed_modifier: float
    assembler_counts: tuple[int, int, int, int, int]
    recycling_return_fraction: float

    @property
    def quality_assembler_cycle(self) -> float:
        speed = self.assembler_speed * (1 + self.assembler_speed_modifier)
        return self.recipe_time / speed

    @property
    def legendary_assembler_cycle(self) -> float:
        return self.recipe_time / self.assembler_speed

    @property
    def recycler_cycle(self) -> float:
        speed = self.recycler_speed * (1 + self.recycler_speed_modifier)
        return self.recycling_time / speed

    @property
    def craft_capacities(self) -> tuple[float, ...]:
        cycles = (self.quality_assembler_cycle,) * 4 + (
            self.legendary_assembler_cycle,
        )
        return tuple(count / cycle for count, cycle in zip(self.assembler_counts, cycles))


def load_scenario(path: Path = DEFAULT_FACTS) -> Scenario:
    data = json.loads(path.read_text(encoding="utf-8"))
    module = data["quality_module"]
    slots = module["count_per_machine"]
    quality_chance = slots * module["quality_chance_per_module"]
    speed_modifier = slots * module["speed_modifier_per_module"]
    return Scenario(
        recipe=data["recipe"]["name"],
        ingredients=data["recipe"]["ingredients"],
        recipe_time=data["recipe"]["energy_required"],
        recycling_time=data["recipe"]["recycling_energy_required"],
        assembler_speed=data["assembler"]["crafting_speed"],
        recycler_speed=data["recycler"]["crafting_speed"],
        assembler_quality_chance=quality_chance,
        recycler_quality_chance=quality_chance,
        assembler_speed_modifier=speed_modifier,
        recycler_speed_modifier=speed_modifier,
        assembler_counts=(4, 1, 1, 1, 1),
        recycling_return_fraction=data["recipe"]["recycling_return_fraction"],
    )


def quality_distribution(base: int, chance: float) -> tuple[float, ...]:
    """Return output probabilities for one item starting at quality *base*."""
    if not 0 <= base < len(QUALITIES):
        raise ValueError("base quality index is out of range")
    if not 0 <= chance <= 1:
        raise ValueError("quality chance must be between zero and one")
    result = [0.0] * len(QUALITIES)
    if base == len(QUALITIES) - 1:
        result[base] = 1.0
        return tuple(result)
    result[base] = 1 - chance
    for target in range(base + 1, len(QUALITIES) - 1):
        distance = target - base
        result[target] = chance * 0.9 * (0.1 ** (distance - 1))
    result[-1] = chance * (0.1 ** (len(QUALITIES) - base - 2))
    return tuple(result)


def transform(values: Iterable[float], chance: float) -> list[float]:
    output = [0.0] * len(QUALITIES)
    for base, value in enumerate(values):
        for target, probability in enumerate(quality_distribution(base, chance)):
            output[target] += value * probability
    return output


def expected_flow(scenario: Scenario, recycler_count: int = 1) -> dict:
    """Solve the steady expected flow with finite crafting capacities."""
    capacities = scenario.craft_capacities
    crafts = [capacities[0], 0.0, 0.0, 0.0, 0.0]

    for _ in range(10_000):
        products = transform(crafts, scenario.assembler_quality_chance)
        recyclable = products[:4] + [0.0]
        recovered = transform(recyclable, scenario.recycler_quality_chance)
        recovered = [value * scenario.recycling_return_fraction for value in recovered]
        updated = [capacities[0]] + [
            min(capacities[index], recovered[index]) for index in range(1, 5)
        ]
        if max(abs(a - b) for a, b in zip(crafts, updated)) < 1e-14:
            crafts = updated
            break
        crafts = updated
    else:
        raise RuntimeError("expected-flow iteration did not converge")

    products = transform(crafts, scenario.assembler_quality_chance)
    recyclable = products[:4] + [0.0]
    recovered = transform(recyclable, scenario.recycler_quality_chance)
    recovered = [value * scenario.recycling_return_fraction for value in recovered]
    recycler_input = sum(recyclable)
    recycler_capacity_each = 1 / scenario.recycler_cycle
    recycler_capacity = recycler_count * recycler_capacity_each
    external_sets = max(0.0, crafts[0] - recovered[0])

    return {
        "crafts_per_second": dict(zip(QUALITIES, crafts)),
        "craft_capacity_per_second": dict(zip(QUALITIES, capacities)),
        "assembler_utilization": {
            quality: (craft / capacity if capacity else 0.0)
            for quality, craft, capacity in zip(QUALITIES, crafts, capacities)
        },
        "products_per_second": dict(zip(QUALITIES, products)),
        "recovered_recipe_sets_per_second": dict(zip(QUALITIES, recovered)),
        "external_normal_recipe_sets_per_second": external_sets,
        "external_normal_items_per_second": {
            name: amount * external_sets for name, amount in scenario.ingredients.items()
        },
        "legendary_products_per_second": products[-1],
        "recycler_input_per_second": recycler_input,
        "recycler_capacity_each_per_second": recycler_capacity_each,
        "recycler_count": recycler_count,
        "recycler_utilization": recycler_input / recycler_capacity,
        "minimum_recyclers": math.ceil(recycler_input / recycler_capacity_each),
    }


def _sample_quality(rng: random.Random, base: int, chance: float) -> int:
    if base == len(QUALITIES) - 1 or rng.random() >= chance:
        return base
    quality = base + 1
    while quality < len(QUALITIES) - 1 and rng.random() < 0.1:
        quality += 1
    return quality


def _simulate_once(scenario: Scenario, hours: float, recycler_count: int, seed: int) -> dict:
    rng = random.Random(seed)
    duration = hours * 3600
    events: list[tuple[float, int, str, int]] = []
    sequence = 0
    buffers = [{name: 0 for name in scenario.ingredients} for _ in QUALITIES]
    external = {name: 0 for name in scenario.ingredients}
    craft_counts = [0] * len(QUALITIES)
    product_counts = [0] * len(QUALITIES)
    assembler_busy = [False] * len(QUALITIES)
    recycle_queue: deque[int] = deque()
    recycler_busy = [False] * recycler_count
    recycler_completed = 0
    maximum_queue = 0

    def push(time: float, kind: str, index: int) -> None:
        nonlocal sequence
        sequence += 1
        heapq.heappush(events, (time, sequence, kind, index))

    def consume_normal() -> None:
        for name, amount in scenario.ingredients.items():
            reused = min(amount, buffers[0][name])
            buffers[0][name] -= reused
            external[name] += amount - reused

    def try_start_assembler(quality: int, now: float) -> None:
        if assembler_busy[quality]:
            return
        if all(buffers[quality][name] >= amount for name, amount in scenario.ingredients.items()):
            for name, amount in scenario.ingredients.items():
                buffers[quality][name] -= amount
            assembler_busy[quality] = True
            cycle = scenario.legendary_assembler_cycle if quality == 4 else scenario.quality_assembler_cycle
            push(now + cycle, "craft", quality)

    def try_start_recyclers(now: float) -> None:
        for recycler in range(recycler_count):
            if recycle_queue and not recycler_busy[recycler]:
                product_quality = recycle_queue.popleft()
                recycler_busy[recycler] = True
                # Encode product quality alongside recycler index.
                push(now + scenario.recycler_cycle, "recycle", recycler * 10 + product_quality)

    for _ in range(scenario.assembler_counts[0]):
        consume_normal()
        push(scenario.quality_assembler_cycle, "normal-craft", 0)

    while events:
        now, _, kind, encoded = heapq.heappop(events)
        if now > duration:
            break
        if kind == "normal-craft":
            craft_counts[0] += 1
            quality = _sample_quality(rng, 0, scenario.assembler_quality_chance)
            product_counts[quality] += 1
            if quality < 4:
                recycle_queue.append(quality)
                maximum_queue = max(maximum_queue, len(recycle_queue))
                try_start_recyclers(now)
            consume_normal()
            push(now + scenario.quality_assembler_cycle, "normal-craft", 0)
        elif kind == "craft":
            quality = encoded
            assembler_busy[quality] = False
            craft_counts[quality] += 1
            output_quality = _sample_quality(
                rng,
                quality,
                scenario.assembler_quality_chance if quality < 4 else 0.0,
            )
            product_counts[output_quality] += 1
            if output_quality < 4:
                recycle_queue.append(output_quality)
                maximum_queue = max(maximum_queue, len(recycle_queue))
                try_start_recyclers(now)
            try_start_assembler(quality, now)
        elif kind == "recycle":
            recycler = encoded // 10
            product_quality = encoded % 10
            recycler_busy[recycler] = False
            recycler_completed += 1
            for name, amount in scenario.ingredients.items():
                returned = amount // 4
                if rng.random() < (amount % 4) / 4:
                    returned += 1
                for _ in range(returned):
                    quality = _sample_quality(rng, product_quality, scenario.recycler_quality_chance)
                    buffers[quality][name] += 1
            for quality in range(1, 5):
                try_start_assembler(quality, now)
            try_start_recyclers(now)

    capacities = scenario.craft_capacities
    return {
        "legendary_per_hour": product_counts[4] / hours,
        "crafts_per_second": [count / duration for count in craft_counts],
        "assembler_utilization": [
            count / duration / capacity for count, capacity in zip(craft_counts, capacities)
        ],
        "external_items_per_second": {
            name: count / duration for name, count in external.items()
        },
        "recycler_utilization": recycler_completed * scenario.recycler_cycle / duration / recycler_count,
        "maximum_recycler_queue": maximum_queue,
        "ending_recycler_queue": len(recycle_queue),
    }


def stochastic_flow(
    scenario: Scenario,
    hours: float = 100.0,
    trials: int = 20,
    recycler_count: int = 1,
    seed: int = 2111,
) -> dict:
    runs = [_simulate_once(scenario, hours, recycler_count, seed + trial) for trial in range(trials)]

    def summary(values: Iterable[float]) -> dict[str, float]:
        values = list(values)
        return {"mean": mean(values), "stddev": pstdev(values), "min": min(values), "max": max(values)}

    return {
        "hours_per_trial": hours,
        "trials": trials,
        "seed": seed,
        "recycler_count": recycler_count,
        "legendary_products_per_hour": summary(run["legendary_per_hour"] for run in runs),
        "assembler_utilization": {
            quality: summary(run["assembler_utilization"][index] for run in runs)
            for index, quality in enumerate(QUALITIES)
        },
        "external_items_per_second": {
            name: summary(run["external_items_per_second"][name] for run in runs)
            for name in scenario.ingredients
        },
        "recycler_utilization": summary(run["recycler_utilization"] for run in runs),
        "maximum_recycler_queue": summary(run["maximum_recycler_queue"] for run in runs),
        "ending_recycler_queue": summary(run["ending_recycler_queue"] for run in runs),
    }


def analyze(hours: float, trials: int, recycler_count: int, seed: int) -> dict:
    scenario = load_scenario()
    return {
        "scenario": {
            "recipe": scenario.recipe,
            "ingredients": scenario.ingredients,
            "assembler_counts": dict(zip(QUALITIES, scenario.assembler_counts)),
            "assembler_quality_chance": scenario.assembler_quality_chance,
            "recycler_quality_chance": scenario.recycler_quality_chance,
            "quality_assembler_cycle_seconds": scenario.quality_assembler_cycle,
            "legendary_assembler_cycle_seconds": scenario.legendary_assembler_cycle,
            "recycler_cycle_seconds": scenario.recycler_cycle,
        },
        "expected": expected_flow(scenario, recycler_count),
        "stochastic": stochastic_flow(scenario, hours, trials, recycler_count, seed),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=float, default=100.0, help="simulated hours per stochastic trial")
    parser.add_argument("--trials", type=int, default=20, help="number of stochastic trials")
    parser.add_argument("--recyclers", type=int, default=1, help="recycler count")
    parser.add_argument("--seed", type=int, default=2111, help="first random seed")
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    args = parser.parse_args()
    if args.hours <= 0 or args.trials <= 0 or args.recyclers <= 0:
        parser.error("hours, trials, and recyclers must be positive")
    result = analyze(args.hours, args.trials, args.recyclers, args.seed)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
