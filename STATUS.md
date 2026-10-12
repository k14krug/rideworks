# STATUS.md

**Product:** RideWorks.
**Current task:** HOME-UI-01 — app-wide visual refinement; `/AUTOTASK HOME-UI-01` resumed 2026-10-12.
**State:** **ready_for_review — reopened HARD — Analyst Gate 1.** All expanded-scope pages are implemented and locally verified. `TASKS.md` remains `in_progress`; holistic HARD — Owner Gate 2 and final acceptance remain pending.
**Branch / PR:** `task/home-ui-01-dashboard`; [draft PR #32](https://github.com/k14krug/rideworks/pull/32); [issue #31](https://github.com/k14krug/rideworks/issues/31). Current implementation head is recorded on the PR.
**Implemented:** Activities, both Performance views, Training State, Plan and Settings share compact typography, scoped palette, 14px main cards and restrained blue accents. Training State preserves its full 600px desktop / 400px mobile plot. Confirmed Plan completion retains green. Refined Home and Activity Review remain styling anchors; accepted data, charts, source evidence and controls are preserved.
**Verification:** 446 Python tests; 15,435 counted Chromium assertions; standalone Performance, synthetic Dashboard and fake OAuth/Settings suites pass. Retained/synthetic/empty pages at 1440/1024/768/390/320px, filters, forms, keyboard/touch, before/completed Plan, chart interactions and no overflow. Six fixed-clock cases preserve 36 page states, models, all 26 tables / 1,422 originals and approved FTP/Elevate references. Home/Activity Review before/after styles and geometry match. [Report](reports/HOME-UI-01/implementation.md).
**Running review:** `http://127.0.0.1:8801/?home_tz=America%2FLos_Angeles` (disposable retained-source copy); synthetic preview `http://127.0.0.1:8803/`. Original accepted store untouched; private captures/routes/snapshots stay ignored.
**Next action:** Analyst reviews the complete cross-page pass in PR #32 at reopened Gate 1; then Owner reviews the unified running app at Gate 2. No implementation blocker. Keep PR draft/unmerged and issue open until acceptance; do not start another task.
**Accepted prior work:** AR-UI-01 and Phases 1–5 / PC-01 are done. Phase 6 remains deferred.
