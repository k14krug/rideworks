# STATUS.md

**Product:** RideWorks.
**Current task:** HOME-DEV-REVIEW — engineering corrections after independent Astra review of the development UI and Relative Effort changes.
**Branch:** `fix/home-dev-review-corrections`; draft PR targets `dev`, **not** `main`.
**State:** `in_progress` — Analyst JIT committed; Dex implementation has not started. Existing development UI remains unmerged to production.

**Independent review of `dev` at `932f391`:** 523 Python tests: 522 passed, 1 `sqlite3.OperationalError: database is locked` in cold-cache Home vs FTP concurrency test (passes on `main`). Tablet Activities titles collapse at 650/768/850px. Other findings: redundant Relative Effort history DB work, slight desktop sidebar height overshoot, duplicate chart readout CSS. Browser/goal/Relative Effort correctness checks otherwise substantial.

**Controlling JIT:** [HOME-DEV-REVIEW](docs/tasks/HOME-DEV-REVIEW.md). Five engineering fixes are in scope. The separate 42-day mixed-source Relative Effort calibration decision is reserved for Owner review and **must not be implemented here**.

**Required implementation:** Dex uses GPT-6.1 Sol, refreshes origin, works on this PR branch, reproduces confirmed defects, implements small corrections, runs full Python and browser verification, records evidence and updates this PR. Do not modify `main`, merge, deploy, touch production store, or publish private ride data.

**Next action:** Dex invokes `/TASK HOME-DEV-REVIEW` on this PR branch and follows the JIT; stop with verified fixes for Analyst review and subsequent independent Astra check.
