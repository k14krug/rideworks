# STATUS.md

**Product:** RideWorks.
**Current task:** FTP-01 — historical FTP timeline and Performance editor. [Issue #37](https://github.com/k14krug/rideworks/issues/37).
**State:** ready_for_review — Gates 1 and 2 passed; **STOPPED at Gate 3 — HARD Owner**. Task remains in_progress.
**Branch / PR:** `task/ftp-01-implementation` in `/home/kkrug/projects/rideworks-ftp01`; [draft PR #41](https://github.com/k14krug/rideworks/pull/41). Implementation reviewed at `832eac0`; original active checkout remains on the old release.
**Reviews:** Distinct fresh-context Astra technical passes: [Gate 1](reports/FTP-01/astra-gate-1-technical-review.md) at `662e954`, [Gate 2](reports/FTP-01/astra-gate-2-technical-review.md) at `832eac0`. Both affirmative, no unresolved material findings; these are technical passes, not Owner acceptance.
**Verification:** [Gate 1 evidence](reports/FTP-01/gate-1-implementation.md); [Gate 2 evidence](reports/FTP-01/gate-2-implementation.md). 488 final regression tests, 70 browser assertions, independent reviewer regressions, installed-wheel/empty-store checks, numerical parity, insertion/replay/restart/rollback, and preservation of 24 non-cache tables / 1,422 artifacts on private copies passed.
**Safe preview:** http://127.0.0.1:8875/performance/ftp — private `local_data/ftp01/preview`, original 66 entries, no trial insertions or OAuth credentials. Preview is a point-in-time copy, never a production replacement.
**Live boundary:** No task production writes, deployment, merge or active FTP CSV deletion. Three active CSV hashes are unchanged. [Final read-only check](reports/FTP-01/live-state-at-handoff.json) found one new synced ride after the rehearsal snapshot; live remains schema 10 with no FTP tables. The unreleased branch alone stages CSV removal.
**Next action:** Owner reviews the running preview and [exact promotion/rollback proposal](reports/FTP-01/promotion-runbook.md). Live work needs explicit Gate 3 authorization and a separate Owner-directed Gate 4 invocation; use a fresh backup of the actual then-current store. Do not automatically resume or merge.
**Last completed task:** OPS-02 accepted/merged. Phase 6 deferred.
