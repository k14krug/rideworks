# STATUS.md

**Product:** RideWorks.
**Current task:** RACE-02 — screenshot extraction, automatic whole-batch matching, correction/unlink and Activities race fields. [Analyst JIT](docs/tasks/RACE-02.md) · [Issue #60](https://github.com/k14krug/rideworks/issues/60).
**State:** `in_progress` under `/TASK`, stopped before Gate 1 for Analyst review of overlap reconciliation.
**Branch:** `task/race-02-screenshot-reliability` in the primary checkout.
**Production:** Owner reports RACE-01 is in production; no production action or live screenshot extraction is authorized for RACE-02 implementation.
**Blocker:** A synthetic counterexample showed that matching model-supplied coordinates and values can collapse two physical rows into one. A preliminary pixel-border alternative missed a short separator and misidentified a gray background. See [investigation](reports/RACE-02/implementation.md).
**Next action:** Analyst review of a safe, fail-closed method for establishing physical row identity and coverage; then resume the authorized task. No production data was accessed or changed.
