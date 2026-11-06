# STATUS.md

**Product:** RideWorks.
**Most recently completed task:** RACE-01 — Zwift Racing Profile screenshot import and linked Race Results. [PR #59](https://github.com/k14krug/rideworks/pull/59) merged, accepted as-is by Owner with documented recognition errors.
**State:** `done` for RACE-01. No task currently `in_progress`.
**Verification:** The RACE-01 report records 580 passing Python tests and live 11-row comparisons. Final live extraction matched 10/11 average-watt values but only 1/11 Racing Scores and 1/11 score changes; incorrect confirmed records may remain. See [report](reports/RACE-01/implementation.md). These are prior accepted findings, not a quality claim.
**Production:** Owner reports RACE-01 is now in production (2026-11-06); the repository does not independently prove which production revision was deployed. No production action taken by RACE-02 authoring.
**Next pending task:** RACE-02 — improve screenshot extraction, require automatic whole-batch matching, preserve safe correction/unlink and add Activities race fields. [Analyst JIT](docs/tasks/RACE-02.md) · [Issue #60](https://github.com/k14krug/rideworks/issues/60).
**Next action:** Owner may explicitly invoke `/TASK RACE-02` or `/AUTOTASK RACE-02`. Dex must fetch/refesh `main`, use a clean task worktree, follow the JIT and stop for HARD — Analyst technical review. No automatic task start, no unapproved live API upload or deployment.
