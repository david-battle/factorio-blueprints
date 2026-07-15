# QUP Parameterization Harness: One-Pass Instructions

The test blueprint string is in `parameterization_harness.txt`.

1. Import that string into Factorio Space Age experimental 2.1.11.
2. Click **Parameterize**. The blueprint contains the concrete **Crusher**
   recipe, so the recipe row is shown with the Crusher icon. Make that recipe
   the single parameter.
3. Start placing the blueprint and replace the Crusher recipe with **Cargo
   bay** in the one-parameter dialog.
4. Place the complete blueprint. It is absolutely snapped to one 32 x 32 chunk;
   the four corner walls mark its exact bounds.
5. Using a fresh blank blueprint, select all 16 placed harness entities,
   including the four corner walls.
6. Create that new blueprint and export the **new blueprint** to a string.
7. Paste the returned string directly into chat. A fenced code block is fine.

Also mention any error shown by the parameter dialog or any entity that failed
to place. Nothing needs to be powered, supplied, or allowed to run.

The harness checks one recipe parameter across Normal through Legendary recipe
qualities. There are no ingredient or numeric parameters to configure: after
replacing Crusher with Cargo bay, the blueprint is ready to place.
