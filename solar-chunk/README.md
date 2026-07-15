# Solar chunk prototype

This project searches a bounded family of regular pole lattices and 3 x 3 panel
grids. It validates bounds, nominal-footprint overlap, assumed electrical
coverage, and assumed pole connectivity, and exports a Factorio 2.1.11
blueprint string. It does **not** claim optimality.

Substations are accepted only when their entire 18 x 18 electric supply area
stays inside the 32 x 32 chunk. The current reflection-symmetric candidate has
96 panels and four substations, positioned so their supply areas reach the four
chunk corners. Its remaining area includes at least 15 mutually non-overlapping
2 x 2 footprints suitable for optional accumulators.

Blueprint entities retain local chunk coordinates from 0 through 32. Absolute
snapping uses global offset `(0, 0)`, placing their outer edges on Factorio's
heavy world-grid lines at coordinates divisible by 32.

Run the search and write both outputs:

```powershell
python solar-chunk/solar_chunk.py --json solar-chunk/layout.json --ascii solar-chunk/layout.txt --blueprint solar-chunk/blueprint.txt
```

Run the tests:

```powershell
python -m unittest discover -s solar-chunk/tests -v
```

Python 3.10 or newer is required.

All Factorio-specific constants and their evidence status are in the marked
configuration section at the top of `solar_chunk.py`. See `SPEC.md` for the
verification gates that must be completed before those assumptions are promoted
to Space Age 2.1.11 facts.
