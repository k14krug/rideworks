# FTP-01 proposed production promotion and rollback

**Not executed. Gate 3 Owner authorization and a separate Gate 4 invocation are required.** The implementation PR is unreleased. Preview/test copies are never production replacements.

## Designated inputs

- Current protected store: `/home/kkrug/projects/rideworks/data/rideworks.sqlite3`, with its original artifacts and private sidecars under that same data directory. Reconfirm the running service uses this path immediately before cutover; stop if it differs.
- Old release checkout: `/home/kkrug/projects/rideworks`, currently `92667ad` (schema 10). Record the actual deployed commit and launch command at cutover; do not assume the current branch proves what a running process loaded.
- Approved original import sources, still available in the active checkout: `data/athlete/strava_ftp_history.csv` and `rideworks/data/strava_ftp_history.csv`, both SHA-256 `cb990c18e969d0d12f1d524bea22cf8b596746171f179f6241748394b87ad073`. They contain the same 66 entries. The retired root `ftp-history.csv` is not an import source.
- Proposed new code: the exact Owner-approved final commit of PR #41, checked out separately from the active release. Record that commit in the cutover evidence. Do not substitute an unreviewed moving branch.

The October 16 handoff check found a new synced Activity after the rehearsal snapshot, while production remains schema 10 without FTP tables. This reinforces the requirement to use a fresh production backup and the actual current store at cutover; preview/rehearsal copies must never replace it.

## Authorized cutover sequence (future work)

1. Confirm explicit Owner authorization for the target database, code revision, backup location, active CSV removal and launch method. Record the running service/launcher and all database writers. Stop only those writers, including manual sync; verify they remain stopped. This runbook does not assume a systemd unit name or change nginx configuration.
2. Make a timestamped private backup of the **current** production data directory, including original artifacts, SQLite via its supported backup API, and private settings/OAuth sidecars. Pair it with the old application commit/environment. Verify SQLite integrity/foreign keys and table/artifact manifests. Rehearse opening a restored backup with the matching old code. Keep credentials private and do not copy them into reports.
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
