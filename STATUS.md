# STATUS.md

**Product:** RideWorks.
**Current task:** FTP-01 — Database-owned historical FTP and interactive comparison. [Issue #37](https://github.com/k14krug/rideworks/issues/37).
**State:** **blocked for targeted Astra review of clarified product requirements**, not authorized for further Gate 1 coding until cleared.
**Owner clarification (2026-10-14):** **All entries are simply historical FTP values.** Original imported values are the starting 66 entries, not a privileged or read-only class. Later manually selected/adjusted entries belong to that same chronological history. The main action is inserting intermediate date/watt values; inserting must leave prior entries unchanged. No special imported-vs-supplemental classes, provenance UI, immutable anchor policy, duplicate original dataset or elaborate edit audit.
**Revised JIT:** [docs/tasks/FTP-01.md](docs/tasks/FTP-01.md). Earlier [Astra Gate 0 findings](reports/FTP-01/astra-gate-0-review.md) remain valid for bootstrap safety, consumers, cache coherence and verification, but product assumptions requiring origin-based classes are superseded.
**Next action:** Dex refreshes main, checks whether Gate 1 implementation has already begun and identifies conflicting work. Ask Astra for **brief targeted delta review** of the corrected single-history model; return findings and STOP for Analyst clearance before resumed Gate 1 storage/consumer implementation. Do not rerun broad research.
**Gate restrictions:** No Gate 2 graph UI yet; no live production DB write/bootstrap, deployment or CSV removal without later authorization. First migrate current production successfully and verify rollback before final DB-only cutover. All three FTP CSVs removed at completion, no archival copy.
**Last completed task:** OPS-02 accepted/merged. Phase 6 deferred.
