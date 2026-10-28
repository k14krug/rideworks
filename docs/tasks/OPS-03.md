# OPS-03 — Roll out accepted RideWorks to the home-LAN production server

**Status:** **done — production rollout complete and Owner-accepted on 2026-10-28.** The Owner explicitly directed that OPS-03 be marked done and issue #44 closed, with no further deployment, verification or Analyst review.
**Issue:** [#44](https://github.com/k14krug/rideworks/issues/44).

## Owner-directed closure — controlling record (2026-10-28)

The Owner's explicit closure decision supersedes the earlier requirements to collect additional closeout evidence and obtain independent Analyst acceptance for OPS-03 only. No deployment, production access, verification, Analyst review or new closeout task remains requested. Do not resume either rollout gate or automatically begin another task.

**Historical evidence gaps:** Detailed Gate 1/2 approvals, the actual deployed commit and data treatment, backup/recovery checks and smoke/verification results are not documented in the reviewed repository and issue records. Independent Analyst acceptance of OPS-03 is not recorded; the recorded acceptance of the FTP-02 feature is separate. Closure records the Owner's decision and does not claim undocumented checks were performed or passed, nor establish whether each historical step was performed.

The remainder of this brief is retained as the historical rollout specification, including its original invocation, gates, acceptance criteria and stop conditions. It is not authorization or a request to repeat deployment or verification.

---

**Owner direction:** On 2026-10-17 Owner requested transferring accepted RideWorks code/history to the **separate production server**. On 2026-10-27 Owner explicitly requested deploying the newer FTP-02 release `613b0dccc6cc653ac3500b26ce9f292ac5e86037`. Owner reports little or no independent activity on production; **verify**, do not assume that the production store can safely be overwritten. Release selection is not approval of an undisclosed destination or destructive data replacement.

## 1. Purpose and scope

Deploy the now accepted FTP-02 release to the existing private home-LAN production server, and transfer a consistent snapshot of authoritative development cycling data **only if read-only inventory and the Owner-approved cutover plan establish that transfer is intended and safe**. A strictly code-only update is appropriate when the existing production data is already the desired coherent schema-11 history and the Owner elects to preserve it. This is a small, single-rider rollout, not a new synchronizer or production architecture redesign.

**Known development source at prior handoff:**
- Checkout `/home/kkrug/projects/rideworks`; accepted deployment **code release is now `613b0dccc6cc653ac3500b26ce9f292ac5e86037`** (merged FTP-02 PR #48). Previous `cc3acc5527230bb88405b28dd1378fe6d41cde34` is the accepted FTP-01 baseline **only**, not the current release target. Pin the exact approved application tree; do not substitute unaccepted `dev` commits or blindly deploy latest HEAD.
- Development SQLite `/home/kkrug/projects/rideworks/data/rideworks.sqlite3`, schema 11 after FTP-01, along with original source artifacts under the same `data/` root.
- Last accepted observation: 1,444 activities, 2,885 performance-history records, 22 Strava API activities, 66 FTP entries/revision 1 and 1,422 original activity artifacts. **These are dated observations, not invariants**: re-inventory immediately before transfer and carry forward any new development rides/FTP edits.
- Verified development *pre-FTP migration* recovery backup `/home/kkrug/rideworks-backups/ftp01/20261017T015331Z/data/`, paired with old code `92667ad`. Retain it, but **it is not the new source snapshot** for this rollout.

**Known production design, not confirmed live values:** Separate machine on a trusted HTTP home LAN, existing nginx proxy to a loopback-bound RideWorks Python service, probably managed by systemd. The documented `/srv/rideworks` path, `rideworks.lan` name and port 8766 are illustrative examples, **not discovered facts**. Find the actual server, paths, checkout, active data directory, runtime user, service, nginx public origin, and deployment method without fabricating them.


### Release reconciliation — controlling amendment (2026-10-27)

This amendment supersedes the old FTP-01-only release target everywhere in OPS-03 and issue #44. The chosen code is **exact commit `613b0dccc6cc653ac3500b26ce9f292ac5e86037`**, the GitHub merge of the Owner-authorized FTP-02 implementation. FTP-02 is independently accepted by the Analyst based on the reviewed patch and Dex's recorded disposable-data test/browser evidence; this is not a claim that the Analyst reran Dex's suite. No schema upgrade or FTP data rewrite is needed merely to enable after-last manual entries: FTP-02 reuses the schema-11 timeline and its existing history revision/signature invalidation.

The Owner's request to deploy the newer commit is **release-selection authorization**, not a substitute for the existing Gate 1 **exact-target** approval. The report that production is currently running `cc3acc5` is useful preliminary evidence, not a complete inventory of service path, database, production-only history, artifacts, credentials, and rollback. Dex must finish or refresh that inventory and present the actual cutover plan. A code-only update (preserve production data) may be simpler than the original first-copy plan but cannot be silently chosen if the Owner still expects development data to replace production. No production service stop or filesystem write before Gate 2 approval.

## 2. Requirements used

- [AGENTS.md](../../AGENTS.md), [TASKS.md](../../TASKS.md), [STATUS.md](../../STATUS.md), [product requirements](../PRODUCT_REQUIREMENTS.md).
- Accepted FTP-01 [PR #41](https://github.com/k14krug/rideworks/pull/41), [JIT](FTP-01.md), [issue #37](https://github.com/k14krug/rideworks/issues/37), [development Gate 4 cutover plan](../../reports/FTP-01/promotion-runbook.md), and Owner's final Gate 4 acceptance on 2026-10-17.
- **FTP-02**, [JIT](FTP-02.md), [issue #47](https://github.com/k14krug/rideworks/issues/47), merged [PR #48](https://github.com/k14krug/rideworks/pull/48) and Analyst acceptance recorded on PR #48 on 2026-10-27. Dex reports 24/497 tests on the PR branch, 30/532 on dev integration, and 17 Chromium checks on each disposable Store. The Analyst reviewed code and evidence but did not rerun the full test suite.
- Accepted OPS-01 data-home guidance, [OPS-02](OPS-02.md), [RideWorks README](../../rideworks/README.md) private home-LAN nginx/runtime section. Current production behavior/configuration must be observed rather than assumed from example configuration.
- Owner clarification: production is a **different server** from development; development should supply the initial authoritative database and related originals because production has not had meaningful independent use, subject to read-only comparison first.

## 3. Execution Control

**Allowed Invocation: `/TASK only`.**

- **Gate 1 — HARD Owner: inspect and prepare, without mutating the production server.** Dex may refresh repositories, read configuration, inspect current development/prod inventory and service/runtime state, create a consistent **development-side private transfer snapshot** after safely coordinating any source writers, and draft exact transfer/cutover/rollback commands. Remote access may require Owner action. Do not stop the production service, replace data, create a remote directory, change code or restart services in this gate. Record paths and evidence, then **STOP** for Owner confirmation of the real destination, treatment of production-only state/credentials and exact replacement plan. If read-only access is unavailable, ask the Owner for the necessary hostname/login or commands; do not invent access.
- **Gate 2 — controlled production cutover; HARD Owner final acceptance.** Enter only after separate, explicit Owner direction approving Gate 1's actual target/path/backup/configuration decision. Re-inventory for drift, stop writers/services carefully, create a **verified recovery backup of current production data/config**, stage source snapshot and artifacts, verify, atomically switch to an approved code-and-data pair, restart through the existing mechanism and smoke-check. Stop for Owner final acceptance; do not close OPS-03 automatically.
- Any unexplained production-only data, different service/source, unreadable artifact, source inconsistency, unknown auth/secret implications, insufficient storage, failed verification or unclear remote authority is a **mandatory stop**, not permission to force a copy.

No **further** app feature, FTP model, SQLite schema, or application algorithm changes are authorized as part of OPS-03. Deploying already accepted FTP-02 at the exact pinned commit is authorized as a release update; modifying its code or adding other features is not. If additional changes seem necessary, stop for Analyst/Owner before expanding scope. Do not automatically continue to other tasks.

## 4. Gate 1 — read-only discovery and transfer plan

1. On development and production, identify actual host/checkout HEAD and application tree, service/process owner, systemd/nginx launch method, `RUN_PORT`, browser-facing `PUBLIC_ORIGIN`, effective `RIDEWORKS_DATA_DIR`, data directory and SQLite path. Avoid exposing host credentials, env values or tokens in tracked reports. Check live paths with runtime evidence, not a guessed `/srv/rideworks`.
2. Read-only inventory both Stores: SQLite `user_version`, integrity and FK checks, journal/WAL/SHM state, activity and FTP row counts and revisions, Strava API/sync state, user-entered FTP edits, Plan feedback/intents/classification, goals, identity sets and timestamps. Identify whether **anything** exists only on production. This is an initial copy, not a bidirectional merge. If production differs materially, stop and obtain an explicit data-retention decision before overwriting.
3. Inventory original source artifacts and all file references needed by the database. Capture a relative-path/size/SHA-256 manifest without publishing personal filenames, locations, raw payloads or tokens. A SQLite database alone is insufficient. Identify other private runtime sidecars; distinguish **data required for the copied history** from **production-host credentials/settings**.
4. Plan a **consistent SQLite snapshot using the SQLite backup API** (or stopped-writer equivalent), accounting for WAL. Do not transfer a raw live `.sqlite3` without its committed WAL content. Pair it with matching originals, track source hash/manifest; verify it opens and passes integrity/FK and reference checks before shipping.
5. Treat production `.env`, systemd, nginx `PUBLIC_ORIGIN`/port, and production-specific Strava OAuth tokens/settings as **host-specific by default**. Do not silently overwrite them with development credentials or force reauthorization. If the copied SQLite state and retained credentials cannot be used coherently, stop and propose an explicit decision. Do not run live Strava sync as a smoke test without specific permission.
6. Return a **concrete cutover report**: discovered prod host/target, inventory diff, whether the Owner should keep production data unchanged or deliberately replace it with a fresh development snapshot, exact accepted **release `613b0dccc6cc653ac3500b26ce9f292ac5e86037`**, source snapshot location **if a data copy is needed**, backup directory, actual stop/transfer/switch/start commands, verification checks, rollback method and unresolved choices. All private source data and settings stay outside Git. Post only privacy-safe results to issue #44, then request Owner authorization for Gate 2.

## 5. Gate 2 — after explicit target-specific Owner authorization

1. Recheck both stores for new activity/FTP/feedback/sync changes since inventory. If development has changed, prepare **a new verified current snapshot** and revise expected counts before copying. If production has changed, stop for reconciliation rather than overwrite.
2. Stop production service and sync writers through **observed** launch/systemd mechanisms. Back up production SQLite consistently, original artifacts and separate server configuration/OAuth sidecars to a restricted recovery directory; verify integrity, manifests and restorable code/config pairing. Do not delete the current environment prematurely.
3. **Follow the Owner-approved data disposition.** For a code-only rollout, keep the production SQLite database/original artifacts in place (after consistent backup and integrity checks), without copying or overwriting development data. For an explicitly authorized data replacement, stage the verified development SQLite snapshot plus referenced originals **outside the live production data directory**, preserving original bytes/provenance; transfer securely and verify database checksum, row identities, FTP timeline/revision, artifacts, file references and permissions. Keep production-specific config/credentials separate; resolve OAuth readiness before enabling background sync.
4. Checkout/update **the accepted exact code commit `613b0dccc6cc653ac3500b26ce9f292ac5e86037`** in production, not the older `cc3acc5` FTP-01 release or later unreviewed branch tips. **Do not rerun FTP-01 CSV/bootstrap migration**: the existing or transferred schema-11 FTP history must already be initialized. Preserve existing nginx/loopback and systemd configurations unless a confirmed mismatch requires separately approved correction. For an authorized data replacement only, switch staged data into the verified production path with services stopped; prevent an unplanned new/blank Store.
5. Restart via the normal production service manager. Smoke-check the real HTTP LAN origin and Host/Origin/nonce behavior, Home, Activities/Activity Review, Performance/FTP History, Training State, Plan, Settings/Strava connection status, and a clean restart. Verify all source identities/counts and referenced originals match the transferred source snapshot. No arbitrary production FTP edits, live Strava OAuth reconnection or sync just for verification.
6. On failure: stop writers, preserve the failed state, restore matched **previous production code + its pre-cutover database/artifacts/config**; do not restore only the code against an incompatible schema or silently overwrite new post-cutover Owner activity. Document actual recovery. Retain source snapshot and recovery backups until the Owner chooses housekeeping.

## 6. Evidence, non-goals and acceptance

Gate 1: privacy-safe path/identity inventory, production-only divergence assessment, confirmed configuration/source/destination and a precise, Owner-reviewable runbook. Gate 2: actual commands and commit, backup/recovery checks, manifest/database parity, HTTPS **not required** for the existing trusted home-LAN HTTP configuration, browser/proxy smoke results and Owner final acceptance.

Non-goals: new automatic dev/prod synchronization, cloud backup service, database merge engine, Strava reauthorization workaround, port/origin security redesign, bulk historical API access, **additional unapproved** training features, unrelated code upgrades, `dev` branch changes or deletion of the FTP-01 development recovery backup.

**Done means:** the separate production server actually runs an approved RideWorks application tree with the intended development history and original artifacts, independently verified against its staged snapshot; server-specific configuration is retained or explicitly migrated, rollback is viable, and the Owner has accepted the LAN experience. The development server remains intact.
