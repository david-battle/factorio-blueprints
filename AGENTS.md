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
