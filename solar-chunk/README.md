# Solar chunk prototype

This project searches a bounded family of regular pole lattices and 3 x 3 panel
grids. It validates bounds, nominal-footprint overlap, assumed electrical
coverage, and assumed pole connectivity, and exports a Factorio 2.1.11
blueprint string. It does **not** claim optimality.

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
