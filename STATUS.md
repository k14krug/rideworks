# STATUS.md

**Product:** RideWorks.
**Current task:** **HOME-UI-02 — Home Training State and 20-minute Performance trend cards**, [JIT](docs/tasks/HOME-UI-02.md).
**State:** **pending**, ready for Dex after refreshing `main`. HOME-UI-01 is completed.
**Owner-approved target:** Training State: actual six-month Fitness (42-day) line, dynamic Y-axis, right-endpoint value, no Fitness/Fatigue/Form Home tiles. Performance: actual 12-month rolling 42-day best eligible 20-minute power, distinct from latest eligible ride. Both cards sit beside Recent Activities; the Owner shares the private mockup with Dex.
**Execution:** `/TASK HOME-UI-02` or `/AUTOTASK HOME-UI-02`. Preserve existing calculations, source rules and other Home behavior. Dex implements, verifies, opens PR, and stops for Analyst technical review and Owner running-UI acceptance.
**Previous task:** OPS-03 **done** by explicit Owner direction 2026-10-28; [issue #44](https://github.com/k14krug/rideworks/issues/44) closed and [PR #49](https://github.com/k14krug/rideworks/pull/49) merged. Historical evidence gaps remain documented in the OPS-03 task record, not pending work.
**Next action:** Dex starts HOME-UI-02 only when invoked, after reading the JIT and private visual reference. No production work; Phase 6 remains deferred.
