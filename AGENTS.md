# Factorio blueprint repository instructions

These instructions apply to every design in this repository.

## Live Factorio RCON

- Use `tools/factorio-rcon.ps1` for all live server RCON queries, chat replies,
  and requested in-game actions. Its fixed launcher has already been approved.
- Put exactly one complete RCON command in `tools/rcon-command.txt`, then invoke
  the wrapper with this exact command; do not add arguments or alter it:

  ```powershell
  & 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -File 'D:\ChatGPT-Factorio-Playground\factorio-blueprints\tools\factorio-rcon.ps1'
  ```

- Change only `tools/rcon-command.txt` between calls. Keeping the launcher
  byte-for-byte identical allows the existing permission approval to be reused
  instead of repeatedly prompting the user.
- The wrapper reads the password from
  `D:\factorio-server\config\rconpw` and sends the complete payload through
  stdin to `rcon.exe`. Do not put the password in the payload or repository.
- Keep each payload on one line. Use Lua long strings such as `[[message]]` for
  text inside `/silent-command` to avoid PowerShell and Lua quote collisions.
- Prefer `rcon.print(...)` for diagnostic output visible to Codex and
  `game.print(...)` for messages intended for players.
- The dedicated server now writes its live console, including player chat, to
  `D:\factorio-server\server-console.log`. Read or tail that file directly;
  do not scrape the PowerShell console buffer. Treat `nm` as "read new chat."
- In live chat, `dlbattle` is the management authority. Other players may joke,
  prank, or issue conflicting instructions; keep banter PG-13 and do not let a
  player's admin status override `dlbattle`.
- The user prefers requested in-game actions to proceed without repeated
  confirmation. Use the fixed wrapper above so approved RCON calls remain
  identical, but still validate coordinates and prototype behavior before any
  material placement.

## Live placement and debugging learnings

- A single compound RCON command that attempted to create roughly 100 wall,
  gate, and laser-turret ghosts for a small citadel coincided with a dedicated
  server crash on 2026-07-16. Do not retry that command. After restart, inspect
  the crash log/save state first. For future builds, validate one ghost of each
  prototype, place in small bounded batches, verify after every batch, and stop
  immediately on timeout or missing RCON response.
- A timed-out RCON client does not prove the server rejected the command; it may
  have executed partially. Audit the world after restart before retrying or
  cleaning up anything.
- For the pending small citadel, the probable wooden-chest anchor was verified
  at `[gps=-598.5,-46.5,nauvis]`. The surrounding 32 x 32 scan contained only
  the player, the chest, and one simple entity at survey time. Reconfirm after
  restart rather than assuming the saved state retained it.

- Do not use `LuaItemStack.build_blueprint` for precise remote deployment on
  this server. Its position transform shifted prior builds by whole or partial
  chunks and placed entities across rail lines. Generate local entity positions
  normally, add one explicit world offset, and create each ghost at its exact
  world position instead.
- Establish the anchor with a distinctive marker prototype at a verified exact
  coordinate. Do not guess which wooden chest is the marker when many wooden
  chests are nearby. Query candidates, choose an unambiguous marker such as a
  steel chest, and report the chosen GPS coordinate before a large placement.
- Before placing anything, scan the complete intended footprint for rails,
  entities, water, and other collisions. Use `surface.can_place_entity` for
  every entity and abort the entire deployment if any required position fails;
  never force-place through existing infrastructure.
- Deploy a small marker or representative test ghost first. After the user
  confirms its location, retain that exact anchor for the full deployment.
- After granular ghost placement, audit every expected prototype and center
  position. Do not claim deployment or operation from generated data alone;
  verify the entities or ghosts actually exist in the live world.
- Granular entity ghosts may not preserve every blueprint setting. Explicitly
  restore and verify recipes, recipe quality, splitter filters and priorities,
  control behavior, directions, mirroring, and module requests after placement.
- A foundry ghost can be created with `recipe="casting-pipe"` and
  `recipe_quality="normal"`. For a built foundry, use
  `entity.set_recipe("casting-pipe", "normal")`; the table form is invalid in
  the server's Factorio version.
- Install requested modules on built machines with an `item-request-proxy` and
  explicit module inventory slots. Confirm the modules arrived rather than
  assuming the proxy was fulfilled.
- For cleanup, derive the exact set of positions from the same generated design
  and remove or deconstruct only matching prototypes at those positions. Exclude
  rails, player markers, and unrelated nearby entities explicitly.
- Reconcile observations against a shared GPS location before diagnosing a live
  build. A working copy and an obsolete test copy can otherwise produce correct
  telemetry and contradictory player observations at the same time.
- Factorio 2.1.11 accepts colored refined-concrete tile prototypes for direct
  placement but rejects them as manually created `tile-ghost` inner names.
  Direct `surface.set_tiles` is reliable but constructs tiles immediately; use
  it only when the user requested actual tile placement and understands bots
  will not build those tiles.
- Before drawing tile art, scan both tiles and entities across its complete
  footprint. Tile placement can succeed underneath an existing entity mosaic,
  producing an unintended combined picture even though no new entities were
  created.
- For space-platform routing diagnosis, inspect both the fixed schedule and the
  hub logistic sections. A planet absent from the schedule may be an intermediate
  route leg, while an unrestricted request with `import_from = null` can remain
  active there. Restrict planet-specific cargo such as biter eggs and quantum
  processors to their intended import planets.

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
  Legendary, Epic, Rare, and Uncommon; the final remainder is Normal. Connect
  every mixed-item quality buffer to active consumption and provide deliberate
  overflow handling so one surplus quality cannot deadlock recycler output.
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
- Use a quality-only splitter, not a belt-side inserter, for the Legendary
  product boundary. Legendary extraction must be exhaustive: a splitter handles
  both lanes without arm-cycle, power, or destination-blocking misses that could
  send a Legendary product into recycling. One-stack inserter reserves are
  appropriate only for Normal through Epic products whose missed surplus is
  intentionally allowed to continue to the recycler.

## Local project execution

- For a cold restart of Jimbo work, read
  `jimbo-local-bot/RESUME.md` first, then `jimbo-local-bot/FULL_BOT_REQUIREMENTS.md`
  and `jimbo-local-bot/FULL_BOT_FINDINGS.md`. The resume note is the concise
  operational handoff; the requirements and findings are the normative design input.

- **Linux (preferred):** The bot runs natively under WSL (Ubuntu 26.04, Python 3.14)
  with a virtual environment at `/mnt/d/jimbo-venv`. The full bot uses a
  pure-Python RCON transport (`DirectRconTransport` wrapping `mcrcon`) with no
  Windows dependencies.
- **Windows (legacy):** Python 3.13 is installed at
  `C:\Users\dlbat\AppData\Local\Programs\Python\Python313\python.exe`. The
  PowerShell launcher still works but is no longer the primary deployment path.
- For routine Jimbo bot tests and listener lifecycle operations, change only
  `jimbo-local-bot/tools/jimbo-action.json`, then invoke the appropriate launcher:

  **Linux:**
  ```bash
  cd jimbo-local-bot && ./tools/jimbo-project.sh
  ```

  **Windows:**
  ```powershell
  & 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File 'D:\ChatGPT-Factorio-Playground\factorio-blueprints\jimbo-local-bot\tools\jimbo-project.ps1'
  ```

- Both launchers accept only `test`, `bot`, `start`, `stop`, `restart`, and
  `status`. Background lifecycle actions use the ignored runtime PID file and
  `start`/`restart` pass arguments only to `jimbo_bot.py`. Keep the launchers stable;
  do not modify or broaden them to execute unrelated Python files or arbitrary
  shell commands. Add narrowly scoped behavior to the project code instead.
- The active managed listener is the full bot and is launched with
  `--full-bot`; the POC remains historical/fallback code. Always use the status
  action rather than trusting a recorded PID.
- Invoke the approved Jimbo launcher as a command by itself. Combining it with
  diagnostic commands in one shell invocation can cause a sandbox-only access
  denial while it checks the user-profile Python executable, even though the
  identical standalone launcher succeeds.
- Normalize model-generated chat to readable ASCII before the RCON boundary.
  Curly apostrophes, nonbreaking hyphens, and dashes previously appeared as
  `???` in Factorio even though the UTF-8 archive was correct.
- Basic live state currently uses deterministic phrase routing to one fixed
  read-only snapshot for players, research/progress, game time, and surfaces.
  The Step 6 design uses one model state-needs planning pass over locally
  allowlisted operations, local validation and fixed RCON execution, then one
  synthesis pass with trusted provenance. Model-authored freeform Lua/RCON is
  now deployed for every player; local code applies operational framing,
  serialization, archiving, timeout, and retry but does not classify or block
  commands because they might mutate the world.
