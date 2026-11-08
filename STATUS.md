# STATUS.md

**Product:** RideWorks.
**Current task:** HOME-UI-06 — Race Avg W on Home Recent Activities. [Analyst JIT](docs/tasks/HOME-UI-06.md) · [Issue #62](https://github.com/k14krug/rideworks/issues/62).
**State:** `pending` — Owner approved this narrow Home card enhancement on 2026-11-08; AI Analyst authored the scope and committed JIT on `main`. No implementation has begun.
**Scope:** Add Race Avg W after Avg Pwr using only active race-result watt evidence, preserve distinct source meaning, card dimensions/visible row density and narrow-screen readability. No schema, importer or training changes.
**Execution:** Explicit `/TASK HOME-UI-06` or `/AUTOTASK HOME-UI-06` invocation required. Dex refreshes `main`, works in primary checkout on a task branch, opens a draft PR; HARD — Analyst Gate 1 then HARD — Owner running-UI Gate 2. No separate worktree.
**Production:** RACE-02 was already merged and deployed to production at `4650545ddaf424a32981fb718ff8cc25e61ec2c0`; this new task does not authorize production data access or deployment.
**Next action:** Owner invokes Dex with `/TASK HOME-UI-06` (or `/AUTOTASK HOME-UI-06`). Dex verifies current repository status, implements the small enhancement and stops for Analyst review.
