# STATUS.md

**Product:** RideWorks.
**Current task:** **FTP-02 — manual FTP entry after latest recorded date**, [JIT](docs/tasks/FTP-02.md), [issue #47](https://github.com/k14krug/rideworks/issues/47).
**State:** **ready_for_review — implementation and disposable-data verification in [draft PR #48](https://github.com/k14krug/rideworks/pull/48).** Independent Analyst acceptance remains outstanding.
**Scope:** A new manual FTP entry may be dated after the last existing entry, even with no ride and even if the value is lower. Preserve existing FTP-01 history, comparisons, same-date rejection, stale-write protection, revisions/caches and old ride measurements. No editing/deleting existing entries.
**Verification:** PR branch: 24 FTP tests and 497 full Python tests passed. Development integration based on `origin/dev`: 30 FTP tests and 532 full Python tests passed. A real Chromium browser passed 17 synthetic-data checks on each, including saving a lower latest FTP without a ride, collision and stale-revision rejection, and ride suggestions. No personal FTP history was changed.
**Development preview:** Owner requested the local development restart for testing. The running app uses local integration commit `0d157d430c91161ea5fb55e77ea01d2ba75dc55c`, preserving the newer `origin/dev` changes; its FTP code matches PR #48. The FTP history fingerprint was unchanged across restart. Production was not touched.
**Next action:** Analyst review of PR #48; no automatic merge or production rollout.
**Other task:** **OPS-03 — separate production-server rollout** remains pending under [OPS-03 JIT](docs/tasks/OPS-03.md); do not mix it into FTP-02. Phase 6 remains deferred.
