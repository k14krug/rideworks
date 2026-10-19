# STATUS.md

**Product:** RideWorks.
**Current task:** HOME-DEV-REVIEW — accepted engineering corrections merged into `dev` on 2026-10-19.
**Branch / PR:** `dev`; [PR #46](https://github.com/k14krug/rideworks/pull/46) merged at `564df036efceeb90373da7996d8fe221367d4588`. `main` and production remain unchanged.
**State:** `done` — Analyst engineering review accepted; Owner authorized merging the corrective PR into `dev`. No further implementation work is authorized by this task.

**Corrections:** Home GET defers stress/classification cache writes until after complete response construction, preserving the concurrent FTP edit path, coherent snapshots and stale-snapshot retry. Activities at tablet widths are readable. The Activity Details sidebar spacing and compact chart readout CSS were corrected. Existing Relative Effort and other training/model calculations are unchanged.

**Verification:** Dex's implementation and fresh GPT-6.1 Sol final review both report 529 passing Python tests, 27,990 passing Chromium assertions, and full source/provenance preservation. Sol also independently verified cold/invalidated concurrent FTP edits, transaction rollback/response consistency, signature-aware reuse and tablet geometry. Independent review: [PR review 5573052946](https://github.com/k14krug/rideworks/pull/46#pullrequestreview-5573052946). Private evidence remains local only. The Analyst inspected the source and review but did not run these suites separately.

**Deferred / separate decisions:** Whole-history Relative Effort warm scan optimization is deferred (~0.3–0.4s for 1,420 rides). Mixed HR/power Relative Effort calibration and final development UI/production acceptance remain Owner decisions. The final reviewer suggested optional committed tests for response snapshot bytes and two-batch rollback; scratch probes passed and this is nonblocking. Firefox/WebKit, physical-device and screen-reader testing were not performed.

**Evidence:** [Post-Plan concurrency report](reports/HOME-DEV-REVIEW/post-plan-concurrency.md), [correction report](reports/HOME-DEV-REVIEW/corrections.md), [task brief](docs/tasks/HOME-DEV-REVIEW.md). No production merge/deployment or local development-process restart was performed during the PR review/merge.

**Next action:** Owner pulls updated `dev` and restarts the development app for visual acceptance. Separately review the mixed-source Relative Effort calibration question before approving that model for production. Do not merge `dev` into `main` or deploy without explicit Owner authorization.
