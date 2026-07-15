# QUP Blueprint Design Specification

## 1. Status

This document specifies the intended design. It does not authorize or describe
an implemented generator, checked-in blueprint string, or finalized layout.

Target **Factorio: Space Age experimental 2.1.11**, with all five quality levels
unlocked and no gameplay mods that change the relevant recipes, entities,
modules, or quality mechanics. Runtime prototype values must be verified
against this build before implementation.

## 2. Objective

Create a reusable quality up-cycler blueprint for an item that:

- has quality variants;
- can be crafted in an `assembling-machine-3`;
- has only solid ingredients, unless a later design explicitly provides a
  quality-independent fluid input; and
- produces an item that a recycler can reverse into its recipe ingredients.

The blueprint repeatedly crafts an item, extracts Legendary products, recycles
all unwanted lower-quality products, sorts the recovered ingredients by
quality, and crafts again at the matching ingredient quality.

The distinguishing feature is additional Normal-quality crafting capacity.
This is intended to feed the recycling and higher-quality stages more steadily
than the common one-crafter-per-quality arrangement while remaining reasonable
to build in a real game.

The first concrete reference item is the Space Age `crusher`. The layout should
not hard-code crusher-specific ingredient identities where Factorio blueprint
parameters or generator inputs can make the design generic.

## 3. Reference recipe

The installed Factorio 2.1.11 source defines one crusher per 10-second base
craft using:

- 10 `electric-engine-unit`;
- 10 `steel-plate`; and
- 20 `low-density-structure`.

This differs from recipes documented for later builds and is why the project
must use target-build data. These names, quantities, crafting category,
productivity eligibility, and recycling behavior still require a final
effective-runtime dump or in-game cross-check before export.

An unmodified normal-quality AM3 has crafting speed 1.25 and four module slots.
Four quality modules impose a combined speed penalty whose exact value depends
on the selected modules. Under the currently discussed four-quality-module
configuration, a working planning estimate is approximately one crusher per
assembler per 10 seconds.

At that estimate, the four Normal crusher assemblers have gross demand of:

| Item | Per second | Per minute |
| --- | ---: | ---: |
| Electric engine units | 4 | 240 |
| Steel plates | 4 | 240 |
| Low-density structures | 8 | 480 |
| Crushers crafted | 0.4 | 24 |

These are gross crafting inputs. Recovered ingredients reduce external supply
demand after the recycling loop reaches steady state. The generator must not
encode an assumed reduction without calculating it from the selected module
configuration and verified quality mechanics.

## 4. Crafting fleet

The initial design shall contain eight normal-quality AM3 entities assigned by
recipe quality as follows:

| Selected recipe quality | AM3 count | Normal operating role |
| --- | ---: | --- |
| Normal | 4 | Consume externally supplied and recovered Normal ingredients |
| Uncommon | 1 | Consume recovered Uncommon ingredients |
| Rare | 1 | Consume recovered Rare ingredients |
| Epic | 1 | Consume recovered Epic ingredients |
| Legendary | 1 | Consume recovered Legendary ingredients and make final output |

The four Normal assemblers are an intentional upper bound, not a promise that
all four will run continuously. Starvation during startup or under limited base
supply is acceptable. The layout should allow capacity to be enabled naturally
by material availability without requiring manual recipe changes.

Every assembler must select the same item recipe at the quality listed above.
All item ingredients supplied to one craft must have exactly that quality.

### 4.1 Assembler modules

- Normal through Epic assemblers shall use quality modules in all four slots.
- The initial/default configuration is normal-quality `quality-module-3` in
  every applicable slot. Module tier and module quality shall remain
  configurable and must be recorded as export inputs.
- The Legendary assembler shall not use quality modules: Legendary output
  cannot be upgraded, while quality modules still slow the machine.
- The default Legendary configuration is empty module slots. Speed or
  efficiency modules may be offered as an explicit variant. Productivity may
  be used only when the selected recipe actually permits it.
- Beacon use is outside the initial design unless later analysis demonstrates
  that it materially improves a constrained stage without compromising the
  desired quality chance.

## 5. Recycling fleet

All Normal, Uncommon, Rare, and Epic crafted products shall be eligible for the
recycling path. Legendary finished products shall never be recycled.

Every recycler shall contain four quality modules. The initial/default
configuration is four normal-quality `quality-module-3` modules. Recycler
module tier and quality shall use the same configurable evidence policy as
assembler modules; they need not be identical to the assembler modules if the
final generator supports separate settings.

The initial design shall contain one recycler. The expected-flow model and a
20-trial, 100-hour-per-trial discrete simulation both find approximately 66.4%
recycler utilization for the specified crusher scenario. One quality-module
recycler processes 0.64 crushers/s, while the modeled loop sends approximately
0.425 crushers/s to recycling.

The layout should preserve a practical way to add a second recycler if a
different parameterized recipe has a shorter crafting time or creates more
recycler load. Recycler sizing for every reference scenario must use:

- the target recipe's verified recycling time;
- recycler crafting speed and entity quality;
- module speed modifiers;
- expected product flow from every crafting tier;
- belt and inserter throughput; and
- an allowance for stochastic bursts and output blocking.

The balance calculation is reproducible with `qup_analysis.py`; changing the
recipe, module configuration, assembler fleet, or building qualities requires
rerunning it.

## 6. Material flow

The logical flow is:

```text
external Normal ingredients + recovered ingredients
                         |
                         v
       quality-specific ingredient buffers
                         |
                         v
       matching-quality assembling machines
                         |
              +----------+----------+
              |                     |
       Legendary product       lower-quality product
              |                     |
              v                     v
         final output       quality-module recyclers
                                      |
                                      v
                         recovered ingredient sorter
                                      |
                                      +----> quality buffers
```

Recovered ingredients from a single recycled product roll independently and
may emerge at different qualities. They must be classified by both item type
and quality before being admitted to an assembler buffer.

For the crusher reference recipe, the routing system must distinguish all 15
item/quality combinations: electric engine units, steel plates, and low-density
structures across five qualities.
The generic design must derive this set from the selected recipe rather than
assuming three ingredients.

## 7. Logistics and buffering requirements

- Use belts as the primary transport mechanism inside the up-cycler. Internal
  item movement shall not depend on logistic robots.
- Use the turbo belt family by default: `turbo-transport-belt`,
  `turbo-underground-belt`, and `turbo-splitter`.
- Use filtered splitters for quality/item separation wherever a filtered
  splitter and a filtered inserter can both perform the job correctly. A
  filtered inserter is acceptable only where geometry, buffering, quality-aware
  routing, or machine/chest interaction makes a splitter unsuitable.
- Use normal-quality `bulk-inserter` entities for transfers that require an
  inserter. Do not use `stack-inserter`: its behavior of waiting to collect a
  full hand can introduce undesirable delays in this low-volume, stochastic
  quality loop. Any exception requiring another inserter prototype must be
  documented and justified by the layout.
- Use iron chests where internal buffering is necessary. Do not substitute
  logistic chests for internal buffers merely to simplify routing.
- Requester chests may be used for external input only at the Normal-quality
  ingredient boundary. They must obtain recipe-derived requests as specified
  in Section 9 and must not request Uncommon, Rare, Epic, or Legendary
  ingredients from the surrounding base.
- Provide one passive provider chest for the finished-product boundary. Only
  Legendary finished products may be delivered to this chest; no lower-quality
  product or recycled ingredient may reach it.
- Provide buffering between recycling/sorting and every quality-specific
  assembler. Random recycler returns must not directly synchronize assembler
  cycles.
- Prevent one surplus ingredient or quality from blocking recycler output or a
  shared transport line.
- Prevent ingredients of the wrong quality from entering an assembler.
- Prevent non-Legendary finished products from escaping the recycling path.
- Prevent Legendary finished products from entering a recycler.
- Keep the external Normal-input requester chests and outgoing Legendary-product
  passive provider chest physically and logically separate.
- Prefer visible, diagnosable material flow over dense circuitry. Circuit
  conditions are permitted when they prevent overflow or control optional
  Normal capacity, but the initial design should not require a complex control
  computer.
- Document every requester-chest request and any logistic-network dependency.
  The external base may use robots to fill the Normal-input requester chests,
  but robots shall not be required for internal sorting or recirculation.

The buffer policy must account for ingredients with different counts per craft.
For crushers, a useful threshold is at least one full recipe batch per active
assembler, with additional margin to absorb the recycler's discrete returns.
Exact chest limits and inserter enable conditions remain to be designed.

## 8. Quality and recycling model

The balancing tool shall model five qualities in order:

1. Normal
2. Uncommon
3. Rare
4. Epic
5. Legendary

For a machine with total quality chance `Q`, the documented model makes an
initial upgrade roll with chance `Q`; after success, additional tier jumps use
a 10% continuation chance and are capped at Legendary. Recycling returns an
average of 25% of reversible solid recipe ingredients before applying quality
rolls. Fluid ingredients are not recovered.

These rules create a stochastic flow rather than a deterministic recipe ratio.
The analysis tool shall report at least:

- expected crafts and products per minute by quality;
- expected recycled products per minute by quality;
- expected recovered ingredients per minute by item and quality;
- required external Normal ingredients;
- expected utilization of each assembler and recycler;
- bottleneck stage; and
- enough buffer guidance to tolerate ordinary variance.

Expected values alone do not prove that a compact buffer will avoid starvation
or blocking. A discrete-event or Monte Carlo simulation should be considered
before finalizing buffer sizes.

## 9. Adaptability

The final exported artifact shall be a native Factorio parameterized blueprint.
After import, the player must be able to use Factorio's built-in blueprint
parameterization interface to select a compatible target recipe; generating a
new blueprint string with the Python generator shall not be required for normal
recipe substitution.

The blueprint shall expose one canonical target-recipe parameter and reuse it
throughout the design. Parameter substitution must configure every AM3 with the
selected target recipe while preserving that machine's assigned recipe quality
(Normal, Uncommon, Rare, Epic, or Legendary).

Every recipe-dependent setting must be classified as one of:

1. directly replaced by Factorio's blueprint parameterization;
2. derived by Factorio from the parameterized assembler recipe; or
3. deliberately recipe-agnostic in the physical design.

No recipe-dependent prototype name, item signal, inserter filter, splitter
filter, belt reader condition, chest request, or circuit constant may remain
silently fixed to `crusher` or one of its ingredients.

Normal-input requester chests require special treatment. They shall not contain
fixed ingredient requests copied from the crusher example. Their requests must
be set or derived from the recipe in the associated assembler using Factorio's
supported recipe-to-request behavior, so that selecting a different recipe
also produces the correct ingredient requests. Any request multiplier, minimum
batch size, or quality setting must remain valid after parameter substitution.
The outgoing passive provider chest shall contain no fixed crusher-specific
setting. It does not request ingredients or finished products.

If Factorio cannot parameterize a recipe-dependent field, the design must avoid
that field or replace it with a recipe-derived/generic mechanism. A generator-
side special case is not an acceptable substitute for native parameterization
in the final artifact.

Parameterization shall be tested in the target game with the crusher reference
and at least two materially different compatible AM3 recipes, including a
recipe with a different ingredient count. For each test recipe, verify recipes
and recipe qualities on all eight assemblers, requester-chest contents, filters
and circuit signals, routing, recycling, and Legendary extraction.

The eventual generator should separate recipe data from physical layout. At a
minimum, its input model should cover:

- target item and recipe prototype names;
- target Factorio version;
- solid ingredient names and quantities;
- recipe energy/crafting time and output count;
- crafting and recycling categories;
- assembler and recycler prototype names and qualities;
- assembler counts by recipe quality;
- module prototype, tier, quality, and count for each stage;
- belt/inserter/chest choices; and
- blueprint parameters supported by the target game version.

The first artifact may be crusher-specific while the layout is proven, but
crusher identities must be isolated so another compatible recipe can replace
them without rewriting placement logic.

Recipes with fluids, multiple products, probabilistic products, catalysts,
spoilage, non-reversible recycling, more ingredients than the sorter supports,
or a crafting category unavailable to AM3 are outside the initial compatibility
set and must fail validation with a clear reason.

### 9.1 Crusher balance result

With four normal-quality Quality Module 3s in each Normal-through-Epic AM3 and
in the recycler, and no modules in the Legendary AM3, the expected steady flow
is:

| Stage | Crafts/s | Assembler utilization |
| --- | ---: | ---: |
| Normal | 0.400000 | 100.00% |
| Uncommon | 0.020313 | 20.31% |
| Rare | 0.004079 | 4.08% |
| Epic | 0.000768 | 0.77% |
| Legendary | 0.000085 | 0.068% |

The expected final output is 0.000263 Legendary crushers/s, or approximately
0.948/hour. A 20-trial simulation of 100 hours per trial produced a mean of
0.929/hour with a range of 0.83 to 1.07/hour.

Recycling reduces the fresh Normal input to approximately 79.75% of gross:

| External Normal input | Items/s |
| --- | ---: |
| Electric engine units | 3.19 |
| Steel plates | 3.19 |
| Low-density structures | 6.38 |

These figures are statistical steady-state values, not guaranteed short-window
rates. The checked-in detailed result is `crusher_analysis.json`.

## 10. Physical layout and blueprint metadata

No footprint or chunk count has yet been chosen. The design does not currently
require a one-chunk layout.

Once a footprint is chosen, its outer nominal bounds should be multiples of 32
where practical. If the design is exported with absolute snapping, it shall
follow the repository alignment rules: outer nominal bounds on world chunk
boundaries and a zero absolute grid offset. It must not use a half-chunk shift.

All entity positions are entity centers. The implementation must preserve
prototype names, entity qualities, recipe selections, module inventories,
filters, circuit connections, and positions through blueprint encoding.

## 11. Verification gates before implementation is complete

Before a generated blueprint can be called complete:

1. Verify the runtime is Factorio: Space Age experimental 2.1.11.
2. Dump or otherwise verify the effective target-build prototypes and recipes.
3. Confirm that AM3 can craft the crusher recipe at every unlocked quality.
4. Confirm crusher recycling ingredients, quantities, time, and rounding.
5. Confirm quality-module effects and speed penalties in both AM3s and
   recyclers.
6. Cross-check the modeled one-recycler throughput in game and confirm that
   burst buffering prevents input or output blocking.
7. Verify every belt, inserter, chest, module, and power entity used.
8. Validate nominal footprints and all entity-center positions.
9. Demonstrate that no item/quality combination can deadlock the sorter under
   the stated buffer assumptions.
10. Encode the artifact as `0` plus Base64-encoded, zlib-compressed compact
    blueprint JSON.
11. Decode the checked-in artifact and validate metadata, entity counts,
    positions, qualities, recipes, modules, filters, and connections.
12. Inspect every recipe-dependent field and prove it is parameterized,
    recipe-derived, or recipe-agnostic.
13. Instantiate the imported blueprint through Factorio's built-in
    parameterization UI for the crusher and at least two other compatible
    recipes, then validate all recipe-derived requests and settings.
14. Perform an in-game operating test on the target build.

Any change to generator inputs, layout, or metadata requires regenerating the
checked-in blueprint artifacts and rerunning the decode-and-validate round trip.

## 12. Open design decisions

- Inserter capacities and circuit conditions at each transfer point; the
  default inserter is a normal-quality bulk inserter, internal buffers are iron
  chests, requester chests are confined to the Normal-input boundary, and a
  passive provider chest is used for Legendary output.
- Recycler placement and provision for an optional repeatable second recycler.
- Buffer sizes and overflow behavior.
- Whether idle Normal assemblers need circuit-controlled input priority.
- Whether all four Normal assemblers share equal priority or start in stages.
- Power distribution entities and their qualities.
- Blueprint dimensions, symmetry, tiling, and snapping grid.
- Which routing and filtering mechanisms remain fully generic under native
  parameterization, especially for recipes with different ingredient counts.
- Legendary assembler module variant, if any.

## 13. Sources and evidence status

Sources consulted on 2026-07-15:

- Official Factorio Wiki, Crusher: <https://wiki.factorio.com/Crusher>
- Official Factorio Wiki, Assembling machine 3:
  <https://wiki.factorio.com/Assembling_machine_3>
- Official Factorio Wiki, Quality: <https://wiki.factorio.com/Quality>
- Official Factorio Wiki, Recycler: <https://wiki.factorio.com/Recycler>
- Official Factorio Wiki, Quality upcycling math:
  <https://wiki.factorio.com/Tutorial:Quality_upcycling_math>
- Official Factorio Wiki, Tungsten carbide:
  <https://wiki.factorio.com/Tungsten_carbide> (consulted during early analysis;
  not an ingredient in the target 2.1.11 crusher recipe)
- Official Factorio Wiki, Electric engine unit:
  <https://wiki.factorio.com/Electric_engine_unit>
- Official Factorio Wiki, Foundry: <https://wiki.factorio.com/Foundry>
- Official Factorio Wiki, Big mining drill:
  <https://wiki.factorio.com/Big_mining_drill>

Wiki values are documented planning evidence, not a substitute for target-build
data. The executable reports 2.1.11 build 86962. Recipe, AM3, recycler, module,
and recycling-generation values in `prototype_facts_2.1.11.json` were traced
through the installed unmodified 2.1.11 prototype Lua on 2026-07-15. Because a
server and client were already running, a separate `--dump-data` process could
not be completed; an effective-runtime dump or in-game cross-check therefore
remains a mandatory final gate.
