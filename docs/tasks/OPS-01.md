# OPS-01 — Promote one authoritative RideWorks data store

**State:** **pending / awaiting Owner destination agreement**. Production readiness discussion 2026-10-12. No local data has been moved or deleted.
**Type:** Local single-rider data-operations transition, **not a change from SQLite**, schema redesign, Strava historical API acquisition, or Phase 6.
**Controlling design:** [OPS-01 one-store production plan](../design/OPS-01-production-data-home.md).
**Owner direction:** Current RideWorks interface is production-worthy; stop depending on the proliferation of `local_data/<task>` SQLite review stores in normal app use.

## Execution Control

**Allowed Invocation: `/TASK or /AUTOTASK`.**

**Gate A — Read-only inventory (Owner authorization needed to start):** Once invoked after Owner acknowledges the proposed data destination, Dex inventories active launch configuration and candidate local SQLite stores **without opening them with `Store()`** or making any writes/migrations. Identify actively used source, timeline/number of synced rides, Source/Activity/derived/goal/override counts, SQLite schema/integrity/foreign keys and original-file manifest, compare candidates/possible conflicts and present source/target recommendation. Do not reveal real activity titles, athlete data, tokens or private file paths in public commits; private report stays ignored/local. A sanitized comparative summary may be committed.

**HARD — Owner Gate B: approve authoritative SOURCE + DESTINATION before changing any data.** The user must be shown the candidate inventory and potential newer/divergent data and approve a single source and destination. Default `~/.rideworks` is recommended, **not assumed approved**. If target already contains user data, STOP rather than overwrite/merge. No blind reconciliations or deleting any `local_data` directory. Owner also approves if and how OAuth sidecar state should be carried forward without exposing secrets.

**Gate C — Promote approved store after Gate B clearance:** stop all writers, make verified rollback backup, stage complete source directory using consistent SQLite backup and exact copied/hash-verified referenced artifacts and relevant sidecar state, validate IDs, all source hashes, current sync/checkpoint, editable rider decisions and original analytical results. Prefer atomic directory publish when appropriate; preserve unchanged source for rollback. Set ordinary RideWorks startup to one expected path, remove stale `.env` data-dir override only by an intentional private local change. Ensure no silent empty database when expected production history is missing. Establish simple backup/restore instructions and verify a test restore to a disposable store, including privacy of auth state. Maintain current loopback server, SQLite, source provenance, schema/migrations and no changed training metrics.

**HARD — Analyst Gate D:** compare end-to-end post-promotion real application versus baseline on the Owner's machine, original/source bytes and history, derived performance/training state/planner/goal, Settings and Strava connection, backup/restore and safe rollback. Local real data private; full existing tests and browser checks. Return evidence for review.

**HARD — Owner Gate E:** user verifies the actual everyday launch opens all their history and settings from the single intended store, without requiring `--data-dir local_data/... `. User must positively accept production promotion. No auto-delete old stores and no merge/close before final acceptance. Future test copies still live in isolated disposable dirs and are never the normal user's app data.

## Explicit non-goals / safeguards

- No wholesale DB SQL schema migration, no new database server/account/cloud host, no automatic merging of unrelated DBs.
- No wiping old stores; keep recoverable original and rollback backup until the Owner separately approves cleanup.
- No copying/printing OAuth refresh tokens to GitHub; treat token/config files as private user data.
- No initial startup on a different empty directory and silent creation masquerading as lost ride history.
- No unapproved re-fetching, historical Strava API harvest, change of source precedence or automated training behavior.
- No assumption that a previous **1,422 original** acceptance count or a folder named `p2-05-review` is guaranteed today's authoritative current collection.
- Explicitly document launch precedence: `--data-dir` > `RIDEWORKS_DATA_DIR` environment > private checkout `.env` > `~/.rideworks`; current `.env.example` points to an old review folder and must be corrected as part of the approved production transition.

**Next step:** Owner confirms preferred durable location, then explicitly invokes `/TASK OPS-01` or `/AUTOTASK OPS-01`. Dex begins with **read-only inventory only** and stops for Gate B. Do not begin migration based on this brief alone.
