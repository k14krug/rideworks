# STATUS.md

**Product:** RideWorks.
**Current task:** FTP-01 — Database-owned historical FTP and interactive comparison. [Issue #37](https://github.com/k14krug/rideworks/issues/37).
**State:** **in_progress — focused Astra review accepted by Analyst; Gate 1 storage/consumer implementation authorized only**. No Gate 2 or production writes.
**Review accepted/merged:** [PR #39](https://github.com/k14krug/rideworks/pull/39) was merged as **documentation-only** at `2e63aaa7` and includes the focused Astra review and Analyst-authorized JIT. Dex must begin coding on a separate Gate 1 implementation branch from refreshed main.
**Implementation check:** No Gate 1 code has started. Implementation paths are unchanged from the original reviewed code; no obsolete anchor/two-class implementation needs removal.
**Review:** [Focused Astra findings](reports/FTP-01/astra-single-timeline-delta-review.md). The single historical timeline and intermediate insertion contract is technically coherent; no unresolved product decision blocks Gate 1 after Analyst reauthorization. Preserve persistent initialization state, marker-based bootstrap replay after later insertions, and coherent history/cache snapshots. Boundary insertion and correction UI choices can wait until needed.
**Controlling contract:** [Current Analyst JIT](docs/tasks/FTP-01.md) and latest issue #37 clarification: all entries share one timeline, insertion leaves existing dates/watts untouched, no origin-based classes or duplicated original dataset/audit ledger. Initial Gate 0 product assumptions are superseded.
**Verification:** Focused text/code/Git/GitHub review only; no tests, application execution or migration. Documentation-only changes; database and three FTP CSV integrity checked.
**Next action:** Dex refreshes merged main and starts a fresh `/TASK FTP-01` for **Gate 1 only**: DB timeline, safe initial import/replay, all FTP consumers and coherent caches, verification on synthetic and private-store copies. Submit implementation PR and STOP at HARD — Analyst before Gate 2.
**Restrictions:** No Gate 2 chart/editor UI, live DB write/bootstrap, deployment or CSV removal in Gate 1. Later promotion and retirement require separate JIT authorizations.
**Last completed task:** OPS-02 accepted/merged. Phase 6 deferred.
