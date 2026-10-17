# OPS-03 — Roll out accepted RideWorks to the home-LAN production server

**Status:** pending — Analyst-authored execution brief, 2026-10-17.
**Issue:** [#44](https://github.com/k14krug/rideworks/issues/44).
**Owner direction:** After accepting FTP-01 on the development server, Owner said "Let's proceed" with updating the **separate production server** using the accepted development code and cycling history. Owner reports little or no independent activity on production; **verify**, do not assume that the production store can safely be overwritten.

## 1. Purpose and scope

Perform one controlled transfer of the already accepted RideWorks release and **a consistent snapshot of the authoritative development cycling data** to the existing private home-LAN production server. This is a small, single-rider operational rollout, not a new product feature, new synchronizer, or production architecture redesign.

**Known development source at prior handoff:**
- Checkout `/home/kkrug/projects/rideworks`, tested FTP-01 application release `cc3acc5527230bb88405b28dd1378fe6d41cde34` (merged PR #41); later `main` may contain documentation-only commits. Pin a proven application tree.
- Development SQLite `/home/kkrug/projects/rideworks/data/rideworks.sqlite3`, schema 11 after FTP-01, along with original source artifacts under the same `data/` root.
- Last accepted observation: 1,444 activities, 2,885 performance-history records, 22 Strava API activities, 66 FTP entries/revision 1 and 1,422 original activity artifacts. **These are dated observations, not invariants**: re-inventory immediately before transfer and carry forward any new development rides/FTP edits.
- Verified development *pre-FTP migration* recovery backup `/home/kkrug/rideworks-backups/ftp01/20261017T015331Z/data/`, paired with old code `92667ad`. Retain it, but **it is not the new source snapshot** for this rollout.

**Known production design, not confirmed live values:** Separate machine on a trusted HTTP home LAN, existing nginx proxy to a loopback-bound RideWorks Python service, probably managed by systemd. The documented `/srv/rideworks` path, `rideworks.lan` name and port 8766 are illustrative examples, **not discovered facts**. Find the actual server, paths, checkout, active data directory, runtime user, service, nginx public origin, and deployment method without fabricating them.

## 2. Requirements used

- [AGENTS.md](../../AGENTS.md), [TASKS.md](../../TASKS.md), [STATUS.md](../../STATUS.md), [product requirements](../PRODUCT_REQUIREMENTS.md).
- Accepted FTP-01 [PR #41](https://github.com/k14krug/rideworks/pull/41), [JIT](FTP-01.md), [issue #37](https://github.com/k14krug/rideworks/issues/37), [development Gate 4 cutover plan](../../reports/FTP-01/promotion-runbook.md), and Owner's final Gate 4 acceptance on 2026-10-17.
- Accepted OPS-01 data-home guidance, [OPS-02](OPS-02.md), [RideWorks README](../../rideworks/README.md) private home-LAN nginx/runtime section. Current production behavior/configuration must be observed rather than assumed from example configuration.
- Owner clarification: production is a **different server** from development; development should supply the initial authoritative database and related originals because production has not had meaningful independent use, subject to read-only comparison first.

## 3. Execution Control

**Allowed Invocation: `/TASK only`.**

- **Gate 1 — HARD Owner: inspect and prepare, without mutating the production server.** Dex may refresh repositories, read configuration, inspect current development/prod inventory and service/runtime state, create a consistent **development-side private transfer snapshot** after safely coordinating any source writers, and draft exact transfer/cutover/rollback commands. Remote access may require Owner action. Do not stop the production service, replace data, create a remote directory, change code or restart services in this gate. Record paths and evidence, then **STOP** for Owner confirmation of the real destination, treatment of production-only state/credentials and exact replacement plan. If read-only access is unavailable, ask the Owner for the necessary hostname/login or commands; do not invent access.
- **Gate 2 — controlled production cutover; HARD Owner final acceptance.** Enter only after separate, explicit Owner direction approving Gate 1's actual target/path/backup/configuration decision. Re-inventory for drift, stop writers/services carefully, create a **verified recovery backup of current production data/config**, stage source snapshot and artifacts, verify, atomically switch to an approved code-and-data pair, restart through the existing mechanism and smoke-check. Stop for Owner final acceptance; do not close OPS-03 automatically.
- Any unexplained production-only data, different service/source, unreadable artifact, source inconsistency, unknown auth/secret implications, insufficient storage, failed verification or unclear remote authority is a **mandatory stop**, not permission to force a copy.

No app feature, FTP model, SQLite schema, or application algorithm changes are authorized. If such changes seem necessary, stop for Analyst/Owner before expanding scope. Do not automatically continue to other tasks.

## 4. Gate 1 — read-only discovery and transfer plan

1. On development and production, identify actual host/checkout HEAD and application tree, service/process owner, systemd/nginx launch method, `RUN_PORT`, browser-facing `PUBLIC_ORIGIN`, effective `RIDEWORKS_DATA_DIR`, data directory and SQLite path. Avoid exposing host credentials, env values or tokens in tracked reports. Check live paths with runtime evidence, not a guessed `/srv/rideworks`.
2. Read-only inventory both Stores: SQLite `user_version`, integrity and FK checks, journal/WAL/SHM state, activity and FTP row counts and revisions, Strava API/sync state, user-entered FTP edits, Plan feedback/intents/classification, goals, identity sets and timestamps. Identify whether **anything** exists only on production. This is an initial copy, not a bidirectional merge. If production differs materially, stop and obtain an explicit data-retention decision before overwriting.
3. Inventory original source artifacts and all file references needed by the database. Capture a relative-path/size/SHA-256 manifest without publishing personal filenames, locations, raw payloads or tokens. A SQLite database alone is insufficient. Identify other private runtime sidecars; distinguish **data required for the copied history** from **production-host credentials/settings**.
4. Plan a **consistent SQLite snapshot using the SQLite backup API** (or stopped-writer equivalent), accounting for WAL. Do not transfer a raw live `.sqlite3` without its committed WAL content. Pair it with matching originals, track source hash/manifest; verify it opens and passes integrity/FK and reference checks before shipping.
5. Treat production `.env`, systemd, nginx `PUBLIC_ORIGIN`/port, and production-specific Strava OAuth tokens/settings as **host-specific by default**. Do not silently overwrite them with development credentials or force reauthorization. If the copied SQLite state and retained credentials cannot be used coherently, stop and propose an explicit decision. Do not run live Strava sync as a smoke test without specific permission.
6. Return a **concrete cutover report**: discovered prod host/target, inventory diff, source snapshot location, tested release commit (prefer the exact accepted code tree `cc3acc5527230bb88405b28dd1378fe6d41cde34`), backup directory, actual stop/transfer/switch/start commands, verification checks, roll-back method and unresolved choices. All private source data and settings stay outside Git. Post only privacy-safe results to issue #44, then request Owner authorization for Gate 2.

## 5. Gate 2 — after explicit target-specific Owner authorization

1. Recheck both stores for new activity/FTP/feedback/sync changes since inventory. If development has changed, prepare **a new verified current snapshot** and revise expected counts before copying. If production has changed, stop for reconciliation rather than overwrite.
2. Stop production service and sync writers through **observed** launch/systemd mechanisms. Back up production SQLite consistently, original artifacts and separate server configuration/OAuth sidecars to a restricted recovery directory; verify integrity, manifests and restorable code/config pairing. Do not delete the current environment prematurely.
3. Stage the approved, verified development SQLite snapshot + referenced originals **outside the live production data directory**, preserving original bytes/provenance. Transfer securely on the private link and verify database checksum, data rows/identities, FTP timeline/revision, artifacts, file references and permissions on destination. Keep production-specific config/credentials separate; resolve OAuth readiness before enabling background sync.
4. Checkout/update the accepted exact code commit in production. **Do not rerun FTP-01 CSV/bootstrap migration**: the transferred schema-11 database is already initialized. Preserve existing nginx/loopback and systemd configurations unless an identified mismatch requires separately approved correction. Switch the staged data into the verified production path with services stopped; prevent an unplanned new/blank Store.
5. Restart via the normal production service manager. Smoke-check the real HTTP LAN origin and Host/Origin/nonce behavior, Home, Activities/Activity Review, Performance/FTP History, Training State, Plan, Settings/Strava connection status, and a clean restart. Verify all source identities/counts and referenced originals match the transferred source snapshot. No arbitrary production FTP edits, live Strava OAuth reconnection or sync just for verification.
6. On failure: stop writers, preserve the failed state, restore matched **previous production code + its pre-cutover database/artifacts/config**; do not restore only the code against an incompatible schema or silently overwrite new post-cutover Owner activity. Document actual recovery. Retain source snapshot and recovery backups until the Owner chooses housekeeping.

## 6. Evidence, non-goals and acceptance

Gate 1: privacy-safe path/identity inventory, production-only divergence assessment, confirmed configuration/source/destination and a precise, Owner-reviewable runbook. Gate 2: actual commands and commit, backup/recovery checks, manifest/database parity, HTTPS **not required** for the existing trusted home-LAN HTTP configuration, browser/proxy smoke results and Owner final acceptance.

Non-goals: new automatic dev/prod synchronization, cloud backup service, database merge engine, Strava reauthorization workaround, port/origin security redesign, bulk historical API access, new training features, unrelated code upgrades or deletion of the FTP-01 development recovery backup.

**Done means:** the separate production server actually runs an approved RideWorks application tree with the intended development history and original artifacts, independently verified against its staged snapshot; server-specific configuration is retained or explicitly migrated, rollback is viable, and the Owner has accepted the LAN experience. The development server remains intact.
