# STATUS.md

**Product:** RideWorks.
**Current task:** HOME-UI-05 — Compact Training Overview and 90-day Power Bests.
**State:** `pending` — Owner selected the compact two-column Home mockup and requested implementation on 2026-10-30. [Analyst JIT](docs/tasks/HOME-UI-05.md) is committed to `main`; no HOME-UI-05 implementation has begun.
**Baseline:** HOME-UI-04 [PR #55](https://github.com/k14krug/rideworks/pull/55) merged to `main` on 2026-10-30. The Owner accepted the page as complete before selecting this further visual change.
**Goal:** Compact CURRENT STATUS rows and 90-DAY POWER BESTS (5s, 1m, 5m, 20m), calculated only from valid existing cached Virtual Ride power profiles. Avoid full-history signature validation, new data architecture or taller desktop cards.
**Next action:** Owner supplies the private approved mockup and invokes `/TASK HOME-UI-05` (or `/AUTOTASK HOME-UI-05`). Dex refreshes `main`, reads the JIT and current sources, implements on a task branch, runs accuracy/performance/browser checks, and opens a draft PR. Stop at HARD — Analyst and HARD — Owner gates.
**Deployment:** Not authorized; no production Store or live service change.
