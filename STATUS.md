# STATUS.md

**Product:** RideWorks.
**Current task:** SEG-02 — Validate bulk sources for watched-segment history.
**State:** `in_progress` — Owner likes the revised layout and requested rank and time behind best before final review.
**Branch:** `seg-02-history-sources`.
**PR:** [#70](https://github.com/k14krug/rideworks/pull/70) (draft).
**Verification:** 689 Python tests, native Chromium clipboard and sortable history at 1440 and 390 px, and a bounded read-only Hilly KOM metric check. See the [implementation report](reports/SEG-02/implementation.md).
**Next action:** On explicit `/TASK SEG-02`, implement the saved-effort ranking column in the JIT on this draft. Return to HARD Analyst review, then HARD Owner review in Dev.
