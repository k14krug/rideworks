# STATUS.md

**Product:** RideWorks.
**State:** **done — FTP-01 final Gate 4 accepted by Owner on 2026-10-17** for the main development application. No active implementation task. Do not automatically start a new task.
**Completed task:** FTP-01 — historical SQLite FTP history and Performance editor. [Issue #37](https://github.com/k14krug/rideworks/issues/37), [merged PR #41](https://github.com/k14krug/rideworks/pull/41), approved development release `cc3acc5527230bb88405b28dd1378fe6d41cde34`.
**Development deployment:** The Owner reports RideWorks running on port 8765 after successful in-place migration to schema 11, initial 66 FTP entries at revision 1, and preservation of 1,444 activities, 2,885 performance-history records, 22 Strava API activities, 24 non-cache tables and 1,422 original source artifacts. Integrity, numeric parity and browser smoke checks passed per the cutover handoff; Owner inspected and explicitly accepted the feature.
**Verification:** 494 Python tests, 107 disposable-copy browser assertions, fresh-context Astra reviews, and targeted database concurrency checks passed before release. The local Gate 4 evidence is in `/home/kkrug/projects/rideworks-ftp01/reports/FTP-01/gate-4-cutover.md` (not currently tracked on GitHub).
**Recovery:** Keep the verified pre-cutover schema-10 backup at `/home/kkrug/rideworks-backups/ftp01/20261017T015331Z/data/` paired with old code `92667ad`. Retain the FTP-01 worktree until housekeeping is separately chosen.
**Environment boundary:** The separate production server has **not** been updated under FTP-01 Gate 4. A later Owner-directed update may use the accepted development code and a consistent SQLite/database-artifact copy, with its own backup and preservation of production-specific configuration. This is not automatic.
**Next action:** Wait for the Owner to choose the next task or direct the separate production-server rollout. Phase 6 remains deferred.
