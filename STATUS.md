# STATUS.md

**Product:** RideWorks.
**Current task:** **FTP-02 — manual FTP entry after latest recorded date**, [JIT](docs/tasks/FTP-02.md), [issue #47](https://github.com/k14krug/rideworks/issues/47).
**State:** **in_progress — changes committed on `task/ftp-02-manual-latest-entry` in [draft PR #48](https://github.com/k14krug/rideworks/pull/48) on 2026-10-27; local runtime verification and review still required.** No personal data-store write or deployment.
**Scope:** A new manual FTP entry may be dated after the last existing entry, even with no ride and even if the value is lower. Preserve existing FTP-01 history, comparisons, same-date rejection, stale-write protection, revisions/caches and old ride measurements. No editing/deleting existing entries.
**Verification:** Actual FTP browser preview function passed six isolated synthetic cases, and modified JavaScript parsed. Static source checks confirm removal of the prohibition; normal Python regressions and disposable-browser verification have **not** been run.
**Next action:** Run FTP-focused and full regression suites on an isolated test Store, review the branch and browser behavior, then seek Owner acceptance before merge/deployment.
**Other task:** **OPS-03 — separate production-server rollout** remains pending under [OPS-03 JIT](docs/tasks/OPS-03.md); do not mix it into FTP-02. Phase 6 remains deferred.
