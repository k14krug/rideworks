# STATUS.md

**Product:** RideWorks.
**Current task:** FTP-01 — Database-owned historical FTP and interactive comparison. [Issue #37](https://github.com/k14krug/rideworks/issues/37).
**State:** ready_for_review — focused Astra delta review complete; Gate 1 coding remains paused pending renewed Analyst authorization.
**Branch:** `task/ftp-01-timeline-review`, based on refreshed `main` at `a1a5ae9`.
**Implementation check:** No Gate 1 code has started. Implementation paths are unchanged from the original reviewed code; no obsolete anchor/two-class implementation needs removal.
**Review:** [Focused Astra findings](reports/FTP-01/astra-single-timeline-delta-review.md). The single historical timeline and intermediate insertion contract is technically coherent; no unresolved product decision blocks Gate 1 after Analyst reauthorization. Preserve persistent initialization state, marker-based bootstrap replay after later insertions, and coherent history/cache snapshots. Boundary insertion and correction UI choices can wait until needed.
**Controlling contract:** [Current Analyst JIT](docs/tasks/FTP-01.md) and latest issue #37 clarification: all entries share one timeline, insertion leaves existing dates/watts untouched, no origin-based classes or duplicated original dataset/audit ledger. Initial Gate 0 product assumptions are superseded.
**Verification:** Focused text/code/Git/GitHub review only; no tests, application execution or migration. Documentation-only changes; database and three FTP CSV integrity checked.
**Next action:** Analyst reviews the focused findings and explicitly reauthorizes Gate 1 storage/consumer work. Resume only through a fresh `/TASK FTP-01`; stop again at its HARD — Analyst gate before Gate 2.
**Restrictions:** No Gate 2 UI, live DB write/bootstrap, deployment or CSV removal in this invocation. Later promotion and retirement require the JIT's staged authorizations.
**Last completed task:** OPS-02 accepted/merged. Phase 6 deferred.
