# STATUS.md

**Product:** RideWorks.
**Current task:** FTP-01 — Database-owned FTP history and editable 20-minute chart.
**State:** ready_for_review — Gate 0 findings only; implementation has not begun.
**Branch:** `task/ftp-01-astra-review`; [draft PR #38](https://github.com/k14krug/rideworks/pull/38); [issue #37](https://github.com/k14krug/rideworks/issues/37).
**Review:** [Independent Astra report](reports/FTP-01/astra-gate-0-review.md), reviewed `main` at `a85ff5a` under the unchanged [FTP-01 JIT](docs/tasks/FTP-01.md). Astra finds the objective feasible but the brief not ready to authorize implementation.
**Required decisions:** Migration/promotion/CSV-removal order and matching-code rollback; retained original observations/edit lineage; missing-FTP/chart/date semantics; all downstream consumers/cache consistency; explicit copy-store verification and rollout authorization. Astra recommends two implementation review gates.
**Verification:** Read-only code, requirements, issue and local metadata review; no execution tests or migration rehearsal. Only documentation changed. Protected database and FTP-source integrity checked before publication.
**Next action:** Owner/Analyst accepts or amends Gate 0 findings and commits an Analyst-authored revised brief explicitly authorizing implementation. Resume only with a fresh `/TASK FTP-01`; no coding, production write or CSV cleanup is authorized now.
**Last completed task:** OPS-02 accepted and merged in [PR #36](https://github.com/k14krug/rideworks/pull/36). Private-LAN deployment/provider callback checks remain a separate follow-up. Phase 6 stays deferred.
