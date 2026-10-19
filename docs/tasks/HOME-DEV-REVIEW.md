# HOME-DEV-REVIEW — Correct verified development regressions

**Task type:** Continuation of the already-`in_progress` HOME-DEV-REVIEW task, prompted by the independent Astra review of the Home, Activity Details, Activities, Performance and Relative Effort work.

**Review reference:** Independent GPT-6 Astra findings supplied by the Owner after inspecting `dev` at `932f391` against production baseline `main` at `dcd77f1` (29 changed files). The Agent must re-fetch branches and confirm the actual PR base/head before editing; do not assume those SHAs are the current tips.

**Implementation branch:** `fix/home-dev-review-corrections` (draft PR targeting `dev`). **Never target `main` or deploy production in this task.** The development application is separately operated by the Owner.

## 1. Purpose

Resolve the confirmed technical regressions from the independent review, preserve the Owner-approved UI and Relative Effort classifications, then present verified fixes for Analyst/Owner review. The defect report found one High transaction-order regression, one Medium tablet layout failure, three Low engineering/presentation findings, and a separate Medium **calibration question that remains an Owner decision**.

## 2. Requirements Used

- Current Owner instruction: Dex may fix the five engineering items in the supplied independent review; **do not change the Relative Effort comparison model** pending separate Owner calibration decision.
- `AGENTS.md`, `TASKS.md`, `STATUS.md` and this Analyst-authored JIT.
- `docs/design/RE-01-relative-effort.md` (existing 42-day model, explicit data-quality limits).
- `docs/tasks/HOME-UI-01.md` and `reports/HOME-UI-01/dev-dashboard-cleanup-review.md` for existing dashboard/visual behavior and test coverage.
- Existing accepted Training State, dated FTP, Goal, Performance, and Planning behavior; the current tests and verification scripts.
- Personal single-rider constraints: preserve source provenance, original measurements, estimated-vs-known distinctions, existing SQLite database, and simple implementation.

## 3. Execution Control

**Allowed Invocation: `/TASK only`.**

This is an authorized engineering correction **on the named PR branch**, continuing the existing `HOME-DEV-REVIEW` task. For this continuation, refresh `origin`, verify a clean worktree and the existing PR, checkout and fast-forward the PR head, then read the current code, this JIT, the review findings, and open PR comments. If earlier generic new-task instructions suggest starting from `main`, do **not** replace the already-authorized `dev` base or silently move this PR to `main`; report any irreconcilable branch/task conflict.

**HARD — Analyst Gate:** After implementing and locally verifying the engineering corrections, stop at `ready_for_review`, push to this PR, and report results. No automatic merger.

**HARD — Owner Gate:** Relative Effort mixed-source calibration and visual acceptance are reserved for the Owner. Do not change classification logic, historical window, thresholds, evidence population, FTP treatment, or training metrics here.

## 4. Corrections in scope (priority order)

### A. HIGH — Home may block concurrent FTP edits (merge blocker)

- The added Home Relative Effort calculation writes training-stress caches before the existing expensive planning work finishes. SQLite's early writer lock can block a concurrent FTP update when caches are cold/invalidated.
- Reproduce exact existing test `test_home_get_finishes_plan_batch_before_training_summary_and_allows_ftp_write`: reported **fails on `dev`, passes on `main`** with `sqlite3.OperationalError: database is locked`.
- Restore the **existing deferred cache-write/transaction ordering**, reusing results where practical; do not solve by removing the test, widening lock timeouts, broadening transactions, permitting inconsistent cache writes, or adding unrelated infrastructure.
- Prove the concurrency test repeatedly passes with cold/invalidated caches, FTP edits remain possible, existing snapshots/evidence stay correct, and new code does not cause early writer locks.

### B. MEDIUM — Activities table broken at tablet widths (merge blocker)

- Existing five-column layout squeezes the title to ~46px at 850px, 0px at 768px/650px, and wraps ride titles into very tall columns. The mobile stacked layout begins only at 620px.
- Create a readable layout at **650, 768 and 850 CSS px**, also test 1024, 1440, 620, 390 and 320px. A sensible earlier stacked breakpoint or genuinely flexible grid is preferred; keep titles, effort category dot/text, date, type, distance/duration/power readable.
- Add a browser assertion for **minimum usable ride-title width and sane row height**, not merely whole-document overflow. Verify against the accepted layout and screenshots at tablet and mobile widths. Keep functional links and sorting/paging/filtering.

### C. LOW — Avoidable full-history Relative Effort work

- Measured on 1,420 cycling rides: warm rating scans ~0.33–0.34s and ~7,236 SQL statements on each request, whereas percentile classification itself takes ~0.008–0.009s.
- Investigate low-risk reuse **within a request** and avoiding duplicate full-history work when a page already has accepted Training State/results. If practical without increasing lock duration or altering FTP/source/model invalidation, implement the modest correction and measure before/after.
- **Transaction correctness takes priority.** Do not introduce a new persistent cache, background processing, schema change, or expanded abstraction just to chase performance. If no safe simple fix exists, document the measured tradeoff and leave it unchanged.

### D. LOW — Desktop Ride Details sidebar height

- At 1440px, Ride Summary plus collapsed Relative Effort card extended ~20px beyond Power/Heart Rate for corrected native-power and ~40px for session-estimated/HR-estimated evidence.
- Reduce combined sidebar space modestly without hiding evidence, breaking disclosure accessibility, or making text cramped. User's requirement was **ideally** matching height; report cases if it cannot be achieved cleanly. Verify on real ride/source types and narrow screens.
- Do not make fixed-height clipping, overflow hiding, or test threshold weakening the solution.

### E. LOW — Conflicting chart readout CSS

- Two identical selectors near the current `rideworks/static/style.css` chart readout styles conflict; the later rule restores unwanted top padding and 42px minimum height.
- Consolidate into one intentional compact declaration and verify browser-computed styles.

## 5. Explicit exclusions

- **Do not change Relative Effort `relative-effort-v1` classification**, its 42 prior LA-calendar-day window, midrank ties, six prior ride requirement, load-first/one-band intensity adjustment, selected stress evidence, active-duration basis, or mixed-source HR/power policy.
- Do not reinterpret HR-estimated vs power-modeled stress as equivalent by fiat. The Owner will separately review calibration; an independent sensitivity check changed **120 of 857** classifiable labels when compared only within matching method families, including one Very Light → High shift. This is a sensitivity finding, **not proof that the alternative is right**.
- No production deployment/merge, `main` changes, FTP/goal/training/planning/performance algorithm changes, Strava API changes, database migration, generalized caching infrastructure, secrets or personal source files committed.
- Do not refactor unrelated modules, delete/relax regression assertions, or fabricate success reports.

## 6. Inputs and local data

Read source and test code from current repository; the Owner-provided independent review text is the starting defect report. If a local private disposable RideWorks database snapshot is present, use it only within existing local privacy/snapshot rules; **do not copy/commit it, personal activity titles, exported files, or secrets**. If unavailable, run synthetic/fixture verification and mark real-rider checks outstanding.

## 7. Required verification and output

1. Before fixes, reproduce the concurrency and tablet defects. Capture exact commands and baseline branch/commit.
2. Add focused regression tests covering cold-cache concurrent FTP edits and 650/768/850px Activities row readability. Keep existing test semantics.
3. Execute **full Python suite** (previous independent baseline: 523 tests, 522 pass/1 error), all relevant dashboard, Activity Details, Activities/responsive and Relative Effort browser checks. Specify commands and whether tests actually ran.
4. Exercise corrected/HR/session/Strava review variants at desktop and phone widths; verify collapsible details, dynamic chart controls, goal marker/CSP, and source-data fidelity remain intact.
5. Measure any Relative Effort work reduction; clearly separate scoring time from database read/cache time.
6. On the PR, report tests passed/failed, screenshot evidence location (local-only where private), remaining limitations, exact changed files/commit, and whether both merge blockers are resolved.
7. Update `TASKS.md`/`STATUS.md` as required by repository lifecycle. Keep status `in_progress` / `ready_for_review` until Analyst acceptance.

## 8. Acceptance criteria

- The cold-cache FTP concurrency test passes and no early writer-lock regression remains.
- Activities readable at 650/768/850px and desktop/mobile; focused layout assertion proves title width/row height.
- Compact chart readout CSS no longer overridden.
- Ride sidebar improves without introducing clipping and keeps all meaningful evidence accessible.
- Any Relative Effort performance change demonstrably lowers redundant work **without** new cache invalidation or transaction defects; otherwise document deferral.
- No changes to agreed Relative Effort ratings or other model calculations.
- Full Python suite + relevant browser checks pass, or failures are explicitly reported with evidence and stop conditions; no claims for unexecuted tests.
- Analyst and Owner retain final acceptance; **leave this PR draft and do not merge without authorization**.

## 9. Stop-and-report

Stop for Analyst/Owner instruction if the concurrency fix requires redesign of the shared Training State cache, if historical model semantics would change, if responsive changes cannot preserve usable Activities, if a test reveals an unanticipated training-data discrepancy, if source/private data access is uncertain, or if the repository task/PR state conflicts with these controls.

## 10. Dex handoff

**Use GPT-6.1 Sol for implementation.** Start by reading this brief and the associated draft PR. Implement code on `fix/home-dev-review-corrections`; add focused tests, execute required checks, push back to the same PR, and stop for review. The Analyst will request an independent Astra re-review of the changed diff. The mixed-source Relative Effort calibration is a separately gated design decision, **not part of this implementation PR**.
