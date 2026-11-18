# STATUS.md

**Product:** RideWorks.
**Current task:** SEG-01 — Saved watched Strava segments and Sync updates.
**State:** `blocked` — Analyst reviewed the probe; historical retrieval gate not cleared.
**Branch:** `seg-01-watched-segments`.
**Verification:** Activity detail verified one exact effort and one local ride link; the earlier effort-list HTTP 404 leaves history coverage unverified. See [sanitized probe report](reports/SEG-01/probe.md).
**Next action:** On explicit `/TASK SEG-01` with an Owner-supplied link to one known public outdoor segment the Owner has ridden, run the already-scoped read-only outdoor control only, using the same Dev connection and the same segment detail and effort-list endpoints (at most one GET each). Report sanitized results and stop at HARD Analyst review. No additional Tempus requests, implementation, data persistence, or production changes. An Owner decision and revised brief are required only if we later choose to narrow implementation to selected ride links plus forward capture.
