# OPS-01 — Move RideWorks from disposable review stores to one everyday data home

**Status:** Owner direction to simplify production data handling, 2026-10-12; proposal for approval and local inventory, **no live-store migration performed**.
**Scope:** Production-operating/data-directory transition for this **one private rider on one PC**, separate from completed visual HOME-UI-01 and deferred Phase 6.
**Owner question:** Now that RideWorks feels production-worthy, why are many `local_data/<task>` folders each holding their own SQLite database, and can we move away from that practice?

## 1. What is true today

- `Store(data_dir)` already operates on **one SQLite database inside the selected directory**: `rideworks.sqlite3`, immutable `originals/`, staging and local source-dependent state. This is **one logical store**, not one database per feature.
- `rideworks.config.startup_config` chooses data directory by **`--data-dir` > exported `RIDEWORKS_DATA_DIR` > checkout-local ignored `.env` > default `~/.rideworks`**. `Store.resolve_data_dir()` defaults to user-home `~/.rideworks`, independent of repository working directory. **If no store exists, Store creates its directories and a new blank database**; a silent fresh store could look like missing history to a user.
- Early `rideworks/README.md` and `.env.example` still show `local_data/p1-03-review`; recent reports use `local_data/p2-05-review`, `p4-02-baseline/store`, `p5-01-` and task-specific copied stores for isolated schema/algorithm/browser experiments. This was an **intentional disposable verification pattern**: reports describe consistent SQLite backups plus copied/hash-verified originals. It does **not** establish which store is the newest canonical one on the Owner's PC.
- A store can also contain **`.strava-tokens.json`**, `.strava-settings.json`, sync checkpoint in SQLite, user-entered activity classifications/intent/leg feedback/annual goal and other derived caches. Treat OAuth tokens as private secrets. Files under ignored `local_data/` are not in Git; no Git history can identify which local copy contains the most recent unsynced user actions.

## 2. Recommended operating model

**Recommendation:** Keep the existing standard-library SQLite store and copied original source artifacts. Pick **ONE authoritative private data directory outside the repository** for everyday RideWorks, with `~/.rideworks` as the **preferred default** unless the Owner has a strong preference for another stable local disk directory.

The code checkout/repository holds the application; the permanent user-home data directory holds the one authoritative `rideworks.sqlite3`, originals, local settings and current private Strava token. Development and test still use explicitly designated **disposable** directories to validate change, never the everyday store. This is a **development workflow distinction**, not a new product architecture. There is no need for PostgreSQL, cloud services, container orchestration, user accounts, multiple schemas or background synchronization.

**Other options and trade-offs:** 
- Stay in one named `local_data/production` folder: simpler relative to today's tools, but still inside a Git checkout and prone to accidental path changes/copy collisions/repository deletion.
- Use a fixed user-chosen folder outside repo (e.g. on a separate local disk): reasonable if there are backup/storage preferences, but requires a deliberate selected path and reliable startup config.
- Default `~/.rideworks`: already supported, independent of checkout and low implementation risk, though initially hidden to nontechnical users. Expose the currently active store path/role in **Settings or a concise read-only startup diagnostic** so the Owner always knows which database is open.

## 3. Minimum promotion workflow (no guessed sources or destructive cleanup)

### Stage A: Read-only inventory and candidate recommendation — **HARD Owner source selection**
1. On the Owner's PC, **without invoking `Store()` on candidates** (it auto-migrates/creates databases), enumerate existing likely local stores and the effective running-server store: its resolved path, schema version, readable SQLite integrity, source/artifact counts and hashes, latest synchronized ride/date, latest sync checkpoint, user corrections/goal/feedback, and whether a private token/config file exists **by presence only**. Never print token contents or full private ride labels/titles; output a **sanitized comparative matrix** locally.
2. Distinguish stored snapshots, testing fixtures and current actively used directory. **Recommend one likely most-complete/latest source** based on evidence rather than folder name or highest counter. If stores diverge, document missing/newer work and a bounded reconciliation plan: no blind SQLite file concatenation or assumption that rows/IDs line up.
3. Confirm whether target `~/.rideworks` already exists and contains data; **never overwrite an existing directory**, merge OAuth tokens between copies, or auto-select solely because the default path is empty. Return precise source/target choices to Owner **for approval before any copy or startup redirection**.

### Stage B: Safe one-time promotion after Owner approval
1. **Stop the local web process and any writers**. Capture a recoverable immutable baseline snapshot of the selected original store (SQLite-consistent database copy/backup, referenced `originals/` with hash manifest, relevant private sidecars/settings/tokens; protect secrets). Prefer a separate backup disk/location. Retain the original directory unchanged.
2. Stage a **complete copy** at a new target path (rather than moving or only copying `rideworks.sqlite3`), verify schema/integrity/foreign keys, all DB-referenced original artifact checksums, Activity and Source identities/counts, latest ride and user settings/classifications, sync checkpoint, profile/20-minute/training/planner outputs, and private token file existence/permissions. Do **not** assume earlier accepted 1,422 artifact count is still today's current total.
3. Point a single documented normal launcher to the target (ideally using the default `~/.rideworks` and no `--data-dir`; scrub stale checkout `.env` override **only with explicit private local change**). Verify actual displayed store path or read-only status plus source summary; run Home, Activities, Performance, Training State, Plan and Settings; check Strava connection without gratuitous reauthorization or history fetch.
4. **Rollback path:** stop application and point it back to unchanged source if verification fails; do not delete/corrupt target/source automatically. Only the Owner decides whether old, *unreferenced disposable* testing folders may be archived or deleted later.

### Stage C: Production everyday defaults
- Make the launch experience short/repeatable: one command/shortcut, one explicit user-facing **active data directory** readout, one authoritative path. Avoid confusing `local_data/<phase>` examples in current quick-start and `.env.example`.
- Add the **smallest reliable backup + test-restore workflow** for both SQLite and original files plus the sensitive small files needed for sync. Manual backups are acceptable initially; off-machine copies materially protect against disk loss. Any scheduled backup is a separate opt-in after recovery is verified.
- Separate disposable test data from main operation: tests create temporary stores, never select production by inherited config; verification uses read-only or copied snapshots.
- **Do not add a 'production mode' framework** without a concrete necessity. A missing expected data store should be obvious (not silently initialize an apparently empty history) after promotion, while explicit first-run creation must remain possible for a future true new installation.

## 4. What is *not* approved by this design note

No data migrations or `local_data/` deletion today; no choice of an authoritative current store without local evidence/Owner confirmation; no Strava token printing/duplication, no unsanctioned re-sync or historical fetch; no changes to training calculations, source provenance, FTP history, PC-01, Plan, or image UI. No public 'production hosting' or remote network access. User-home store, simple local loopback web server and SQLite are sufficient for this single-rider product.

**Decision requested next:** Agree to `~/.rideworks` (or supply another stable outside-repo local path) as permanent destination, then authorize Dex to perform **Stage A read-only inventory first**, reporting the best candidate and conflicts before copying.
