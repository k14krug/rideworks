# FTP-01 proposed production promotion and rollback

**Not executed. The Owner has approved the feature and authorized merging PR #41 after safe reconciliation and verification. Live migration, deployment and CSV retirement remain stopped pending the separate Gate 4 invocation.** Preview/test copies are never production replacements.

## Designated inputs

- Current protected store: `/home/kkrug/projects/rideworks/data/rideworks.sqlite3`, with originals and private sidecars under that data directory. **Read-only reconfirmed 2026-10-16:** the active process PID 431278 has working directory `/home/kkrug/projects/rideworks`, command `.venv/bin/python -m rideworks serve`, and listens on `127.0.0.1:8765`; `.env` supplies `RUN_PORT=8765`. It was started from the interactive VS Code terminal (TTY `pts/8`), not a RideWorks systemd service. Its command has no `--data-dir` or `RIDEWORKS_DATA_DIR`; `Store.resolve_data_dir()` resolves to `/home/kkrug/projects/rideworks/data`, so the database path is `/home/kkrug/projects/rideworks/data/rideworks.sqlite3`. Immediately before Gate 4, re-identify the process, cwd, database target and all sync writers; stop if any differ.
- Live database read-only observation 2026-10-16: SQLite schema version 10, journal mode `delete`, no FTP tables, 1,444 Activities, 2,885 performance-history rows and 22 Strava API activities. This is newer than the 1,443-Activity rehearsal snapshot. Use the actual current store and make a fresh backup; do not replace it with a preview/rehearsal copy.
- Old release code: the running process started while checkout HEAD was `92667ad`; the local checkout was later fast-forwarded to `c748ef9` for the documentation-only PR #42 update. `rideworks/` application source is identical between these commits. For rollback use matched code commit `92667ad` plus the verified pre-cutover schema-10 backup, after reconfirming the actual running version at cutover.
- Proposed approved code to activate: reconciled PR #41 head `94ea2036115d784344b016264ab3a18f84a4f277`; verify after GitHub merge that the resulting `main` merge commit has the same tree, then use that exact GitHub merge commit for deployment. Do not deploy a moving branch or a different/unreviewed tree.
- Approved original import sources, still available in the active checkout: `data/athlete/strava_ftp_history.csv` and `rideworks/data/strava_ftp_history.csv`, both SHA-256 `cb990c18e969d0d12f1d524bea22cf8b596746171f179f6241748394b87ad073`. They contain the same 66 entries. The retired root `ftp-history.csv` is not an import source.
- Proposed new code: the exact Owner-approved final commit of PR #41, checked out separately from the active release. Record that commit in the cutover evidence. Do not substitute an unreviewed moving branch.

The October 16 handoff check found a new synced Activity after the rehearsal snapshot, while production remains schema 10 without FTP tables. This reinforces the requirement to use a fresh production backup and the actual current store at cutover; preview/rehearsal copies must never replace it.

### Backup destination and exact proposed commands

The proposed private backup destination is `/home/kkrug/rideworks-backups/ftp01/<UTC-cutover-id>/data/`, with `<UTC-cutover-id>` generated at cutover as `YYYYMMDDTHHMMSSZ`. This destination does not exist yet; it will be created mode `0700` only after the separate Gate 4 invocation. The home filesystem had 857 GiB available at the read-only check, versus a 668 MiB live data directory. Set `umask 077`; include the entire data directory (database via SQLite's backup API, originals, staging, reports, FTP input sources, and private `.strava-*` settings) and keep backup material outside Git. If the chosen destination is unavailable or not private, stop and obtain a new Owner-approved destination rather than silently substituting the preview.

The following commands are a proposal for a later, separately authorized Gate 4 invocation. They have **not** been run. Recheck the process/database/writers first; if the observed PID, cwd, port, schema, paths, sources, or code differ from this record, stop and refresh the proposal.

1. Stop the current app by pressing Ctrl-C in the existing RideWorks terminal (currently PID 431278 / TTY `pts/8`). Confirm it has exited and that no manual sync or other writer is running. Confirm port 8765 is no longer listening. Do not stop or kill a PID until its command and cwd have been rechecked.

2. Make a private backup. This copies non-database files from the stopped live data directory and makes a consistent SQLite backup through the API; it does not overwrite or replace the live Store:

   ```bash
   set -euo pipefail
   umask 077
   DATA=/home/kkrug/projects/rideworks/data
   BACKUP_ROOT=/home/kkrug/rideworks-backups/ftp01
   CUTOVER_ID="$(date -u +%Y%m%dT%H%M%SZ)"
   BACKUP="$BACKUP_ROOT/$CUTOVER_ID"
   install -d -m 700 "$BACKUP_ROOT" "$BACKUP" "$BACKUP/data"
   python3 - "$DATA" "$BACKUP/data" <<'PY'
   from pathlib import Path
   import shutil, sqlite3, sys
   source, target = Path(sys.argv[1]), Path(sys.argv[2])
   db_name = 'rideworks.sqlite3'
   for item in source.iterdir():
       if item.name == db_name or item.name.startswith(db_name + '-'):
           continue
       out = target / item.name
       if item.is_dir(): shutil.copytree(item, out, symlinks=True)
       elif item.is_symlink(): out.symlink_to(item.readlink())
       else: shutil.copy2(item, out)
   src = sqlite3.connect(source.joinpath(db_name).as_uri() + '?mode=ro', uri=True)
   src.execute('PRAGMA query_only=ON')
   dst = sqlite3.connect(target / db_name)
   src.backup(dst)
   dst.close(); src.close()
   (target / db_name).chmod(0o600)
   print('SQLite backup complete; non-database data directory copied.')
   PY
   ```

3. Before migration, verify the backup and recorded inventory. This exact check reports only aggregate metadata and stops unless both source and backup pass integrity, foreign-key, schema and table/row-count parity:

   ```bash
   python3 - "$DATA/rideworks.sqlite3" "$BACKUP/data/rideworks.sqlite3" <<'PY'
   import sqlite3, sys
   def inspect(path):
       db=sqlite3.connect('file:'+path+'?mode=ro',uri=True)
       db.execute('PRAGMA query_only=ON')
       db.execute('BEGIN')
       integrity=[r[0] for r in db.execute('PRAGMA integrity_check')]
       foreign=list(db.execute('PRAGMA foreign_key_check'))
       version=db.execute('PRAGMA user_version').fetchone()[0]
       tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
       counts={name:db.execute('SELECT COUNT(*) FROM "'+name.replace('"','""')+'"').fetchone()[0] for name in tables}
       db.rollback(); db.close()
       return integrity,foreign,version,tables,counts
   live,backup=map(inspect,sys.argv[1:3])
   assert live[0]==backup[0]==['ok'] and not live[1] and not backup[1]
   assert live[2]==backup[2]==10 and live[3:]==backup[3:]
   print('PASS: schema 10, integrity/foreign keys clean, table names and row counts identical')
   PY
   python3 - "$DATA" "$BACKUP/data" <<'PY'
   from pathlib import Path
   from hashlib import sha256
   import json, sys
   def manifest(root):
       out={}
       for p in sorted(root.rglob('*')):
           if p.name=='rideworks.sqlite3' or p.name.startswith('rideworks.sqlite3-'):
               continue
           if p.is_symlink(): value='symlink:'+str(p.readlink())
           elif p.is_file(): value='file:'+sha256(p.read_bytes()).hexdigest()
           else: continue
           out[str(p.relative_to(root))]=value
       return out
   left,right=map(lambda p:manifest(Path(p)),sys.argv[1:3])
   assert left==right, 'non-database file manifest differs'
   digest=sha256(json.dumps(sorted(left.items()),separators=(',',':')).encode()).hexdigest()
   print(f'PASS: {len(left)} non-database files match; manifest SHA-256 {digest}')
   PY
   ```

   Compare non-database files byte-for-byte using a relative-path/SHA-256 manifest on source and destination (excluding `rideworks.sqlite3` and its SQLite sidecars, which were captured with the backup API); record only the total file count and overall manifest hash. Confirm private `.strava-*` sidecars are present with restrictive permissions. Record the backup DB hash, and test opening a private restored copy with old code commit `92667ad`. Stop on any mismatch.

4. Bootstrap the actual live data directory from the two approved, still-present sources while the old checkout and app files are still active. Run the command from the reconciled PR #41 worktree at the reviewed commit (after verifying the GitHub merge tree):

   ```bash
   cd /home/kkrug/projects/rideworks-ftp01
   env -u DEBUG /home/kkrug/projects/rideworks/.venv/bin/python -m rideworks.ftp_history \
     --target-dir /home/kkrug/projects/rideworks/data \
     --source /home/kkrug/projects/rideworks/data/athlete/strava_ftp_history.csv \
     --mirror /home/kkrug/projects/rideworks/rideworks/data/strava_ftp_history.csv
   ```

   The expected result is `imported=true`, 66 entries, revision 1. Validate the exact ordered rows against both byte-identical approved files, the durable completion marker, schema/integrity, no changes to unrelated tables or original artifacts, and fixed-clock calculation parity. Do not use the 52-row root `ftp-history.csv`. Stop before activation or CSV removal on any unexpected database/source state or mismatch.

5. Only after successful migration/parity and another check that the exact source tree equals reviewed PR head `94ea203...`, activate the GitHub merge commit whose tree was verified equal. Preserve the current `.venv` and `.env`; the normal command remains:

   ```bash
   cd /home/kkrug/projects/rideworks
   git fetch origin main
   git checkout --detach <verified-GitHub-merge-commit>
   .venv/bin/python -m rideworks serve
   ```

   The application launch is intentionally unchanged; `.env` sets `RUN_PORT=8765`. This exact code checkout removes the two approved active FTP CSVs, the obsolete root FTP CSV and its unused loader only after the SQLite import has passed. Verify the expected removals with `git status --short`, no packaged/runtime FTP CSV dependency, then smoke Home, Performance/FTP History, Training State, Plan, Activity Review, restart, and database/source preservation. Keep sync writers stopped through final smoke and Owner review.

6. On failure after activation, stop the new app and all writers, make a separate SQLite-API snapshot of the failed live database in `$BACKUP/failed-live/`, and retain it for diagnosis. If no new Owner data has been written, restore the verified pre-cutover database while the app is stopped: preserve the failed database/sidecars, remove only obsolete live `-wal`/`-shm` sidecars after confirming no connections remain, then atomically replace `rideworks.sqlite3` with the backup copy. The replacement operation is:

   ```bash
   DATA=/home/kkrug/projects/rideworks/data
   install -d -m 700 "$BACKUP/failed-live"
   python3 - "$DATA/rideworks.sqlite3" "$BACKUP/failed-live/rideworks.sqlite3" <<'PY'
   import sqlite3, sys
   src=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True)
   src.execute('PRAGMA query_only=ON')
   dst=sqlite3.connect(sys.argv[2])
   src.backup(dst)
   dst.close(); src.close()
   PY
   rm -f "$DATA/rideworks.sqlite3-wal" "$DATA/rideworks.sqlite3-shm" "$DATA/rideworks.sqlite3-journal"
   install -m 600 "$BACKUP/data/rideworks.sqlite3" "$DATA/rideworks.sqlite3.rollback.tmp"
   mv -f "$DATA/rideworks.sqlite3.rollback.tmp" "$DATA/rideworks.sqlite3"
   git -C /home/kkrug/projects/rideworks checkout --detach 92667ad
   cd /home/kkrug/projects/rideworks
   .venv/bin/python -m rideworks serve
   ```

   **Do not run the shown sidecar removal/restore commands until the separate Gate 4 invocation and a confirmed no-writer state.** Confirm the two approved source files are present after old-code checkout. If any new FTP entry, activity, sync result or other Owner data was written after cutover, do **not** overwrite it with the older backup; stop for Owner/Analyst reconciliation before rollback. Code and schema must always be restored as a matched pair.

## Authorized cutover sequence (future work)

1. Confirm explicit Owner authorization for the target database, code revision, backup location, active CSV removal and launch method. Record the running service/launcher and all database writers. Stop only those writers, including manual sync; verify they remain stopped. This runbook does not assume a systemd unit name or change nginx configuration.
2. Make a timestamped private backup of the **current** production data directory, including original artifacts, SQLite via its supported backup API, and private settings/OAuth sidecars. The RideWorks Store now uses persistent SQLite WAL mode; never copy an open `rideworks.sqlite3` file alone or omit its active `-wal` state. Prefer the SQLite backup API after writers are stopped, then verify integrity/foreign keys and table/artifact manifests. Pair the backup with the old application commit/environment and rehearse opening a restored backup with the matching old code. Keep credentials private and do not copy them into reports.
3. Record current ordered FTP input parity and fixed-clock baseline calculations using the old code on a backup copy. Abort if the source inputs fail the approved checksum/equality check, the target is unexpected, or competing writers remain.
4. From the approved new-code checkout, run the explicit import against the **actual designated store** while both approved source files are still available in the old checkout:

   ```bash
   /home/kkrug/projects/rideworks/.venv/bin/python -m rideworks.ftp_history \
     --target-dir /home/kkrug/projects/rideworks/data \
     --source /home/kkrug/projects/rideworks/data/athlete/strava_ftp_history.csv \
     --mirror /home/kkrug/projects/rideworks/rideworks/data/strava_ftp_history.csv
   ```

   The first source path above is the repository's `data/athlete` file, not an activity source or replacement dataset. Run the command with the new checkout as working directory; do not run it before the explicit Gate 4 invocation.
5. Verify schema/initialization, exact ordered 66-entry import, durable completion marker, numerical parity, unchanged unrelated tables and original manifests. A completed replay must be a no-op. Stop on conflicting/partial/unexpected state; never repair it by replacing production with a rehearsal database.
6. Activate only the approved DB-only release using the recorded normal launch method and existing data directory. This is the point at which the reviewed CSV removals take effect in the active source/package/deployment. Remove the obsolete active root FTP CSV/loader as staged in the reviewed change; retain no replacement archive CSV. Historical Git commits remain history. Verify package contents and active runtime imports.
7. Smoke-check Home, Performance/FTP History, Training State, Plan, Activity Review and restart. Confirm all existing FTP dates/watts remain unchanged; a visual check alone must not create a production insertion. Reconfirm integrity/source preservation, document timings and any recovery actions, then stop for Owner final acceptance.

## Failure and rollback

Keep writers stopped if bootstrap, parity, activation or smoke checks fail. Preserve the failed database separately before recovery. Restore the verified pre-cutover production backup **and its matching old code/configuration together**, then verify the restored pages and manifests. Old schema-10 code rejects schema 11; reverting code alone and decrementing `user_version` are not recovery plans. Do not overwrite new Owner edits with an older backup without a separate decision. No automatic retries that restore the original 66 over later entries.

All commands here are a reviewable proposal. The successful rehearsal evidence uses private copies only and does not establish that live deployment or final acceptance has happened.
