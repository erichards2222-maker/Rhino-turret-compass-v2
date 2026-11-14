# Development and code review

This repository contains a Windows/Python turret-bearing helper. Keep changes scoped, retain MIT notices, and do not commit generated diagnostics, local environments or credentials.

## Code Review Rules

Review the exact proposed commit. Check the fixed ring origin, circular wrap, caution gating, calibration invalidation, stale-frame handling, display scaling, Windows message routing, exclusive diagnostic writes, dependency hashes, and installer labels. Treat synthetic tests as image checks, not proof of gameplay accuracy.

Check all runtime and release paths. CI should be read-only; a deliberately invoked release job may write only the named repository release/tag/assets. Do not expose credentials in output or execute code from untrusted PRs with a write token.

Provide concrete reproductions and severity for findings. Distinguish a clean result from a skipped or unrun check. Do not edit the candidate during a read-only review.
