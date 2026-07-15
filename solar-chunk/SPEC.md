# Solar Chunk Blueprint Specification

## 1. Scope and objective

Target **Factorio: Space Age 2.1.11**, with the Space Age expansion enabled and no gameplay mods that alter relevant prototypes or placement/electric-network behavior.

Create one chunk-aligned blueprint that:

1. maximizes the number of normal-quality `solar-panel` entities wholly contained in one 32 x 32 world chunk;
2. uses the fewest electric poles among layouts with the maximum panel count; and
3. among remaining ties, prefers the simplest symmetric layout.

Every panel must belong to the same electric network through electric-pole supply coverage and connected copper-wire links. “Maximum” may be used only when an exact solver, exhaustive search, or independently checkable upper bound proves optimality under the finalized rules. Otherwise report “best found.”

Normal quality is part of this specification. Allowing higher qualities would change pole coverage and wire reach and therefore constitutes a separate optimization problem.

## 2. Evidence policy

Factorio-specific claims are divided into three classes:

- **Verified invariant/documented fact:** supported by current official Factorio documentation and not a value inferred from an older release.
- **Target-build fact:** read from the effective runtime prototypes or directly tested in an unmodded Space Age 2.1.11 instance. These values are not yet populated in this specification.
- **Unverified assumption:** a provisional modeling choice or remembered value. It must not be used to claim an optimum until promoted to a target-build fact with recorded evidence.

For target-build facts, save both the extraction/test procedure and its output. The preferred source is the effective runtime prototype table after all official mods load, because base prototype Lua can be modified during later data stages. Published source files and tooltip values are useful cross-checks, not substitutes for the effective 2.1.11 values.

## 3. Verified documented facts

The following are documented independently of the unresolved 2.1.11 numeric prototype values:

| ID | Fact | Evidence |
| --- | --- | --- |
| V1 | A Factorio world chunk is 32 x 32 tiles. | Official Factorio Wiki, “Map structure” |
| V2 | `ElectricPolePrototype.supply_area_distance` is the radius/half-width represented by the tooltip supply area; the prototype documentation gives 3.5 as a 7 x 7 example. | Official prototype docs, `ElectricPolePrototype` |
| V3 | `ElectricPolePrototype.maximum_wire_distance` is the maximum distance to another directly connected pole and corresponds to tooltip “wire reach.” | Official prototype docs, `ElectricPolePrototype` |
| V4 | Electric poles have a configurable automatic copper-connection limit (`auto_connect_up_to_n_wires`, default 5 at the prototype API level). Therefore geometric reach alone does not prove that automatic placement creates every desired edge. | Official prototype docs, `ElectricPolePrototype` |
| V5 | Blueprint items expose a snapping grid, an absolute-snapping flag, and a position-relative-to-grid offset. | Official runtime docs, `LuaItem.blueprint_snap_to_grid`, `blueprint_absolute_snapping`, and `blueprint_position_relative_to_grid` |
| V6 | Blueprint entity positions are map positions, not occupied-tile indices. Position coordinates may be fractional. | Official runtime concepts/docs for blueprint entities and map positions |
| V7 | Current runtime documentation defines blueprint wires separately as endpoint tuples (`BlueprintWire`). | Official runtime concepts docs, `BlueprintWire` |
| V8 | The exchange format uses a leading format byte followed by base64-encoded zlib-compressed JSON; the documented current format byte is `0`. Factorio 2.0 can also import uncompressed blueprint JSON. | Official Factorio Wiki, “Blueprint string format” |

These facts establish available fields and concepts, but **do not** establish their exact placement semantics, the target-build entity values, or the correct offset for this blueprint.

Sources consulted on 2026-07-15:

- <https://wiki.factorio.com/Chunk>
- <https://lua-api.factorio.com/latest/prototypes/ElectricPolePrototype.html>
- <https://lua-api.factorio.com/latest/classes/LuaItem.html>
- <https://lua-api.factorio.com/latest/concepts.html>
- <https://wiki.factorio.com/Blueprint_string_format>

The blueprint-string wiki page is explicitly marked as needing updates for 2.0. It may support general background, but its entity/wire schema must not be treated as authoritative for 2.1.11 without an export round-trip test.

## 4. Target-build facts required before optimization

No numeric row in this section is considered verified until an unmodded Space Age 2.1.11 runtime dump or recorded in-game test fills it in.

### 4.1 Entity geometry

Record these effective prototype properties for `solar-panel`, `small-electric-pole`, `medium-electric-pole`, `big-electric-pole`, and `substation`:

- prototype type and name;
- `collision_box` coordinates;
- `selection_box` coordinates;
- `tile_width` and `tile_height`, if exposed;
- placement flags, especially `placeable-off-grid`;
- tile-alignment behavior for even- and odd-sized entities;
- any direction-dependent collision geometry; and
- any Space Age or quality modifier affecting these properties.

“Footprint” must not be a single ambiguous value. The final model must distinguish:

1. **nominal tile footprint**, used to describe the familiar 3 x 3 or 2 x 2 occupied tile block;
2. **collision box**, used by Factorio for collision/buildability checks; and
3. **selection box**, which is visual/UI geometry and must not be used for overlap unless engine behavior requires it.

The containment rule for this project is deliberately stricter than “collision box inside the chunk”: the entire nominal occupied tile footprint must be inside the chunk. The collision box must also be inside. Selection-box overhang is permitted unless the user later requires all visual/selection geometry to remain inside.

### 4.2 Pole electrical data

For every permitted normal-quality pole, record:

- `supply_area_distance`;
- the tooltip supply-area dimensions;
- `maximum_wire_distance`;
- the tooltip wire reach;
- connection-point locations relevant to distance calculations;
- `auto_connect_up_to_n_wires`; and
- any other property affecting automatic copper connections.

Confirm whether all four named vanilla poles are present and placeable with Space Age enabled. Do not assume that these are the complete set merely because they are the familiar base-game poles; enumerate effective prototypes of type `electric-pole` and document any inclusion/exclusion.

### 4.3 Engine semantics requiring direct tests

Prototype fields alone do not fully specify these behaviors. Test them in 2.1.11:

- the exact rule for whether a pole supplies a solar panel: entity-center inclusion, collision-box intersection, nominal-footprint/tile intersection, electric-source connection point, or another rule;
- inclusive versus exclusive treatment at the supply-area boundary;
- the exact copper reach metric, including whether the limiting reach is the minimum of the two pole prototypes and whether distance is center-to-center or connection-point based;
- inclusive versus exclusive treatment at exact maximum wire distance;
- how automatic pole connections are selected when more reachable neighbors exist than the automatic connection limit;
- whether blueprint placement preserves explicit copper edges exactly, adds automatic edges, or rewires neighbors; and
- whether ghosts and revived entities produce the same final network as direct placement.

Use boundary-focused tests: place entities immediately below, exactly at, and immediately above each claimed limit. Save coordinates and observed results.

## 5. Unverified numeric assumptions

These values are provisional hypotheses only. They are retained to make the audit explicit, not to authorize implementation:

| Entity/property | Provisional value | Required verification |
| --- | ---: | --- |
| `solar-panel` nominal footprint | 3 x 3 tiles | 2.1.11 effective prototype plus placement test |
| Solar-panel legal center parity | half-integer x/y for a tile-aligned 3 x 3 entity | blueprint export of panels placed at known world tiles |
| Small pole nominal footprint | 1 x 1 tile | effective prototype plus placement test |
| Medium pole nominal footprint | 1 x 1 tile | effective prototype plus placement test |
| Big pole nominal footprint | 2 x 2 tiles | effective prototype plus placement test |
| Substation nominal footprint | 2 x 2 tiles | effective prototype plus placement test |
| Small pole supply area | 5 x 5 (`supply_area_distance = 2.5`) | effective 2.1.11 normal-quality prototype |
| Medium pole supply area | 7 x 7 (`supply_area_distance = 3.5`) | effective 2.1.11 normal-quality prototype |
| Big pole supply area | 4 x 4 (`supply_area_distance = 2`) | effective 2.1.11 normal-quality prototype |
| Substation supply area | 18 x 18 (`supply_area_distance = 9`) | effective 2.1.11 normal-quality prototype |
| Small pole wire reach | 7.5 tiles | effective 2.1.11 normal-quality prototype |
| Medium pole wire reach | 9 tiles | effective 2.1.11 normal-quality prototype |
| Big pole wire reach | **unknown; previous value 30 is not trusted** | effective 2.1.11 normal-quality prototype |
| Substation wire reach | 18 tiles | effective 2.1.11 normal-quality prototype |

The original specification's “big pole = 30” value is especially suspect because electric-pole ranges have changed across Factorio releases. No remembered or wiki value may be silently carried into the optimizer.

## 6. Coordinate and chunk model

### 6.1 Internal canonical model

After verifying that chunks use world tile boundaries at multiples of 32, represent the target chunk locally as the half-open tile region `[0, 32) x [0, 32)`. Tile `(0, 0)` is northwest; positive x is east and positive y is south.

This local convention is a project-defined normalization, not a claim that Factorio stores blueprint entities relative to the northwest corner. Factorio blueprint positions are relative map positions and commonly appear centered around a blueprint origin. Export may translate all entity centers.

An entity is contained only if its verified nominal occupied-tile footprint lies wholly in the local region. Its verified collision box must also not cross the corresponding world boundary. Merely checking the entity center is insufficient.

### 6.2 Blueprint snapping

The intended exported settings are:

- snapping grid: `{x: 32, y: 32}`;
- absolute snapping: `true`; and
- a verified `position-relative-to-grid` offset that causes the local northwest boundary, not merely an entity center or blueprint preview box, to land on world coordinates divisible by 32.

The numerical offset is currently **unverified**. Its sign convention, normalization range, interaction with blueprint translation, and behavior at negative world coordinates must be established by exporting a known test blueprint and placing it across chunk boundaries.

The validator must not infer alignment from JSON metadata alone. It must apply the verified snapping transform at multiple candidate cursor positions and prove that every realized entity footprint lies within the same world chunk. Final acceptance also requires in-game placement in positive and negative chunks.

### 6.3 Blueprint coordinate conventions to verify

Before generating the final exchange string, establish and record:

- whether entity coordinates are preserved verbatim or normalized/translated by the 2.1.11 exporter;
- legal coordinate parity for each odd- and even-sized prototype;
- the blueprint origin and preview/selection bounding-box convention;
- how `position-relative-to-grid` is represented and applied, including its sign;
- whether the `version` integer must encode exactly 2.1.11 and the correct encoding formula;
- the 2.1.11 top-level representation of copper wires and connector IDs;
- whether quality is omitted for normal entities or explicitly encoded as `normal`; and
- whether decode/re-encode and in-game import/export preserve snapping and copper-wire data.

## 7. Permitted entities and surface assumptions

Only `solar-panel` and verified prototypes of type `electric-pole` are permitted. No accumulator, combinator, lamp, roboport, foundation, landfill, power switch, consumer, tile, or decorative entity is allowed.

The optimization surface is a flat, empty, fully buildable 32 x 32 area on which all selected prototypes are legal. Planet-specific solar output is irrelevant to connectivity, but planet/surface placement restrictions must be checked. The final acceptance surface and its prototype must be recorded. Space-platform construction is excluded unless explicitly requested because platform tiles and platform electrical behavior would define a different problem.

No additional entity is currently known to be necessary. Adding one requires a specification revision and proof that the requested blueprint cannot otherwise be represented or connected.

## 8. Validity constraints

A valid layout satisfies all of the following using the finalized 2.1.11 facts:

1. Every entity has a legal prototype, normal quality, position, and direction.
2. Every nominal occupied-tile footprint and collision box is contained in one 32 x 32 chunk.
3. Factorio considers every entity pair simultaneously buildable; the programmatic collision test must reproduce the verified collision-box and collision-mask rules. Edge contact is allowed only if the engine permits it.
4. Every solar panel is supplied according to the verified electric-supply rule.
5. Required pole-to-pole copper edges satisfy the verified reach rule for both endpoint prototypes.
6. All poles that supply panels are in one connected copper network. Disconnected or unused poles are invalid because removing them improves the secondary objective.
7. The required connected network exists after ordinary blueprint construction, accounting for explicit wire records, automatic connection limits, and any engine-added edges.
8. The decoded final blueprint represents exactly the layout validated by the optimizer.

Panels do not need literal visible wires to themselves unless the 2.1.11 engine model demonstrates otherwise; the intended meaning is that each panel is supplied by a pole and all supplying poles share one copper network. This interpretation remains a project assumption until confirmed in game.

## 9. Programmatic validation requirements

Do not write the optimizer until Sections 4 through 6 have been resolved. The eventual validator must consume a versioned machine-readable dump of the verified facts and validate both the internal layout and the decoded final blueprint.

It must fail on:

- a build/version or active-mod mismatch;
- malformed exchange data or an incorrect blueprint version;
- missing/incorrect 32 x 32 absolute snapping metadata;
- a footprint outside the chunk under any tested snapped placement;
- illegal prototype, quality, coordinate parity, position, or direction;
- collision or overlap under verified engine rules;
- an unsupplied panel;
- an invalid required copper edge;
- more than one connected component among supplying poles;
- nondeterministic or incorrect final wiring after placement;
- mismatch between optimized, decoded, manifest, and rendered entities; or
- mismatch between the rendering/edge list and the decoded blueprint.

Use exact integer or rational arithmetic wherever the verified data permits it. If a prototype value is not exactly representable after scaling coordinates by two, choose a sufficient exact scale or rational representation; do not assume half-tile precision in advance. Connectivity must be checked with a standard graph traversal or union-find.

Report the panel count, poles by prototype, nominal occupied area, collision/buildability result, uncovered panels, supplying-pole component count, snapped world bounds, and final pass/fail status.

## 10. Required deliverables

The completed project must provide:

1. a Factorio exchange string beginning with the verified format byte and importable into Space Age 2.1.11;
2. the decoded blueprint JSON;
3. the recorded 2.1.11 prototype dump and boundary-test results;
4. optimization/export/validation source and invocation instructions;
5. a machine-readable manifest of entity IDs, prototypes, quality, centers, nominal footprints, collision boxes, supplied panels, and copper neighbors;
6. a generated 32 x 32 grid rendering with coordinates, legend, entity centers/IDs, pole types, and a copper-edge overlay or edge list; and
7. a validation and optimality report.

The rendering must be generated from the decoded entity list, with one text cell per world tile if a text rendering is used.

## 11. Pre-implementation verification checklist

Implementation is blocked until each item has evidence and a pass/fail result:

- [ ] Confirm the executable reports Factorio/Space Age version 2.1.11 and record active mods.
- [ ] Dump effective normal-quality prototypes for the panel and every electric pole.
- [ ] Verify solar-panel nominal footprint, collision box, center parity, and boundary placement.
- [ ] Verify every pole's nominal footprint, collision box, center parity, and boundary placement.
- [ ] Verify normal-quality supply areas and wire reaches; reconcile runtime values with tooltips.
- [ ] Determine the exact panel-supply inclusion and boundary rule.
- [ ] Determine the exact mixed-pole copper distance and boundary rule.
- [ ] Test automatic connection selection and explicit copper-wire preservation.
- [ ] Export a known 32 x 32 absolute-snapped test blueprint and derive the offset transform.
- [ ] Verify chunk alignment and containment in positive and negative world chunks.
- [ ] Verify the 2.1.11 JSON wire schema, connector IDs, quality field, and version integer.
- [ ] Confirm that the chosen non-platform test surface permits all selected entities.
- [ ] Confirm with the user that “same electric network” means supply through a connected pole graph.

Only after this checklist is complete may provisional values in Section 5 be replaced with target-build facts and optimization begin.
