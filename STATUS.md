# STATUS.md

**Product:** RideWorks.
**Current task:** HOME-UI-06 — Race Avg W on Home Recent Activities. [Analyst JIT](docs/tasks/HOME-UI-06.md) · [Issue #62](https://github.com/k14krug/rideworks/issues/62).
**State:** `done` — HARD — Analyst Gate 1 and HARD — Owner Gate 2 accepted on 2026-11-08 for application code `027e4624f174e8c575df80daad87905573071bc2`.
**Acceptance:** [Analyst technical review](https://github.com/k14krug/rideworks/pull/63#issuecomment-6728718848); [Owner running-UI approval and merge/production authorization](https://github.com/k14krug/rideworks/pull/63#issuecomment-6728858759).
**PR / merge:** [PR #63](https://github.com/k14krug/rideworks/pull/63) merged into `main` as `fb4685eff8ebe55330c9143680be5cb06999f66b`. The accepted application change is `027e462`; later closeout commits changed documentation only.
**Verification:** 642 Python tests and synthetic browser checks across 1440, 1280, 1100, 768, 740, 620, 390 and 320px. At desktop widths the card dimensions and fully visible row count were unchanged; smaller widths use taller, scrollable stacked rows accepted by Owner. [Implementation report](reports/HOME-UI-06/implementation.md).
**Data:** Active race-result `Race Avg W` remains distinct from Activity `Avg Pwr`; missing, removed and null race watts show a dash; no schema, import, training model or source-data changes.
**Release:** Owner explicitly authorized merge and production rollout. Actual production deployment is the responsibility of the **separate production Dex** on the production server, not this development closeout. Do not copy dev data, trigger a paid extraction, auto-import races or mutate production history.
**Next action:** Owner's separate production Dex deploys the approved merged release with verified backup, safe restart and smoke checks. No additional HOME-UI-06 coding, reviews or automatically started tasks.
