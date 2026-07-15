# QUP Routing Schematic

## 1. Purpose and status

This document defines the logical material-routing design that should be proven
before assigning entity coordinates. It is not a placeable blueprint and does
not fix the final footprint.

The schematic targets Factorio: Space Age experimental 2.1.11 and implements
the requirements in `SPEC.md`: native blueprint parameterization, four Normal
assemblers, one assembler at every higher quality, one recycler, turbo belts,
filtered turbo splitters, normal-quality bulk inserters, iron-chest buffers,
Normal-only logistic input, and Legendary-only logistic output.

## 2. Top-level flow

```text
                     EXTERNAL LOGISTIC NETWORK
                                |
                  Normal ingredient requests only
                                v
                  +---------------------------+
                  | requester-chest input bank|
                  +-------------+-------------+
                                |
                         turbo input belt
                                |
                                v
                   +--------------------------+
                   | Normal item buffer cells |<------------------+
                   +------------+-------------+                   |
                                |                                 |
              +-----------------+------------------+              |
              |                 |                  |              |
              v                 v                  v              |
          Normal AM3        Normal AM3         Normal AM3          |
              |                 |                  |              |
              +-----------------+------------------+              |
                                |                                 |
                           Normal AM3                              |
                                |                                 |
                                +------------+                    |
                                             |                    |
 Uncommon buffers -> Uncommon AM3 -----------+                    |
 Rare buffers     -> Rare AM3 ---------------+                    |
 Epic buffers     -> Epic AM3 ---------------+                    |
 Legendary buffers-> Legendary AM3 ----------+                    |
                                             |                    |
                                             v                    |
                                  finished-product merge belt     |
                                             |                    |
                               [Legendary product splitter]       |
                                      /              \            |
                                     v                v           |
                         passive provider chest   lower-quality    |
                         (Legendary products)      product queue    |
                                                        |         |
                                                        v         |
                                             quality-module recycler
                                                        |         |
                                                        v         |
                                          item x quality splitter ladder
                                                        |         |
                                      +-----------------+---------+
                                      |
                           five quality buffer banks
```

All crafted products share one merge belt. A parameterized filtered turbo
splitter extracts only the selected finished product at Legendary quality. Its
filtered output goes to the passive provider chest. The unfiltered output is
the recycler queue, so Normal through Epic products cannot escape extraction
and Legendary products cannot reach the recycler.

## 3. Parameter contract

The schematic uses these logical blueprint parameters:

| Parameter | Meaning |
| --- | --- |
| `P0` | Target recipe selected by the player |
| `PRODUCT` | Main item product derived from `P0` |
| `INGREDIENT[n]` | Solid item ingredient `n` derived from `P0` |
| `AMOUNT[n]` | Number of `INGREDIENT[n]` consumed per craft |
| `QUALITY[q]` | Fixed quality assigned to a bank or assembler |

`P0` configures all eight AM3s. Each AM3 keeps its schematic-assigned recipe
quality. `PRODUCT` configures the Legendary output splitter. Each
`INGREDIENT[n]` configures the relevant sorter filters and Normal requester
requests. `AMOUNT[n]` configures request quantities and local feed thresholds.

The logical design reserves six ingredient slots, matching the intended upper
bound for compatible AM3 solid-item recipes. A recipe with fewer ingredients
must leave unused slot cells inert: no request, no active filter, and no
inserter activity. Whether Factorio 2.1.11 parameterization makes an absent
ingredient parameter safely inert is an explicit prototype-test gate. If it
does not, the final artifact must use the largest ingredient count that can be
proven safe or adopt a different generic sorter mechanism.

## 4. External Normal input bank

Use four requester chests, one associated with each Normal assembler. Their
requests are copied or derived from the parameterized assembler recipe; they
must not contain fixed crusher ingredients.

Each requester requests only Normal-quality ingredients. A starting request
multiplier of two recipe batches per chest is proposed:

```text
request[n] = 2 * AMOUNT[n], quality = Normal
```

Across four chests this holds approximately eight Normal recipe batches. The
multiplier is deliberately a parameterization test value, not a final balance
claim.

Normal-quality bulk inserters unload the requester chests onto a shared turbo
belt. That belt joins the recovered-Normal stream before the Normal item
splitters, ensuring external and recovered materials use the same buffers and
feed controls.

No requester chest appears at Uncommon, Rare, Epic, or Legendary quality.

## 5. Item x quality splitter ladder

Recycler output contains several ingredient prototypes and qualities. Every
combination must reach a separate buffer cell. For the crusher reference this
is a 3 x 5 matrix:

| Buffer bank | Electric engine | Steel plate | Low-density structure |
| --- | --- | --- | --- |
| Normal | `E-N` | `S-N` | `L-N` |
| Uncommon | `E-U` | `S-U` | `L-U` |
| Rare | `E-R` | `S-R` | `L-R` |
| Epic | `E-E` | `S-E` | `L-E` |
| Legendary | `E-L` | `S-L` | `L-L` |

The generic logical matrix is six ingredients by five qualities. Each active
cell has an exact `(INGREDIENT[n], QUALITY[q])` filtered turbo splitter. The
filtered side leads to that cell; the unfiltered side continues down the
ladder. This uses splitters, not inserters, for classification.

Recommended filter order is Legendary to Normal within each ingredient, with
the highest-value material extracted first. The exact physical folding of the
30-cell generic ladder remains a layout problem.

The final unfiltered remainder must terminate at a visible error belt and iron
chest. Under correct parameterization it remains empty. It must not loop back
into recycling because an unrecognized item would then circulate forever.

## 6. Buffer cell

One logical cell buffers one exact item and quality:

```text
sorter filtered output
          |
          v
    bulk inserter
          |
          v
     [iron chest] ---- buffer contents readable for diagnostics
          |
    metered bulk inserter
          |
          v
quality-specific feed loop
```

The splitter performs classification. Inserters are used only because a chest
must be loaded and unloaded.

An iron chest provides far more capacity than the statistical return stream
requires, but its inventory should be limited initially. Proposed limits:

- Normal: 12 usable slots per active ingredient cell;
- Uncommon: 8 slots;
- Rare: 6 slots;
- Epic: 4 slots; and
- Legendary: 4 slots.

These limits prevent the up-cycler from silently absorbing an excessive part of
the base while preserving many recipe batches even for low-stack-size items.
They require testing with recipes whose ingredients have unusually small stack
sizes.

## 7. Quality-specific feed loops

Each quality has one short circulating turbo belt carrying only ingredients of
that exact quality. All buffer cells for that quality discharge onto the loop.
The matching assembler input inserter takes ingredients directly from it.

The Normal loop serves four AM3s. Each higher loop serves one AM3. Assemblers
automatically reject items that are not ingredients of their selected recipe,
while the upstream sorter guarantees the correct quality.

Uncontrolled discharge from the iron chests could eventually let one surplus
ingredient fill a loop and exclude another. Each buffer-output inserter must
therefore be locally metered using the contents of its feed loop:

```text
enable cell n when:
  count(INGREDIENT[n] on loop) < AMOUNT[n] * LOOP_BATCHES
```

Proposed starting values are:

- `LOOP_BATCHES = 8` for the four-assembler Normal loop; and
- `LOOP_BATCHES = 2` for each one-assembler higher-quality loop.

The item signal and threshold must derive from `P0`. This is a small repeated
local control, not a centralized circuit computer. If Factorio cannot
parameterize the belt-reading condition and arithmetic constant reliably, an
alternative mechanically bounded feed cell must be proven before layout.

Assembler output bulk inserters place completed products on the common
finished-product merge belt. The Legendary AM3 has no quality modules; the
other seven AM3s contain four normal-quality Quality Module 3s.

## 8. Recycler queue and output

One recycler receives the unfiltered side of the Legendary product splitter.
It contains four normal-quality Quality Module 3s.

The input belt acts as the burst buffer. The analysis predicts 0.425 products/s
against recycler capacity of 0.64 products/s, so its average utilization is
approximately 66.4%. Simultaneous completion of the four Normal assemblers can
briefly queue several products; reserve at least eight belt positions before
the recycler input.

The recycler ejects directly onto a dedicated output belt. Nothing else may
merge onto this belt before the complete item x quality splitter ladder. This
protects its output inventory from downstream ambiguity and makes a blockage
visually diagnosable.

Leave a straight belt connection or repeatable entity bay beside the input and
output so a second recycler can be added for faster parameterized recipes. It
is not part of the initial entity count.

## 9. Finished-product output

The Legendary filtered branch terminates in exactly one passive provider chest
loaded by a normal-quality bulk inserter. This chest contains only the
parameterized `PRODUCT` at Legendary quality.

The chest should have a conservative slot limit so a stalled external logistic
network does not consume unbounded finished-product storage. One usable slot is
enough for crushers but may be too restrictive for high-rate recipes; the
final limit should be a blueprint parameter or a documented fixed compromise.

No requester setting belongs on the output chest.

## 10. Power and physical zones

The eventual layout should keep these zones visually recognizable:

1. Normal requester input edge;
2. Normal four-assembler block;
3. one-assembler higher-quality spine;
4. finished-product merge and Legendary extraction;
5. recycler and burst queue;
6. splitter ladder and iron-chest matrix; and
7. five quality feed loops.

Power poles must not obstruct belt-filter expansion or the optional second
recycler. Their prototypes and qualities are not yet selected.

## 11. Deadlock and contamination checks

The physical design is unacceptable unless all of these checks pass:

- A full buffer cell cannot block the splitter's unfiltered continuation.
- A surplus ingredient remains in its iron chest rather than filling a quality
  feed loop.
- The recycler can eject every result while any correctly parameterized buffer
  cell has room.
- The error chest catches every unrecognized item without feeding it back.
- A backed-up passive provider chest stops production visibly but never sends a
  Legendary product toward recycling.
- Lower-quality finished products have exactly one destination: recycler input.
- Every assembler can receive every ingredient required by its recipe.
- No belt crossing combines different quality feed loops.
- Unused ingredient slots remain inert after parameterization.
- Re-parameterizing to a recipe with two, three, four, five, and six solid
  ingredients leaves no stale filters or requester settings.

## 12. Decisions deferred to physical layout

- Exact ordering and folding of the splitter ladder.
- Whether five feed loops fit more cleanly as rows, columns, or nested loops.
- Iron-chest slot limits after stack-size testing.
- Circuit wire colors and local metering entity placement.
- Electric pole prototypes and placement.
- Exact requester multipliers and output-chest slot limit.
- Footprint, symmetry, and chunk-aligned snapping dimensions.
- Parameterization behavior for absent ingredient indices in Factorio 2.1.11.

## 13. Next validation artifact

Before generating the full blueprint, create a small parameterization harness
containing:

- one AM3;
- one recipe-derived requester chest;
- six candidate ingredient parameters;
- a short filtered-splitter ladder;
- one belt-reading metering condition; and
- recipes with two through six solid ingredients.

Export and decode that harness to record exactly which fields Factorio 2.1.11
parameterizes and how absent ingredients are represented. The full physical
layout should use only mechanisms that pass this harness.
