# QUP: Quality up-cycler

This project generates a Factorio blueprint for a generic quality up-cycling
loop built from assembling machines, belts, inserters, recyclers, quality
modules, and storage chests.

The design targets Factorio: Space Age experimental 2.1.11. The current
integrated beta consists of the generator in [`qup.py`](qup.py), its decoded
JSON artifact in [`qup.json`](qup.json), and the importable blueprint string in
[`qup.txt`](qup.txt). The generator validates entity counts, positions,
footprints, filters, circuit and copper wiring, and the encoded round trip.

The design requirements, implemented-beta status, remaining verification
gates, and unresolved decisions are recorded in [`SPEC.md`](SPEC.md).

The logical belt, splitter, buffer, and machine routing is documented in
[`ROUTING_SCHEMATIC.md`](ROUTING_SCHEMATIC.md).

The one-chunk in-game parameterization test is
[`parameterization_harness.txt`](parameterization_harness.txt); follow
[`HARNESS_INSTRUCTIONS.md`](HARNESS_INSTRUCTIONS.md) exactly once and return the
blueprint string copied from the placed entities.

Run the crusher throughput analysis:

```powershell
python qup/qup_analysis.py --hours 100 --trials 20 --recyclers 1 --output qup/crusher_analysis.json
```

Run its tests:

```powershell
python -m unittest discover -s qup/tests -v
```

Regenerate and validate the integrated blueprint artifacts:

```powershell
python qup/qup.py --output qup/qup.txt --json qup/qup.json
```
