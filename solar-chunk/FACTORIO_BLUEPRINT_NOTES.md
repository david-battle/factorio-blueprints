# Factorio blueprint notes for future Codex sessions

## Chunk-aligned 32 x 32 blueprints

- Factorio world chunk boundaries—the heavy tile-grid lines—are at world tile
  coordinates divisible by 32.
- Keep a one-chunk design's nominal entity bounds in local coordinates
  `[0, 32]` on both axes. Entity JSON positions are entity centers; for example,
  a 3 x 3 entity with top-left tile `(0, 0)` has position `(1.5, 1.5)`.
- Export these blueprint properties:

  ```json
  "snap-to-grid": {"x": 32, "y": 32},
  "absolute-snapping": true,
  "position-relative-to-grid": {"x": 0, "y": 0}
  ```

- Do not shift entity coordinates by half a chunk. Do not use `(16, 16)` for
  `position-relative-to-grid`; that offsets placement by half a chunk and makes
  a 32 x 32 design straddle four world chunks.
- The small red flag shown in Factorio's blueprint viewer is the blueprint
  snapping/reference point. It is metadata and is not placed as an entity.
- Validate a generated blueprint by decoding it and checking that its nominal
  bounds are exactly `(0, 0)` through `(32, 32)`, its absolute grid offset is
  `(0, 0)`, and all expected entities survive the encode/decode round trip.
- Blueprint strings use prefix `0`, followed by Base64-encoded zlib-compressed
  compact JSON.

When beginning another Factorio design, tell Codex: **Read
`solar-chunk/FACTORIO_BLUEPRINT_NOTES.md` before generating the blueprint.**
