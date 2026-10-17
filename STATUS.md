# STATUS.md

**Product:** RideWorks.
**Current task:** FTP-01 — historical FTP timeline and Performance editor. [Issue #37](https://github.com/k14krug/rideworks/issues/37).
**State:** in_progress — reconciling the Owner-approved implementation with refreshed `main`, then verifying and merging PR #41. Stop before Gate 4 production changes; task remains in_progress.
**Branch / PR:** `task/ftp-01-implementation` in `/home/kkrug/projects/rideworks-ftp01`; [PR #41](https://github.com/k14krug/rideworks/pull/41). Owner approved the feature and merge after reconciliation; production cutover requires the separate Gate 4 invocation.
**Controlling JIT:** refreshed `docs/tasks/FTP-01.md` from `main` at `c748ef9`; preserve its single-timeline/prehistory requirements and Gate 4 HARD Owner controls.
**Verified refinements:** earlier FTP from purple prehistory rides, unknown FTP before the chosen date, deliberate date confirmation for timezone-uncertain rides, smaller accessible dots, draggable date navigator, and deferred GET/cache writes with WAL. [Gate 3 refinement evidence](reports/FTP-01/gate-3-refinements.md), [Astra review](reports/FTP-01/astra-gate-3-refinements-review.md).
**Prior verification:** full suite 494 tests; Playwright 107 assertions on a disposable copy; corrected-code Astra review 88 tests and 21 browser assertions. New synthetic regressions cover Home concurrency and prehistory classification/stress/daily/Plan/cache changes.
**Preview:** http://127.0.0.1:8875/performance/ftp — isolated `local_data/ftp01/preview` with 66 FTP entries and no trial submissions.
**Live boundary:** no production DB or deployed code changes and no active FTP CSV deletion. Cutover must use the actual current live Store, include newly synced activities, retain the old release/CSV sources through bootstrap, and pair rollback database with compatible old code.
**Next action:** finish conflict resolution, targeted Astra review if behavior changes, tests/browser checks, merge PR #41, then publish the exact Gate 4 runbook and commands for Owner authorization. Do not perform Gate 4 writes/deployment/removal in this invocation.
**Last completed task:** OPS-02 accepted/merged. Phase 6 deferred.
