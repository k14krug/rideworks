# STATUS.md

**Product:** RideWorks.
**Current task:** RACE-01 — Zwift Racing Profile screenshot import and linked Race Results.
**State:** `blocked` — Owner-requested merge is paused because the live v3 extraction and confirmed results contain a high score-field error rate. See the [report](reports/RACE-01/implementation.md), [Analyst JIT](docs/tasks/RACE-01.md), and [issue #58](https://github.com/k14krug/rideworks/issues/58).
**Branch:** `task/race-01-screenshot-import`, based on refreshed `main`.
**PR:** [#59](https://github.com/k14krug/rideworks/pull/59) (draft).
**Verification:** 580 Python tests, including 20 race tests, passed. The Owner's live v3 test produced 11 confirmed results; against the Owner-supplied reference, 10/11 average-watt values, 1/11 scores and 1/11 score changes match. The comparison was local.
**Next action:** Resolve or explicitly review the high error rate and existing confirmed data before merge or worktree removal. Do not silently modify the Owner's records.
**Deployment:** Not authorized.
