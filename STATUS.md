# STATUS.md

**Product:** RideWorks.
**Current task:** RACE-01 — Zwift Racing Profile screenshot import and linked Race Results.
**State:** `ready_for_review` — Analyst-authorized prompt and candidate-matching corrections are ready for Owner verification. See the [report](reports/RACE-01/implementation.md), [Analyst JIT](docs/tasks/RACE-01.md), and [issue #58](https://github.com/k14krug/rideworks/issues/58).
**Branch:** `task/race-01-screenshot-import`, based on refreshed `main`.
**PR:** [#59](https://github.com/k14krug/rideworks/pull/59) (draft).
**Verification:** 580 Python tests, including 20 race tests, passed. All 11 rows in the latest retained response have dated, preselected qualifying candidates; the previous watts and scores remain incorrect. The verbatim prompt has not been live-tested.
**Next action:** Owner tests matching and, if desired, initiates a fresh extraction using the unchanged configured model. Check every field and candidate; do not confirm either earlier incorrect extraction as-is.
**Deployment:** Not authorized.
