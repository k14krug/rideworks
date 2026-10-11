# STATUS.md

**Product:** RideWorks.
**Current task:** PC-01 — Power-duration curves; invoked `/AUTOTASK PC-01` on 2026-10-11.
**State:** ready_for_review — implementation complete under `/AUTOTASK PC-01`; stopped at HARD — Analyst Gate 1. Not accepted.
**Branch / PR:** `task/pc-01-power-curves`; [draft PR #28](https://github.com/k14krug/rideworks/pull/28), linked to [issue #27](https://github.com/k14krug/rideworks/issues/27).
**Implemented:** Cached source-qualified multi-duration MMP; Performance keeps default 20-Minute History and adds independent period curves; Activity Review defaults to its own preceding 42 days with no future leakage. Exact anchor inspection, source links, native/API provenance and JIT §13 timer handling. Incremental normal-sync/explicit updates; short read snapshots and atomic publication preserve page availability during rebuild.
**Verification:** 440 full / 24 focused Python tests; 1,959 Chromium checks plus native desktop/mobile capture inspection. All 122,112 duration results independently verified; exact 1,022 native / seven API best-20 parity. 1,443 cached profiles / 1,271 with power, ~23 s forced build / 0.37 s unchanged build. 18 concurrent accepted-page checks pass. All 20 source tables / 1,422 originals, approved FTP/Elevate and same-clock Performance/Training State/Plan preserved. [Review report](reports/PC-01/implementation.md).
**Running review copy:** `http://127.0.0.1:8782/performance?curve=1`; contributing Activity links show prior-six-week overlays. Original accepted store untouched; screenshots/private route remain ignored locally.
**Next action:** Analyst reviews actual code, source/parity, cache/scale, preservation and visual evidence at Gate 1. After explicit clearance, present the running feature at HARD — Owner Gate 2. PR stays draft; no acceptance, merge or Phase 6 work.
**Accepted prior work:** Phases 1–5 v1 remain done, including Performance-v2, Training State v4 and rolling Plan. Phase 6 remains deferred.
