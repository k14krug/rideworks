# STATUS.md

**Product:** RideWorks.
**Current task:** SEG-02 — Validate bulk sources for watched-segment history.
**State:** `in_progress` — Owner requested dedicated tracked-segment count columns before final review.
**Branch:** `seg-02-history-sources`.
**PR:** [#70](https://github.com/k14krug/rideworks/pull/70) (draft).
**Verification:** 690 Python tests and Chromium rank, ride-filter and import checks at 1440 and 390 px. See the [implementation report](reports/SEG-02/implementation.md).
**Next action:** On explicit `/TASK SEG-02`, implement the two count columns in the JIT on this draft. Return for HARD Analyst review of the columns and ranking, then HARD Owner review in Dev.
