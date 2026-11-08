# STATUS.md

**Product:** RideWorks.
**Current task:** HOME-UI-06 — Race Avg W on Home Recent Activities. [Analyst JIT](docs/tasks/HOME-UI-06.md) · [Issue #62](https://github.com/k14krug/rideworks/issues/62).
**State:** `ready_for_review` — implementation and synthetic verification complete on `home-ui-06-race-avg-w`; [draft PR #63](https://github.com/k14krug/rideworks/pull/63) for HARD — Analyst Gate 1.
**Scope:** Add Race Avg W after Avg Pwr using only active race-result watt evidence, preserve distinct source meaning, card dimensions/visible row density and narrow-screen readability. No schema, importer or training changes.
**Execution:** Explicit `/TASK HOME-UI-06` or `/AUTOTASK HOME-UI-06` invocation required. Dex refreshes `main`, works in primary checkout on a task branch, opens a draft PR; HARD — Analyst Gate 1 then HARD — Owner running-UI Gate 2. No separate worktree.
**Production:** RACE-02 was already merged and deployed to production at `4650545ddaf424a32981fb718ff8cc25e61ec2c0`; this new task does not authorize production data access or deployment.
**Verification:** 642 Python tests passed; synthetic responsive comparison and source checks documented in [implementation report](reports/HOME-UI-06/implementation.md).
**Next action:** Analyst Gate 1 code/data/performance/layout review; then Owner Gate 2 running-UI review.
