# Development workflow

Use a feature branch and a draft pull request. Keep the change bounded and explain the exact behavior being altered. Include a regression test for a fixed defect.

Run manifest verification, unit tests, the three synthetic suites and the Qt smoke check. Record the actual platform and distinguish static-image checks from live capture, hotkey and gameplay checks. Inspect the Actions result for the exact proposed commit.

The runtime inputs are the selected image region and manually entered calibration. Preserve explicit validity states, stationary-use assumptions, frozen copy snapshots and opt-in diagnostic saving. Keep source, tests, fixtures and documentation limited to this application.

Keep captures and local test outputs outside committed source. For a new shared fixture, inspect its visible content and metadata, minimize it to the indicator, and add a deterministic regression test. Include only reviewed fixture files; retain attribution in NOTICE.md.

Update MANIFEST_SHA256.txt with `python tools/update_manifest.py` after intentional edits. Do not use that command to dismiss an unexplained integrity failure. Review the resulting diff before committing.

Merging and publishing are deliberate maintainer decisions. A green CI check establishes only the checks actually executed.
