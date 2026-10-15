# STATUS.md

**Product:** RideWorks.
**Current task:** FTP-01 — Database-owned FTP history and editable 20-minute comparison, [issue #37](https://github.com/k14krug/rideworks/issues/37).
**State:** in_progress — **Gate 0 Astra independent review accepted by Analyst; revised JIT authorizes Gate 1 only.**
**Branch / review:** [Draft PR #38](https://github.com/k14krug/rideworks/pull/38) documents the independent review and revised [FTP-01 JIT](docs/tasks/FTP-01.md). Gate 0 review at [reports/FTP-01/astra-gate-0-review.md](reports/FTP-01/astra-gate-0-review.md).
**Approved next action:** After review documentation/revised JIT reaches main, Dex refreshes origin and uses a fresh `/TASK FTP-01`. Work only on Gate 1 (storage/consumer changes and private-copy tests), then stop at HARD — Analyst. Gate 2 chart/editor and source-file retirement staging require explicit subsequent Analyst authorization.
**Not authorized:** No production database bootstrap/write, live deployment, FTP CSV deletion from the running checkout, or silent transition to Gate 2. Final production bootstrap must precede deployment of DB-only release, with separate Owner approval and matching-code/DB rollback.
**Analyst decisions recorded:** SQLite retains original 66 FTP observations plus edit history; all eligible ride points including unknown-FTP cases are selectable; comparison uses unrounded 95% of best-20; Performance houses FTP History; future-dated editor entries excluded initially; Planning literal target watts unchanged; remove the third retired root FTP CSV along with the two approved input CSVs at final cutover (no archive dataset).
**Last completed task:** OPS-02 accepted and merged in PR #36. Separate private-LAN deployment/provider callback checks remain open. Phase 6 stays deferred.
