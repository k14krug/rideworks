# FTP-01 Gate 3 feedback refinements

**State:** Implementation and local verification complete; separate fresh-context Astra review is pending. Owner visual review remains the Gate 3 stop. All database experiments used synthetic or isolated private copies.

## Behavior

- An eligible purple prehistory ride can seed a new earliest FTP entry. The insertion keeps every existing date/value, makes FTP unknown before the new effective date, and hands the prior earliest interval back to its original entry. Empty-history initialization, duplicate dates, and dates after the latest setting remain rejected.
- A timezone-uncertain ride does not prefill a date. The user must explicitly choose or confirm the effective calendar date before saving.
- Ride markers are smaller and lighter. Larger transparent hit targets preserve mouse/touch selection; chart points remain keyboard focusable/selectable. The date navigator uses draggable range and pan controls, remains synchronized with exact From/To and Reset controls, and does not overwrite an FTP draft.
- Dynamic GETs use a coherent deferred read snapshot rather than reserving SQLite's writer slot at request start. SQLite remains in WAL mode so a normal writer can commit during long page calculations. A single `SQLITE_BUSY`/locked read-to-write cache upgrade retries the page once from a fresh snapshot.

## Concurrency evidence

Two synthetic multi-ride GETs were paused after the first ride had completed and while a later calculation was in progress. For `/training-state`, the request paused after ride two; for `/plan`, it paused at classification two, after both stress calculations. In both cases the two cache tables were still empty, and a concurrent FTP insertion committed before the calculations resumed (0.0028 seconds for Training State; 0.0033 seconds for Plan). No WAL writer lock was held across the remaining ride/classification work.

At the final batch-upgrade boundary the original read snapshot had become stale. SQLite rejected the batch; the request transaction rolled back, and `Application.get` retried once. Both rides recalculated (four calculation/classification calls total across the first attempt and retry), both responses returned HTTP 200 using the new 250 W FTP, and only retry results with nonempty per-ride input signatures were committed. Cold synthetic GETs took 0.0767 seconds for Training State and 0.0628 seconds for Plan. The batch keeps the existing signature formulas and their history inputs unchanged.

The Home route had an additional ordering hazard: it previously called the Training State summary first, flushing stress cache rows before Plan performed its more expensive activity-classification loop. Home now renders Plan first; its deferred stress and classification batches are the last database-writing calculation. `dashboard()` and `training_home()` were checked for any later cache writes; dashboard is read-only, and Training State reads Plan's just-populated cache. A two-ride cold Home regression pauses during classification two, confirms neither cache table has rows, and commits a competing FTP change in 0.0034 seconds. Home then rolls back its stale batch, retries all four calculations on a coherent snapshot, and writes current-signature stress/classification rows. Cold Home GET took 0.0813 seconds.

A synthetic integration regression starts with a Nov 8 2024 ride before the earliest Nov 9 FTP. Before insertion, FTP comparison is unavailable and power stress reports `ftp_unavailable`. Adding 190 W effective Nov 8 leaves Nov 7 unknown and preserves both existing FTP rows. The ride then compares at 190 W (95% of its measured 200 W best-20), receives the below-recorded-FTP classification, selects recorded power stress instead of HR fallback, and changes daily stress/Fitness/Fatigue. Training State and Plan expose the new dated FTP; stress and classification input signatures both change.

A rollback-journal baseline held a read snapshot while a second connection attempted the same ordinary FTP write with a 100 ms busy timeout. The write failed with `database is locked` after 0.103 seconds. Deferred `BEGIN` alone cannot permit a rollback-journal writer to commit during a long calculation; WAL is the small tested correction for that contention.

The persistent WAL mode means a live database may have `-wal` and `-shm` sidecars. The promotion runbook now requires the SQLite backup API after writers stop and forbids copying only the open main database file. The existing read-only inventory tool previously refused WAL. It now copies a stable database/WAL pair to private temporary storage before inspecting it, never opens or writes the source through SQLite, fingerprints the source main/WAL/SHM/journal files before and after, and refuses incomplete, changing, or unsupported states. Regression tests verify it includes committed WAL data while source file bytes and metadata remain unchanged.
See [concurrency evidence](gate-3-concurrency.json).

## Verification

- `env -u DEBUG PYTHONPATH=tests /home/kkrug/projects/rideworks/.venv/bin/python -m unittest discover -s tests` — **494 tests passed**.
- `node --check rideworks/static/ftp.js` — passed.
- Playwright CLI browser verification (`npx --offline --yes --package @playwright/cli playwright-cli --session ftp01check run-code --filename tools/verify_ftp_browser.js`) — **107 assertions passed**, including prehistory and timezone-uncertain selection, navigator dragging/panning at exact x=60/970 track bounds, draft preservation, full/one-day/middle-range keyboard movement, live slider ARIA values, mobile widths/touch, filtering, and existing save/revision/security behavior. The disposable copy contained 1,029 eligible candidate rides (135 above, 744 at/below, and 150 FTP-unavailable); it had 71 FTP rows before the one test insertion.
- Focused concurrency regressions — cold Training State, Plan, and Home GETs each returned 200 after a stale-cache retry while an ordinary FTP write committed during classification; Home's test write took 0.0034 seconds. Prehistory integration verified comparison, power stress, daily values, Plan, and cache-signature refresh.
- `git diff --check` — passed.

The browser preview is at `http://127.0.0.1:8875/performance/ftp` and uses only the isolated `local_data/ftp01/preview` copy. No production database, deployment, merge, or active FTP CSV removal was performed. Astra's separate review and PR #41 publication remain with the parent workflow.
