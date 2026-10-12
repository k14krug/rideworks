# OPS-01 Stage A — review package

Invocation: `/AUTOTASK OPS-01`, 2026-10-12. Controlling JIT: [OPS-01](../../docs/tasks/OPS-01.md). Branch: `task/ops-01-production-readiness`; [draft PR #34](https://github.com/k14krug/rideworks/pull/34), [issue #33](https://github.com/k14krug/rideworks/issues/33).

Stage A implements the approved timezone default and inventories candidate stores read-only. **Stop at HARD — Analyst Gate 1.** The source, deployment host and destination remain unselected. No promotion, permanent copy, rollback snapshot, migration, cleanup, credential reset, startup redirection or new backup subsystem was performed.

## Server and browser behavior

- An absent calendar timezone selects `America/Los_Angeles` through `ZoneInfo`, including DST. Home, Plan, Training State, Activities filters, annual-goal Settings and Activity Review's current-next-ride panel render on the first response.
- Explicit `home_tz`, `plan_tz`, `tz` and existing `curve_tz` overrides remain supported. Empty, duplicate or invalid selected timezone parameters receive a clear HTTP 400; excessive query fields also receive a clear 400 instead of silently ignoring a timezone.
- Removed browser timezone redirects from `review.js` and `power_curve.js`. Browser date presentation uses the validated server zone. Plan's midnight/tab-focus check uses the same zone, including explicit overrides; Activity Review correction forms receive their timezone from the server.
- Power Curve's existing calendar-boundary computation receives the selected `curve_tz` (default LA). Its algorithms, source qualification and absolute activity baseline windows are unchanged. The panel discloses the selected calendar rather than claiming browser-controlled bounds.
- Original timestamps remain absolute UTC evidence. Without JavaScript, source instants remain visibly labeled UTC; date-filter/calendar computations use the server zone. Interactive graphs retain their existing JavaScript requirements.

## Verification

**453 Python tests passed**, including seven new OPS-01 tests. Focused suites: 7 calendar/inventory, 25 dashboard, 19 history, 29 planning tests. The full suite includes accepted Performance, Power Curve, FTP, Training State, planning, source and Strava coverage.

New calendar checks cover missing versus explicitly blank/invalid/duplicate zones; substantive and honest empty first responses; LA versus UTC/Tokyo date filters; the year boundary; summer's local previous date; and both sides of the 2026 spring/fall DST transitions. Default responses equal explicitly selected LA responses at fixed clocks. Source instants remain unchanged. Inventory tests check database/secret-file bytes and mtimes stay unchanged and WAL/journal candidates are refused without sidecar creation.

**640 Chromium assertions passed** across JavaScript enabled/disabled and browser zones UTC/Tokyo. Each ordinary main-navigation link loads once with no timezone query injected. Explicit bookmarks remain unchanged, invalid requests return 400 without loops, date labels/forms retain server zones, Power Curve overrides persist, and Plan focus does not reload due to a browser/server calendar mismatch. See [browser checks](browser-checks.json).

**Synthetic comparison against refreshed `main` (`67321e7`) preserved** six fixed-clock model cases, JSON payloads for 36 page states, all 26 tables, two generated source originals (hash/size/mtime), and approved FTP/Elevate reference files. Existing model, eligibility and provenance logic is unchanged. See [preservation evidence](preservation.json). This uses synthetic data and does not claim real-store promotion parity; that remains Gate 3 work.

Reproducible commands (all application verification uses explicit disposable stores):

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_calendar_defaults.py'
.venv/bin/python tools/preview_home.py --data-dir <new-disposable-synthetic-directory>
.venv/bin/python -m rideworks --data-dir <synthetic-directory> serve --port 8777
npx --yes --package @playwright/cli playwright-cli --session ops-01 open http://127.0.0.1:8777/
npx --yes --package @playwright/cli playwright-cli --session ops-01 run-code --filename tools/verify_calendar_defaults_browser.js
```

The committed browser script uses only the disposable server on port 8777. Do not point it at an everyday store. The Playwright skill wrapper worked for opening the session, but its injected `--config` is unsupported for this installed CLI's `goto`/`run-code`; those operations used the repository's established direct `npx` CLI pattern.

For fixed-clock comparison, archive `main` into a temporary code directory, run `tools/verify_rideworks_visual_preservation.py` with an explicit synthetic `--data-dir`, `--code-root <baseline-code>` and private `--snapshot`, then repeat against the task code. Compare `models`, `tables`, `artifacts`, `references` and each page's `payloads`; markup/notes deliberately differ. Private snapshots and run logs remain ignored local files.

## Read-only inventory method

`tools/inventory_rideworks_stores.py` accepts explicit candidate directories and an explicit new private output file (mode 0600). It never imports/constructs `Store`, reads OAuth/settings contents, runs migrations, copies databases, or writes candidates.

It checks the SQLite header and existing journal sidecars before opening. WAL-mode or journal-bearing candidates are refused. Rollback-journal stores use SQLite URI `mode=ro`, normal locking, `query_only`, memory temporary storage and one read transaction. No `immutable=1` assertion is made about potentially writable data. This follows [SQLite URI documentation](https://www.sqlite.org/uri.html) and avoids the shared-memory creation concerns described in [SQLite WAL documentation](https://www.sqlite.org/wal.html).

Per candidate, private output records schema, integrity/FKs, table/cache/snapshot counts and cached-content fingerprints, activity/source/external observation identity sets, user state and recency, latest activity/sync evidence, referenced original hashes/sizes, linked-original dependencies, and token/settings **presence only**. Database size/mtime and absence of new journal sidecars are checked after inspection. Shared originals are read and recorded as dependencies; no symlink is altered. Missing/mismatched originals remain explicit evidence.

Launch discovery reads only relevant CLI/config keys and resolves precedence (`--data-dir` > exported env > ignored checkout `.env` > user-home default). Process environments, command lines and private `.env` contents are never dumped. Private paths, identities, activity dates and auth values are excluded from this report/PR.

Example inventory invocation, with all candidates explicitly supplied:

```bash
.venv/bin/python tools/inventory_rideworks_stores.py \
  --data-dir <candidate-a> --data-dir <candidate-b> \
  --private-output <new-private-local-report.json>
```

## Inventory result and handoff

[Sanitized comparison](inventory-summary.json): **86 candidate stores**, **85 readable** with integrity `ok` and no FK violations. All inspected database size/mtime checks remain unchanged and no journal sidecars appeared. One older WAL-mode replay (S46) was refused; its existence is recorded without assuming it contains no divergent state.

The configured source **S35** is actively running and is the recommended source to consider after Analyst review, **subject to Owner Gate 2**. Its 1,443 Activity identities, 1,421 file-source hashes, 21 API external/observation identities and sync checkpoint match recent full-history review copies S02/S24. All 1,422 referenced originals verify. It retains one saved classification correction absent from those copies, one annual-goal row and private OAuth/settings sidecars; there are no saved feedback/intent rows. Recent review copies have no OAuth token sidecar. Cache populations match (1,443 Power Curve profiles, 1,419 training cache entries and 1,326 classification cache entries). These are population comparisons, not a declaration that every cached profile is eligible.

No larger/newer identity cohort was found among readable candidates. Other large copies have older/fewer activity/API identities or schemas. **Eleven older/replay stores have 15,074 missing original references**; no present artifact has a hash/size mismatch. S19 has all 1,422 originals linked outside its own directory. These copies are not self-contained promotion candidates. No repair, copying or deletion was attempted.

Seven preexisting application servers were identified. The configured data path matches one of them, but the next normal launch's configured port does not match that server's explicit port. The normal launcher therefore is not yet established as an everyday operation. The recommended default destination does not exist; its absence does not authorize creating/promoting it. Host and destination are still undecided.

Full paths, exact latest activity/sync and user-change times, identity sets, cache fingerprints, process/config discovery and a meaningful-path recommendation remain in ignored private local files. To reproduce discovery, enumerate databases under the ignored local-data root, the user-home default if present and active CLI/config-resolved paths. Inspect `/proc` process arguments/environment only for startup keys and data/port arguments; apply the existing `startup_config` precedence with each process's working directory. Supply all paths explicitly to the inventory command. The exact local discovery results and invocation inputs are retained privately. Cache fingerprint supplementation used separate rollback-mode `mode=ro` read transactions with the same header/sidecar and before/after metadata checks; no candidate mutations occurred.

**Review needed now:** Analyst Gate 1 correctness/data-safety/source-recommendation review, including the refused WAL store, missing-original copies, linked dependency and differing saved classification. After that gate, Owner Gate 2 selects exact source, deployment host, destination and any reconciliation. Stage A does not establish promotion/rollback parity (Gate 3) or everyday-launch acceptance (Gate 4). Existing candidates remain intact; Phase 6 remains deferred.
