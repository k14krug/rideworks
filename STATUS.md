# STATUS.md

**Product:** RideWorks.
**Current task:** **OPS-03 — initial separate production-server rollout**, [JIT](docs/tasks/OPS-03.md), [issue #44](https://github.com/k14krug/rideworks/issues/44).
**State:** **pending — Owner requested production rollout preparation on 2026-10-17**. No remote production inspection or data transfer has been performed by this task.
**Previous task:** FTP-01 done and Owner-accepted on the development server at tested release `cc3acc5527230bb88405b28dd1378fe6d41cde34`; schema 11, 66 starting FTP values, 1,444 activities and 1,422 original artifacts at the accepted handoff (counts may change). Keep its verified pre-migration backup and worktree.
**Source environment:** normal development checkout `/home/kkrug/projects/rideworks`, data root `/home/kkrug/projects/rideworks/data`. Verify before staging a fresh consistent snapshot.
**Destination environment:** separate production server on trusted home HTTP LAN behind nginx. **Actual host, checkout, service, data path, and production-only changes not yet established.** README `/srv/rideworks` etc. are examples only.
**Execution:** `/TASK OPS-03` only. Gate 1 = read-only production inventory, comparative source/destination review, development snapshot and exact transfer/backup/rollback runbook; STOP at HARD Owner confirmation of actual target before any production write/overwrite. Gate 2 = controlled code/data update only under later explicit Owner direction; stop for final Owner acceptance.
**Next action:** Dex reads refreshed JIT/issue and discovers actual production configuration, using Owner assistance if remote access is needed. No speculative remote writes, OAuth changes or Strava sync. Phase 6 remains deferred.
