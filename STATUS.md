# STATUS.md

**Product:** RideWorks.
**Current task:** FTP-01 — historical FTP timeline and Performance editor. [Issue #37](https://github.com/k14krug/rideworks/issues/37).
**State:** in_progress — refreshed-main reconciliation and verification passed; publishing the reconciled PR head and Astra report, then merging PR #41 as Owner-authorized. Stop before Gate 4 production changes; task remains in_progress.
**Branch / PR:** `task/ftp-01-implementation` in `/home/kkrug/projects/rideworks-ftp01`; [PR #41](https://github.com/k14krug/rideworks/pull/41). Owner approved the feature and merge after reconciliation; production cutover requires the separate Gate 4 invocation.
**Controlling JIT:** refreshed `docs/tasks/FTP-01.md` from `main` at `c748ef9`; preserve its single-timeline/prehistory requirements and Gate 4 HARD Owner controls.
**Verified refinements:** earlier FTP from purple prehistory rides, unknown FTP before the chosen date, deliberate date confirmation for timezone-uncertain rides, smaller accessible dots, draggable date navigator, and deferred GET/cache writes with WAL. [Gate 3 refinement evidence](reports/FTP-01/gate-3-refinements.md), [Astra review](reports/FTP-01/astra-gate-3-refinements-review.md).
**Verification:** full suite 494 tests; Playwright 107 assertions on a separate disposable copy; JavaScript syntax and diff checks passed. Fresh-context Astra passed the focused main-reconciliation review at `94ea203`; prior corrected-code Astra review passed 88 tests and 21 browser assertions. See [reconciliation verification](reports/FTP-01/main-reconciliation-verification.md).
**Preview:** http://127.0.0.1:8875/performance/ftp — isolated `local_data/ftp01/preview` with 66 FTP entries and no trial submissions.
**Live boundary:** no production DB changes, deployment or active FTP CSV deletion. Current read-only check: schema 10, 1,444 Activities, no FTP tables; the live store and launch details are documented in [the Gate 4 runbook](reports/FTP-01/promotion-runbook.md). Cutover must use this actual current Store, retain the old release/CSV sources through bootstrap, and pair rollback database with compatible old code.
**Next action:** publish and merge the reconciled PR #41, then report its exact GitHub main merge commit and prepared Gate 4 commands. Stop for the separate Owner-directed Gate 4 invocation before any live write, deployment or CSV removal.
**Last completed task:** OPS-02 accepted/merged. Phase 6 deferred.
