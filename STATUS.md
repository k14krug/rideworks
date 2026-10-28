# STATUS.md

**Product:** RideWorks.
**Current task:** **HOME-UI-02 — Home Training State and 20-minute Performance trend cards**, [JIT](docs/tasks/HOME-UI-02.md).
**State:** **ready_for_review** — HOME-UI-02 implementation and local verification complete on `task/home-ui-02-trend-cards` from refreshed `main` (`453a52f`). `TASKS.md` remains `in_progress` pending required review and acceptance. HOME-UI-01 is completed.
**Owner-approved target:** Training State: actual six-month Fitness (42-day) line, dynamic Y-axis, right-endpoint value, no Fitness/Fatigue/Form Home tiles. Performance: actual 12-month rolling 42-day best eligible 20-minute power, distinct from latest eligible ride. Both cards sit beside Recent Activities; the Owner shares the private mockup with Dex.
**Execution:** `/TASK HOME-UI-02` or `/AUTOTASK HOME-UI-02`. Preserve existing calculations, source rules and other Home behavior. Dex implements, verifies, opens PR, and stops for Analyst technical review and Owner running-UI acceptance.
**Previous task:** OPS-03 **done** by explicit Owner direction 2026-10-28; [issue #44](https://github.com/k14krug/rideworks/issues/44) closed and [PR #49](https://github.com/k14krug/rideworks/pull/49) merged. Historical evidence gaps remain documented in the OPS-03 task record, not pending work.
**Verification:** 509 Python tests and 543 Chromium assertions passed at 1440/1024/768/390/320px; six fixed-clock/two-timezone comparisons preserve other Home sections, full pages, accepted models, 28 synthetic tables and two source artifacts. [Implementation/evidence](reports/HOME-UI-02/implementation.md). No production or personal activity data accessed.
**Next action:** **HARD — Analyst** technical review of the implementation PR, then **HARD — Owner** running-UI visual acceptance. Stop here; no merge, deployment or next task. Phase 6 remains deferred.
