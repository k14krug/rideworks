# STATUS.md

**Product:** RideWorks.
**Current task:** HOME-UI-03 — Home Mileage by Year card, **pending**. Analyst-authored [JIT](docs/tasks/HOME-UI-03.md) and [TASKS.md](TASKS.md) entry are on main; Dex has not started.
**State:** **pending — awaiting Owner invocation** via /TASK HOME-UI-03 or /AUTOTASK HOME-UI-03 (both authorized by the JIT).
**Baseline:** HOME-UI-02 is accepted, closed and merged as [PR #50](https://github.com/k14krug/rideworks/pull/50). P3-01 and HOME-UI-01 remain accepted.
**Scope:** Replace Home Annual Mileage Goal with compact three-year cumulative Mileage by Year, current YTD, miles remaining and ceil(existing needed-weekly) text; preserve accepted goals, provenance and all other pages/cards. Private Owner mockup must be supplied to Dex directly and must not be committed.
**Next action:** Ken passes the approved mockup to Dex and invokes the authorized task command. Dex must refresh origin, check clean worktree, fast-forward main, read AGENTS/TASKS/STATUS/JIT and relevant sources, create a task branch, then implement and open a PR. HARD — Analyst technical review and HARD — Owner running-UI acceptance before done. No production access/deployment authorized.
