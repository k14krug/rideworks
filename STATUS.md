# STATUS.md

**Product:** RideWorks.
**Current task:** RE-03 — Fixed-color Strava Relative Effort numbers.
**State:** `ready_for_review` — implementation complete; task remains `in_progress` pending Analyst and Owner review. [Analyst JIT](docs/tasks/RE-03.md).
**Branch:** `task/re-03-strava-relative-effort`; draft PR against `main`.
**Implementation:** Current associated Strava scores appear on Home, Activities and Activity Review using the JIT's provisional fixed bands. Bounded recent refresh skips other summary changes; score-only source revisions preserve compatible stream provenance and converge Performance and Power Curve caches.
**Verification:** 30/30 recent cycling API summaries had numeric scores (bands 0–19: 12, 20–39: 4, 40–69: 4, 70–109: 7, 110+: 3). Read-only targeted preflight: 20 compatible, zero non-score changes. Synthetic score-revision/model regressions and full Python suite: 544 passed. Synthetic browser: 254 checks across 1440, 1024, 850, 768, 650, 390 and 320 px; no client errors. Initial sandboxed suite had 21 loopback-permission errors; rerun with loopback access passed. No live activity data changed.
**Next action:** HARD — Analyst source, tests and evidence review; HARD — Owner running-UI and final threshold review. No production deployment or merge authorized.
