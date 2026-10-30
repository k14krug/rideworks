# STATUS.md

**Product:** RideWorks.
**Current task:** RE-03 — Fixed-color Strava Relative Effort numbers.
**State:** `ready_for_review` — data-readiness feedback addressed; task remains `in_progress` pending Analyst and Owner review. [Analyst JIT](docs/tasks/RE-03.md).
**Branch:** `task/re-03-strava-relative-effort`; [draft PR #54](https://github.com/k14krug/rideworks/pull/54) against `main`.
**Implementation:** Current associated Strava scores appear on Home, Activities and Activity Review using provisional fixed bands. Home and Activities use aligned, compact effort and ride columns; Home fits complete rows to the available card height. Bounded recent refresh skips other summary changes and converges Performance and Power Curve caches.
**Verification:** Full Python suite: 544 passed; synthetic browser: 277 checks across seven widths including aligned columns and row fit. The running application was successfully verified after the Owner-directed bounded refresh. Original activity files were not changed.
**Next action:** HARD — Analyst review and HARD — Owner running-UI and final threshold review. No production deployment or merge authorized.
