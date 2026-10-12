# STATUS.md

**Product:** RideWorks.
**Current task:** AR-UI-01 — Owner-approved Activity Review visual redesign; `/TASK AR-UI-01` on 2026-10-11.
**State:** **done — AR-UI-01 accepted 2026-10-11**. Analyst reviewed code/verification evidence and the Owner approved the running compact-header layout; both hard gates accepted.
**Branch / PR:** `task/ar-ui-01-activity-review`; [draft PR #30](https://github.com/k14krug/rideworks/pull/30); [issue #29](https://github.com/k14krug/rideworks/issues/29).
**Implemented:** Compact plain header; duplicate jump buttons/divider removed, smaller title/local date and consolidated type/source attribution; four aligned metrics (2×2 on phones). Existing five section links, chart/summary, Power Curve above Workout Context and Current next ride, best-20 and complete source disclosures retained. CSS stays scoped to Activity Review.
**Verification:** Header/navigation 212–217px on real desktop source modes; chart 149–195px higher in captured FIT/API/thin rides. Desktop/mobile before/after captures compared; no overflow and all section links work at 1440/1024/768/390/320px. Final rerun: 445 Python tests, 24,304 Chromium checks including keyboard/touch, forms, charts, source states and unrelated-page geometry. Fixed-clock equality for 27 review modes, accepted models, all 26 store tables and 1,422 originals including mtimes and approved FTP/Elevate. [Report](reports/AR-UI-01/implementation.md).
**Running review:** `http://127.0.0.1:8791/activities`; open real FIT, retained-stream API or thin rides. Disposable retained-source copy; original accepted store untouched. Private captures/routes remain ignored. Synthetic review runs at `http://127.0.0.1:8793/activities`.
**Next action:** Merge accepted PR #30 and close issue #29. Explore a separate Home/dashboard redesign; no implementation of other pages as part of AR-UI-01. Phase 6 remains deferred.
**Accepted prior work:** Phases 1–5 v1 and PC-01 remain done. Phase 6 remains deferred.
