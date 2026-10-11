# STATUS.md

**Product:** RideWorks.
**Current task:** PC-01 — Power-duration curves; invoked `/AUTOTASK PC-01` on 2026-10-11.
**State:** blocked — mandatory stop during source-contract preflight, before feature implementation; not ready for Gate 1 acceptance.
**Branch:** `task/pc-01-power-curves`; draft PR pending creation, linked to [issue #27](https://github.com/k14krug/rideworks/issues/27).
**Finding:** Accepted best-20 ignores native timer events. One accepted window includes 127 samples strictly after a paired stop on a file with contradictory timer/session durations. Separately, excluding a terminal stop sample changes a fully verified source's best-20 value. PC-01 requires timer-aware continuity and exact accepted 1,200-second parity; the endpoint and contradictory-source policies need explicit Analyst clarification.
**Evidence:** [Read-only preflight report](reports/PC-01/timer-contract-preflight.md), [aggregate](reports/PC-01/timer-contract-preflight.json), reproducible diagnostic; 416 full tests / four focused synthetic tests pass. All 1,022 current-policy eligible native results match independent/native/cached best-20; 1,422 artifacts retain approved hashes, SQLite integrity/FKs pass. Original evidence and accepted product code remain unchanged.
**Next action:** Analyst resolves the PC-01 timer/endpoint contract in the JIT (Owner numerical-policy decision if required), then a permitted invocation resumes implementation. No automatic continuation, task acceptance, merge or Phase 6 work.
**Accepted prior work:** Phases 1–5 v1 remain done, including Performance-v2, Training State v4 and rolling Plan. Phase 6 remains deferred.
