# STATUS.md

**Product:** RideWorks.
**Current task:** RE-02 — Relative Effort UI verification and integration.
**State:** `pending` — Owner has authorized proceeding with the existing Relative Effort model; the Analyst-authored [JIT](docs/tasks/RE-02.md) and [task register](TASKS.md) are committed on `main`. Dex has **not** been invoked by this handoff.
**Starting branch:** refreshed `main`; implementation should use a new task branch and a draft PR targeting `main`. Use `dev` as the feature reference only.
**Owner decision (2026-10-29):** Accept practical mixed-source effort colors; power typically for indoor and HR-estimated stress for outdoor rides. Do not conduct additional calibration research or change `relative-effort-v1`. [Recorded on PR #52](https://github.com/k14krug/rideworks/pull/52).
**Scope:** Verify Home Recent Activities dots, Activities effort column and Activity Review compact card; transplant the minimum compatible changes without disturbing newer accepted Home UI (HOME-UI-02/03) or training calculations. Verify tablet/mobile and Home/FTP concurrency behavior. No broad `dev` merge, production deployment, or Store mutation.
**Last completed task:** HOME-UI-03 was accepted and merged to `main` via [PR #51](https://github.com/k14krug/rideworks/pull/51) on 2026-10-29. It remains accepted and must be preserved.
**Next action:** Owner invokes `/TASK RE-02` with Dex. Dex must fetch origin, verify a clean checkout and current main, read AGENTS.md/TASKS.md/STATUS.md and the JIT, then begin the task. After implementation and required tests, hand off a draft PR for HARD — Analyst review. HARD — Owner final running-UI acceptance and authorization are required before merging to `main` or deployment.
