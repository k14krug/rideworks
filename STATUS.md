# STATUS.md

**Product:** RideWorks.
**Current task:** RACE-02 — screenshot extraction, automatic whole-batch matching, correction/unlink and Activities race fields. [Analyst JIT](docs/tasks/RACE-02.md) · [Issue #60](https://github.com/k14krug/rideworks/issues/60).
**State:** `blocked` under `/TASK`; a synthetic corrected-date reimport can leave two active associations for the same race. The branch must not be used for real imports.
**Branch:** `task/race-02-screenshot-reliability` in the primary checkout.
**Production:** Owner reports RACE-01 is in production; no production action or live screenshot extraction is authorized for RACE-02 implementation.
**Evidence:** The [investigation](reports/RACE-02/implementation.md) records the reproducible wrong-attachment case, implemented work and synthetic checks. Gate 1 is not complete.
**Next action:** Analyst review of cross-import race identity and safe correction; do not merge, deploy, or run real imports. No production data was accessed or changed.
