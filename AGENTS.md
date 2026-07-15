# Factorio blueprint repository instructions

These instructions apply to every design in this repository.

## Blueprint exports

- Preserve each design's requested Factorio version, prototype names, entity
  qualities, and entity-center positions.
- Encode blueprint strings as `0` followed by Base64-encoded, zlib-compressed
  compact blueprint JSON.
- Add a decode-and-validate round-trip test and regenerate checked-in blueprint
  artifacts whenever export inputs or metadata change.

## Absolute chunk alignment

For a design intended to occupy exactly one 32 x 32 Factorio world chunk:

- Treat the heavy tile-grid lines as world chunk boundaries. They occur at tile
  coordinates divisible by 32.
- Keep nominal entity bounds in local coordinates `(0, 0)` through `(32, 32)`.
  Blueprint entity positions are centers: a 3 x 3 entity whose top-left tile is
  `(0, 0)` has JSON position `(1.5, 1.5)`.
- Export:

  ```json
  "snap-to-grid": {"x": 32, "y": 32},
  "absolute-snapping": true,
  "position-relative-to-grid": {"x": 0, "y": 0}
  ```

- Do not subtract 16 from entity positions and do not use a `(16, 16)` absolute
  grid offset. Either half-chunk shift can make the design straddle four chunks.
- Validate the decoded artifact by calculating nominal footprints and checking
  that the complete bounds are `(0, 0)` through `(32, 32)`, the absolute grid
  offset is `(0, 0)`, and all expected entities survived the round trip.
- The small red flag in Factorio's blueprint viewer is the snapping/reference
  point; it is metadata, not a placeable entity.

For multi-chunk designs, apply the same principle using dimensions that are
multiples of 32 and keep their outer nominal bounds on multiples of 32.

## Factorio 2.1.11 blueprint learnings

- Prefer small in-game validation blueprints before composing a full layout.
  Copy exact exported positions, directions, control behavior, wires, and item
  inventory structures rather than inferring undocumented JSON shapes.
- A splitter that filters every item of one quality has no item `name`:

  ```json
  "filter": {"quality": "epic", "comparator": "="}
  ```

  Set `output_priority` to the desired filtered side. Quality-only splitter
  ladders can replace recipe-specific item-by-quality sorter matrices.
- For recipe-independent requester chests, wire the chest to an assembling
  machine configured with `"read_ingredients": true`. Configure the requester
  with `"set_requests": true`, `"read_contents": false`, and an empty request
  section. Reading chest contents on the same circuit can feed inventory counts
  back as requests and cause requests to grow as the chest fills.
- When buffer chests are valid ingredient sources, set
  `request_filters.request_from_buffers` to `true` on every requester chest.
- A verified green-wire export between an assembling machine and requester chest
  uses connector 2 at both ends: `[assembler_number, 2, chest_number, 2]`.
- In the verified Normal assembler cell, the bulk inserters use `direction: 8`
  and `mirror: true`. Keep the requester immediately adjacent to its inserter;
  validate reach and arrows in game before replicating a cell.
- Factorio 2.1.11 exports four normal-quality Quality Module 3s as an `items`
  array with one item ID and four explicit module inventory slots:

  ```json
  "items": [{
    "id": {"name": "quality-module-3"},
    "items": {"in_inventory": [
      {"inventory": 4, "stack": 0},
      {"inventory": 4, "stack": 1},
      {"inventory": 4, "stack": 2},
      {"inventory": 4, "stack": 3}
    ]}
  }]
  ```

  Do not encode modules as a name-to-count dictionary in this target version.
- A compact row of 3 x 3 assembling machines needs a three-tile center pitch;
  a four-tile pitch introduces an unnecessary one-tile aisle. Preserve the
  proven off-center inserter column when compacting replicated cells.
- For the verified default-orientation recycler, relative to its center:

  - the input belt is at `(-2.5, -1.5)`;
  - the input bulk inserter is at `(-1.5, -1.5)` with `direction: 12`;
  - recovered ingredients are ejected automatically onto the belt at
    `(-0.5, -2.5)`.

  Do not add a recycler output inserter. An incorrectly positioned output
  inserter can cause the recycler to throw its first products onto the ground.
- Belts must occupy the immediately adjacent input and output tiles of a
  splitter. For an east-facing splitter centered at `(x, y)`, the continuing
  south-lane belts are at `(x - 1, y + 0.5)` and `(x + 1, y + 0.5)`; leaving an
  extra tile creates a disconnected gap.
- On a turning belt path, the corner entity's direction is the outgoing
  direction. Audit every west-to-north, north-to-east, and similar corner
  explicitly; a straight-direction corner can look close while remaining
  disconnected.
- A five-quality sorter needs only four quality-only splitters. Extract
  Legendary, Epic, Rare, and Uncommon; the final remainder is Normal. Use steel
  chests, not iron chests, for the mixed-item quality buffers, and connect each
  buffer to active consumption so it provides backpressure rather than merely
  filling forever.
- A mixed-item buffer of one quality can directly feed an assembler configured
  for that recipe quality. The assembler input inserter automatically selects
  the recipe ingredients it needs; item-specific sorter filters are unnecessary.
- Recovered Normal ingredients may be inserted into the wired Normal requester
  chests. Logistic requests automatically account for chest inventory without
  exposing chest contents on the circuit, provided `read_contents` remains
  `false`.
- Explicit copper connections between electric poles/substations use connector
  ID 5 at both ends: `[pole_a, 5, pole_b, 5]`. Add a connected copper graph to
  the blueprint instead of assuming nearby poles will auto-connect as intended.
- Keep substations outside belt corridors and future lane-extension paths. For
  designs with several logistic chests, include a powered roboport positioned
  to cover the complete chest bank rather than relying on external coverage.
- Before export, reject duplicate entity-center positions and calculate nominal
  footprints for every entity prototype. For a one-chunk design, assert every
  footprint edge stays within local coordinates `0..32`, then export 32 x 32
  absolute snapping with a zero grid offset.
- Use an underground-belt pair for unavoidable crossings between independent
  flows; do not place two ordinary belts at one center or silently merge the
  product, recycler-input, and recovered-ingredient paths.
- A verified Factorio 2.1.11 bulk inserter that filters solely by quality uses
  `"use_filters": true` plus a filter entry containing `index`, `quality`, and
  `comparator`, with no item `name`. For example:

  ```json
  {
    "direction": 8,
    "mirror": true,
    "filters": [{"index": 1, "quality": "uncommon", "comparator": "="}],
    "use_filters": true
  }
  ```

- For a simple finite product reserve, a passive-provider chest with `"bar": 1`
  and a quality-only filtered inserter keeps one stack of that quality without
  circuit logic. One stack is not always equal to rocket capacity, but it is a
  useful transparent approximation when exact rocket-capacity selector logic
  would make the blueprint disproportionately complex.
- When placing quality-reserve inserters on a shared eastbound product belt,
  account for where each native-quality assembler inserts its output. Put the
  matching reserve pickup on that output tile or downstream of it; placing it
  upstream means it can collect quality procs from earlier assemblers but can
  never collect the native assembler's own products.
- If Legendary products already leave through a proven quality-only splitter,
  retain that dedicated outlet and add one-stack reserve chests only for the
  qualities that would otherwise continue to recycling.
