# OPS-01 — project data promotion and cleanup

**State:** Ready for **HARD — Analyst Gate 3** on existing [PR #34](https://github.com/k14krug/rideworks/pull/34). Owner Gate 4 remains open. JIT §8 is controlling; it supersedes the earlier user-home destination and cleanup deferrals. Gates 1/2 were cleared by the Analyst/Owner instructions committed on this branch. No framework conversion or new backup system.

## Delivered operation

The approved current-use source was consistently copied into **repository-root `data/`**, retaining the original source unchanged for rollback. The destination previously contained only the tracked athlete/reference resources, with no user database, originals or private sidecars. Those tracked resources remain unchanged. No prior user-home promotion had occurred.

Stopped seven known source/obsolete-preview servers before copy/deletion. Used SQLite's backup API to make one consistent database copy, copied the original artifact tree and required private Strava sidecars, and restricted production directory/database/token/settings permissions. Runtime lock and transient staging files were not copied as durable evidence.

One source/target comparison passed: integrity/FKs and schema, all **26 table counts**, **1,443 Activities**, Activity/Source/extraction/API identities and observations, saved classifications/goals/feedback/intents, sync checkpoint and cached Performance/Training State/classification/Power Curve contents. All **1,422 referenced originals** match source hashes/sizes. Private sidecar bytes match and target permissions are 0600. Source database mtime remained unchanged. No live resync, reauthorization, migration, historical reconciliation or explicit analysis rebuild was performed. Details: [sanitized evidence](promotion.json). Private source/target files and operational logs remain ignored.

## Everyday launch and missing-store behavior

- `Store.resolve_data_dir()` defaults to top-level `data/` based on the code/project root, independent of process CWD. CLI and exported environment overrides remain supported.
- Removed only stale `RIDEWORKS_DATA_DIR` assignments from ignored `.env`, preserving every other line byte-for-byte. Updated `.env.example` and current startup documentation.
- Added root-anchored `/data/` to `.gitignore`. Production SQLite, originals, token/settings and logs are ignored. Existing tracked top-level reference datasets remain tracked; packaged `rideworks/data/strava_ftp_history.csv` is not hidden by the new rule.
- Normal `serve` refuses a missing database before constructing the application. New installations can explicitly create a store through imports; disposable tests retain explicit temporary data directories.
- Executable **`start-rideworks`** starts/reuses the correct store on familiar port **8766**, opens the browser and requires no typed Python/store flags. It resolves overrides once and passes an absolute internal selection before changing the child's CWD. An occupied port serving a different store is reported, not silently reused.
- Created a **RideWorks Windows desktop shortcut** on the current WSL host. It invokes the same executable through the existing WSL distribution. The shortcut and machine-specific paths remain local. Invoked the shortcut and tested the executable from another CWD.
- Settings includes a read-only active data-folder display. No analytical or source-policy changes.

## Focused verification

**61 focused tests passed:** 17 configuration, 29 Store, two launcher and 13 Strava Settings tests. New checks cover root/CWD-independent default selection, preserving overrides, missing-store failure without filesystem creation and resolving relative overrides consistently before launch.

**26 Chromium assertions passed** across Home, Activities, Performance, Training State, Plan and Settings on the promoted store. All six pages return 200 on plain routes, retain LA calendar defaults and show substantive content; Activities shows the complete count, Settings identifies the new directory and Strava remains Connected. Browser logs/screenshots with personal content stay private.

Stopped and restarted the new server through the normal launcher from a different CWD; all six routes still return 200, the selected folder remains correct and the rollback source is present. The final running app is available through the desktop shortcut or `http://127.0.0.1:8766/`.

The accepted Stage A **453 Python / 640 Chromium** results and fixed-clock synthetic preservation evidence are retained. They were not repeated solely for relocation; focused checks cover the new default/launcher/Settings behavior. The comparison proves retained source/cached state equivalence before normal target operation; this report does not claim a new independent scientific validation of unchanged algorithms.

Commands used:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_config.py'
.venv/bin/python -m unittest discover -s tests -p 'test_rideworks.py'
.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_launcher.py'
.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_strava_settings.py'
./start-rideworks
```

Promotion, guarded cleanup, private browser assertions and restart commands are retained in ignored task operational files; they are single-use local operations, not a new migration/cleanup platform. Do not rerun the promotion script against an established target.

## Authorized cleanup and rollback

Deleted **85 obsolete test-store directories**, then removed remaining artifacts/sibling database backups in **15 known obsolete test-run parent directories**, using the existing candidate paths and path guards. Approximately **19.4 GiB** of allocated storage was reclaimed. No old database content comparison or integrity scan was repeated. Deletion did not follow symlinked originals or cross outside the ignored local-data subtree.

The approved source remains protected for rollback; original ZIP/FIT input archives and unrelated research-input folders were retained. No broad `local_data` deletion occurred. Current private OPS-01 evidence is also retained. These retained inputs/research artifacts are distinct from the obsolete SQLite test copies removed here.

Rollback: stop the new server and explicitly launch the protected old source. Its complete originals/SQLite/private sidecars remain available; no additional archive or scheduled backup job was created. Current docs list the exact production files for the Owner's existing backup strategy, including database consistency and secret handling.

## Owner-directed final research cleanup

After the Owner explicitly requested removing the remaining old research clutter,
removed **15 additional obsolete research/empty directories** and **two old logs**,
reclaiming approximately **1568.7 MiB**. This includes the old reconciliation
snapshot, temporary plotting packages, upstream reference checkout and retired
research outputs. Only original inputs, current OPS-01 private evidence and the
protected rollback source directories remain under local-data. Home and Activities
still return 200. No source archive, current production data or rollback copy was
removed; Gate 3/4 disposition remains unchanged.

## Review needed

**Analyst Gate 3:** Review the one-source/target evidence, safe default/startup and missing-store behavior, launcher/Settings changes and authorized cleanup. **Owner Gate 4:** Open the desktop shortcut and confirm familiar history, goal, correction and Strava state. Until Owner acceptance, retain the old source. After both gates, complete the already-authorized removal of that source with writers stopped; do not declare OPS-01 accepted or merge early. Phase 6 remains deferred.
