# Rhino Turret Compass v0.2.2-beta.1 — Community Beta

A standalone floating compass for the Rhino SRV turret in Elite Dangerous. Obtain estimated bearings to landmarks, surface contacts and deposits without rotating the entire vehicle.

## Download and start

Download **Rhino_Turret_Compass_v0.2.2-beta.1_Beta_SOURCE.zip**. Extract into a short folder such as `%USERPROFILE%\RTC`, install Python 3.12 x64 if needed, and run `Setup_Beta.cmd`. Then run the supplied verification/tests and launch with `Run_Beta.cmd`. Open `START_HERE.html` for the complete guide.

The release contains source and Windows launchers, not a compiled executable. Setup installs hash-pinned dependencies. Keep checksum verification enabled.

## Features

- Fixed-ring, two-edge cone-bisector measurement.
- Manual chassis heading with forward/right calibration.
- Optional floating bearing display and Ctrl+Alt+B copy shortcut.
- Explicit CAUTION/unavailable states and optional diagnostic crops.
- Reproducible tests, a source manifest and SHA-256 release checksums.

## Beta scope

Use while parked on approximately level ground. Recalibrate after chassis movement or display changes. Successful live use has been reported on one Windows setup; no universal accuracy bound is claimed. The one earlier same-target 293°/292° comparison is not a performance distribution. Other applications must explicitly accept an entered bearing; automatic integration is not included.

This first public beta also fixes the installer's long-path error label. The field-tested guarded cone algorithm is retained.

## License and credit

MIT-licensed code: retain the included copyright/license notice when reusing it. A visible credit to **CMDR Rhino / Rhino Turret Compass** for useful code or ideas is appreciated, not an extra license condition. Thanks to Armchair for the motivating surveying discussion. Frontier artwork and dependency notices are in NOTICE.md.

Report reproducible issues on this repository. Review diagnostic crops before sharing.
