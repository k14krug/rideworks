# STATUS.md

**Product:** RideWorks.
**Current task:** HOME-UI-05 — Compact Training Overview and 90-day Power Bests.
**State:** `ready_for_review` — compact overview and bounded cached Power Curve read implemented; [verification report](reports/HOME-UI-05/implementation.md). [Analyst JIT](docs/tasks/HOME-UI-05.md).
**Branch:** `task/home-ui-05-compact-overview`.
**PR:** [#56](https://github.com/k14krug/rideworks/pull/56) (draft).
**Baseline:** HOME-UI-04 [PR #55](https://github.com/k14krug/rideworks/pull/55) merged to `main` on 2026-10-30. The Owner accepted the page as complete before selecting this further visual change.
**Goal:** Compact CURRENT STATUS rows and 90-DAY POWER BESTS (5s, 1m, 5m, 20m), calculated only from valid existing cached Virtual Ride power profiles. Avoid full-history signature validation, new data architecture or taller desktop cards.
**Verification:** 558 Python tests passed; synthetic responsive, missing-profile, desktop-height and before/after HTTP timing checks completed.
**Next action:** HARD — Analyst technical/performance review, then HARD — Owner visual approval of the running UI.
**Deployment:** Not authorized; no production Store or live service change.
