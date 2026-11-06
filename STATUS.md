# STATUS.md

**Product:** RideWorks.
**Current task:** RACE-01 — Zwift Racing Profile screenshot import and linked Race Results.
**State:** `blocked` — the second Owner-run extraction still has a high field error rate; matching behavior and extraction approach need Analyst/Owner direction. See the [report](reports/RACE-01/implementation.md), [Analyst JIT](docs/tasks/RACE-01.md), and [issue #58](https://github.com/k14krug/rideworks/issues/58).
**Branch:** `task/race-01-screenshot-import`, based on refreshed `main`.
**PR:** [#59](https://github.com/k14krug/rideworks/pull/59) (draft).
**Verification:** 578 Python tests and synthetic browser checks passed. The Owner's second live test produced 11 rows with correct dates and times, but matched the supplied reference for average watts in 0/11 rows, race score in 1/11, and score change in 7/11. Comparison was local.
**Next action:** Obtain direction on safe candidate preselection and the next extraction approach. Do not confirm either incorrect extraction as-is.
**Deployment:** Not authorized.
