# STATUS.md

**Product:** RideWorks.
**Current task:** SEG-01 — Saved watched Strava segments and Sync updates.
**State:** `blocked` for implementation — Zwift follow-up authorized on explicit invocation.
**Branch:** `seg-01-watched-segments`.
**Verification:** Activity detail verified one exact effort and one local ride link; the earlier effort-list HTTP 404 leaves history coverage unverified. See [sanitized probe report](reports/SEG-01/probe.md).
**Next action:** `/TASK SEG-01` on this branch: run only the Zwift-first read-only follow-up in the JIT with the newer of the two Owner-supplied Tempus and Titans Loop activity-effort links. Skip the outdoor control. Stop at HARD Analyst review; no implementation or production changes.
