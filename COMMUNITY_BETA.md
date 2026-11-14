# Community beta quickstart

**Rhino Turret Compass v0.2.2-beta.2 — Windows x64 / Python 3.12**

Use the Rhino SRV turret as a convenient bearing indicator for landmarks, surface contacts, or survey notes. The floating compass estimates direction from the circular HUD graphic while the chassis remains parked.

## Installation

Download the named Beta_SOURCE.zip asset from this repository's Releases page. Extract into a short writable path such as `%USERPROFILE%\RTC`. Install Python 3.12 x64, run `Setup_Beta.cmd`, then run `Verify_Package.cmd`, `Run_Tests.cmd` and `Run_UI_Check.cmd`. Finally run `Run_Beta.cmd`. Start with **Open supplied sample**; its image angle is approximately 298°.

## Field checklist

1. Park on approximately level ground and note the normal chassis heading.
2. Select the entire circular turret-direction indicator with a narrow margin. Inspect the fitted circle and pivot, then lock the ring.
3. Enter the chassis heading, aim straight along the nose and set **FORWARD**. Turn the turret about 90° right and perform the **RIGHT** check. Confirm the stationary/level conditions.
4. Sweep a full turn and check that the green line stays centered. Center the target marker, then read the bearing or use **Freeze & COPY bearing now**. The optional shortcut is Ctrl+Alt+B.
5. Invalidate the anchor and recalibrate whenever the chassis or display arrangement changes.

**CAUTION** readings passed extra geometry checks but remain approximate. Keep the warning with your notes: the clipboard number does not include it. On a failed copy, the previous clipboard content remains unchanged.

## Expectations

This is an experimental navigation aid. A successful local test or synthetic suite is not a guarantee for every display or terrain. Level-ground, stationary use is the initial supported workflow. A single earlier target comparison differed by 1°; broader accuracy has not been characterized.

A bearing can be used with any application or calculator that explicitly accepts it. This beta does not automatically integrate with other software and does not calculate target range or coordinates.

## Feedback and reuse

Report reproducible problems through Issues with version, display setup and steps. Save only reviewed indicator crops when diagnostics are needed. See README.md for full instructions and limitations.

MIT-licensed source is included. Retain the required license notice when reusing code. Credit to CMDR Dunn Actual / Rhino Turret Compass is appreciated for code or concept reuse, without adding restrictions to the MIT license.
