# STATUS.md

**Product:** RideWorks.
**Current task:** RE-03 — Fixed-color Strava Relative Effort numbers.
**State:** `pending` — Owner approved the direction on 2026-10-29. [Analyst JIT](docs/tasks/RE-03.md) is committed. No RE-03 code implementation has started.
**Baseline:** RE-02 completed and merged to `main` in [PR #53](https://github.com/k14krug/rideworks/pull/53). Existing rolling 42-day effort dots/labels are the current accepted implementation until RE-03 is implemented and reviewed.
**Goal:** Show Strava `suffer_score` as a fixed-color number on Home Recent Activities, Activities and Activity Review. Use only bounded recent API enrichment; missing scores remain missing. Fitness/Fatigue/Form, RideWorks modeled stress, historical FTP and other features must remain unchanged.
**Undecided:** Exact fixed boundaries; the JIT specifies a provisional set for initial implementation and Owner visual review, not a final accepted scale.
**Next action:** Owner invokes `/TASK` for Dex. Dex must refresh `main`, verify no other work in progress, inspect the JIT and source, implement on a task branch, and open a draft PR. Stop at HARD — Analyst and HARD — Owner review gates.
**Deployment:** Not authorized. No production Store or live service changed.
