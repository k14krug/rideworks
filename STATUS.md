# STATUS.md

**Product:** RideWorks.
**Current task:** HOME-DEV-REVIEW — Owner-directed verification of committed Home dashboard cleanup (2026-10-17).
**Branch:** `dev`; no new branch or PR. No merge to `main` or production deployment authorized.
**State:** ready_for_review — verification complete; awaiting Owner review of the running development app.
**Verification:** 499 Python tests passed with command-scoped `DEBUG=0`; synthetic dashboard Chromium acceptance passed after correcting stale test expectations. Six fixed-clock cases preserve FTP, Training State, Plan, Performance and mileage/goal outputs, allowing the seventh recent ride; 27 table fingerprints equal `main`. All 1,422 referenced originals pass hash/size validation; schema 11, 66 FTP entries.
**Browser:** 996 Chromium assertions passed at 1440/1024/768/390/320px, including keyboard/touch, actual values, Home/Plan agreement and disclosures; no overflow or JavaScript errors. Desktop/phone screenshots inspected privately.
**Concurrent updates:** Preserved the three remote annual target-pace commits through `b57ea98`; restarted only development with its original environment. Final 499-test/synthetic/model checks passed again, plus 61 final browser checks across all five widths for the updated wording and retained cleanup.
**Development application:** `http://127.0.0.1:8766/`, existing `.venv/bin/python -m rideworks serve` process from this checkout, default `data/` store. Already serves the committed cleanup.
**Evidence:** [Development verification report](reports/HOME-UI-01/dev-dashboard-cleanup-review.md); private screenshots/snapshots under ignored `output/playwright/home-cleanup-review/` and `local_data/home-cleanup-review/`.
**Context:** Owner reports FTP-01 deployed to the separate production server. This task does not inspect or change that server; prior OPS-03 handoff is superseded as the current action by this development-only request. Retain existing FTP-01 recovery backup/worktree.
**Next action:** Owner reviews `http://127.0.0.1:8766/`. Stop here; no merge to `main` or production deployment until explicit approval. Phase 6 remains deferred.
