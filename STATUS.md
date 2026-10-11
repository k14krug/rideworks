# STATUS.md

**Product:** RideWorks.
**Current task:** AR-UI-01 — Owner-approved Activity Review visual redesign; `/AUTOTASK AR-UI-01` on 2026-10-11.
**State:** ready_for_review — implementation and required verification complete; stopped at HARD — Analyst Gate 1. Not accepted.
**Branch / PR:** `task/ar-ui-01-activity-review`; draft PR being opened; [issue #29](https://github.com/k14krug/rideworks/issues/29).
**Implemented:** Scoped hero/stat strip and section navigation, 380/320px interactive Power/HR chart with checked visibility controls, real compact context/next-ride/summary cards, full-width PC-01 curve, compact accepted best-20, complete grouped source/calculation disclosures. Thin/unsupported/empty modes remain explicit; unused curve plot collapses without hiding available baselines.
**Verification:** 445 Python tests; 26,343 Chromium checks across synthetic/private modes, 1440/1024/768/390/320px, keyboard and actual touch. Fixed-clock equality for 27 review modes, Performance/Training State/Plan/Dashboard, all 26 store tables and 1,422 originals (including modification times), approved FTP/Elevate, integrity/FKs. Other pages' computed geometry/colors match accepted main. [Report](reports/AR-UI-01/implementation.md).
**Running review:** `http://127.0.0.1:8791/activities`; open real FIT, retained-stream API or thin rides. Disposable retained-source copy; original accepted store untouched. Private captures/routes remain ignored. Synthetic review runs at `http://127.0.0.1:8793/activities`.
**Next action:** Analyst reviews code, real source-mode preservation, interaction and visual evidence at Gate 1. After explicit clearance, Owner reviews the running redesigned page at HARD — Owner Gate 2. PR remains draft; no acceptance/merge or next-page/Phase 6 work.
**Accepted prior work:** Phases 1–5 v1 and PC-01 remain done. Phase 6 remains deferred.
