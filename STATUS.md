# STATUS.md

**Product:** RideWorks.
**Current task:** SEG-02 — Watched-segment history import and activity count columns.
**State:** `done` — Analyst and Owner gates cleared; production cutover not yet verified.
**Branch:** `main`.
**PR:** [#70](https://github.com/k14krug/rideworks/pull/70) merged as `38a16be`.
**Verification:** 690 Python tests and Chromium checks at 1440 and 390 px for count links, ranking, exception confirmation and import. See the [implementation report](reports/SEG-02/implementation.md).
**Next action:** No new development task started. Owner approved production rollout; host cutover requires a verified backup before schema migration and a read-only smoke check before Sync/import. No host action has been performed here.
