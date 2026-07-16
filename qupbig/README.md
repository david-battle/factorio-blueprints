# QUPBIG: foundry pipe quality farm

`qupbig.py` generates a 64 x 32 absolute-snapped Factorio 2.1.11 blueprint.
Two foundries cast pipes from molten iron using four normal-quality Quality
Module 3s each. A quality-only splitter extracts every Legendary pipe; one
quality-module recycler turns all lower-quality pipes into quality iron plates.

The recovered plates are an output, not a closed loop: `casting-pipe` consumes
only molten iron, and fluids have no quality, so the recovered solid plates
cannot feed the foundries directly.

Generate and round-trip validate the artifacts:

```powershell
python qupbig/qupbig.py --output qupbig/qupbig.txt --json qupbig/qupbig.json
```

## Live verification

The two-foundry/one-recycler layout was deployed and operated on Nauvis in
Factorio 2.1.11 on 2026-07-16. Verified in the live build:

- both foundries received 1500-degree molten iron through their south ports;
- four normal-quality Quality Module 3s were installed in both foundries and
  the recycler;
- both foundry output inserters and the complete reject belt operated;
- the quality-only splitter retained its Legendary filter and left priority;
- the recycler input arm, automatic output tile, eastbound recovery belt, and
  active-provider chest operated;
- all machines and substations belonged to the same electric network; and
- the recovered chest received both Normal and Uncommon iron plates.

The live prototype rates are 3.2 crafts/s per module-slowed foundry and 12.8
items/s for the module-slowed recycler. With the foundry's inherent +50%
productivity, two foundries produce at most 9.6 pipes/s, leaving roughly 33%
recycler throughput headroom before Legendary extraction.

The external molten-iron connection is site-specific and is not included in
the reusable artifact.
