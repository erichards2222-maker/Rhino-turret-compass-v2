# Changelog

## 0.2.2-beta.1 — first public community beta

- General-purpose turret-bearing instructions, quickstart, attribution and release packaging.
- Fixed the installer's long-path error label and strengthened its regression test.
- Retained the stationary manual calibration, fixed ring pivot, cone bisector, floating readout, copy shortcut and diagnostic export.
- Includes the guarded apex-fit caution correction from 0.2.1; the bearing algorithm is otherwise unchanged.

## 0.2.1 — guarded apex-fit caution

- Qualify modest apparent apex discrepancies only when edge and radial measurements agree.
- Display CAUTION in the interface, floating readout, copy history and diagnostic JSON.
- Retain rejection for severe mismatch, ambiguous sectors and unstable centerlines.

## 0.2 — fixed-ring detector

- Fit the outer ring instead of assuming the selected region's center.
- Measure the bisector of two cone boundaries rather than the colored-pixel centroid.
- Added pale-cyan edge handling, invalid-image regressions, and correct Qt hotkey dispatch.
