# HOME-DEV-REVIEW — Post-Plan concurrency follow-up

2026-10-18; existing draft [PR #46](https://github.com/k14krug/rideworks/pull/46)
targets `dev`, branch `fix/home-dev-review-corrections`. Addresses
[Analyst review 5563420406](https://github.com/k14krug/rideworks/pull/46#pullrequestreview-5563420406)
of `8f236206d9d5d5b73354311ecdf76e841a9f89ec`.

## Confirmed failure

The initial fix moved Plan before Relative Effort but flushed Plan's cache batch
before the remaining Home work. The existing classification-pause tests passed
while missing this later writer-lock window.

Added cold-cache and FTP-invalidated-cache tests that pause after Plan, inside
Relative Effort, then attempt the same concurrent FTP edit with a **200ms busy
timeout**. Both reproduced `sqlite3.OperationalError: database is locked` on
`8f23620`. Two further tests pause after final response rendering; both also
fail against an archived `8f23620` source tree. No assertions or timeouts were
relaxed.

## Correction

Home's HTTP request now owns the existing two pending cache-write lists:

1. Plan calculates stress/classifications into those lists.
2. Relative Effort and Training State use the same pending stress batch without
   writing it to SQLite.
3. Home markup and the final response wrapper (including Performance status)
   finish on the same coherent read snapshot.
4. The two existing cache batches are written immediately before returning from
   the existing outer transaction.

`Store._transaction`, WAL/isolation, commit/rollback and `Application.get`'s
single stale-snapshot retry are unchanged. A concurrent FTP edit can commit
during the expensive work. If it invalidates the reader's snapshot, the final
cache-write upgrade triggers the existing full-request retry; the old pending
lists are discarded. Both cache types and the returned response are then
calculated from the new coherent snapshot.

This carries the existing optional deferred-write pattern through Home's
consumers; it does not introduce a new transaction mechanism, persistent cache,
schema, background process or generalized caching framework. Standalone Plan,
Training State, Relative Effort and direct Home calls retain their default
transaction/cache ownership behavior.

Later consumers reuse serialized results already in the pending write list
**only when the full existing input signature matches**. This avoids rescoring
cold rides for each card. Date/title/timezone presentation is rebuilt for each
consumer. A dedicated test verifies reuse across LA/Tokyo and recalculation
after an FTP revision, without any early cache insert.

There is no UI or training-model change. The accepted Relative Effort population,
thresholds, historical FTP and duration rules remain intact. Broad warm-history
scan optimization remains deferred: three standalone warm scans still used
7,236 SQL statements and 0.306/0.343/0.307 seconds over 1,420 rides; pure
classification took 0.008–0.010 seconds. Pending-result reuse preserves one
calculation per ride per attempt; it is not a claim of faster warm pages.

## Automated verification

All commands use command-scoped `DEBUG=0` and `PYTHONDONTWRITEBYTECODE=1`.

```bash
.venv/bin/python -m unittest discover -s tests -p test_rideworks_ftp_page.py \
  -k post_plan_relative_effort -v
.venv/bin/python -m unittest discover -s tests -p test_rideworks_ftp_page.py \
  -k home_get -v
.venv/bin/python -m unittest discover -s tests -p test_rideworks_ftp_page.py \
  -k pending_stress -v
.venv/bin/python -m unittest discover -s tests -q
```

- Full suite: **529 passed** in 29.298 seconds.
- Six Home concurrency cases cover classification, post-Plan Relative Effort,
  and fully rendered response, each with cold/invalidated caches. Five repeats
  of each: **30 passed**; maximum concurrent FTP commit time **0.0039 seconds**.
- Every case verifies the existing coherent retry, fresh 250W FTP cache values,
  both cache batches, and exactly one stress calculation per ride per attempt.
- The pending-result reuse test validates the current FTP signature, recomputed
  display timezone/day and deferred database writes.
- Six fixed-clock LA/Tokyo cases preserve exact Relative Effort, Training State,
  Plan and dashboard hashes; FTP/Performance and all 26 non-cache tables match
  the reviewed development baseline.

The response-pause baseline reproduction uses the same tests with
`PYTHONPATH=/tmp/rideworks-home-post-plan/baseline` and an absolute `tests`
directory; that archive contains `8f23620`, not the corrected working files.

## Source preservation

The existing `tools/verify_activity_review_preservation.py` was run first with
`--code-root /tmp/rideworks-home-post-plan/baseline` (archived `8f23620`) and then
against corrected source with `--compare`, using the existing disposable review
store. **All 27 representative review cases, all 28 tables, all 1,422 original
artifact hashes/sizes/modification times, accepted model results, raw payloads,
summaries, calculated values, provenance and approved reference match.**
Integrity is `ok`; zero foreign-key violations. The independent
`tools/verify_rideworks_dashboard.py` also passed.

```bash
.venv/bin/python tools/verify_activity_review_preservation.py \
  --data-dir /tmp/rideworks-astra-review \
  --code-root /tmp/rideworks-home-post-plan/baseline \
  --snapshot /tmp/rideworks-home-post-plan/activity-preservation.json
.venv/bin/python tools/verify_activity_review_preservation.py \
  --data-dir /tmp/rideworks-astra-review \
  --snapshot /tmp/rideworks-home-post-plan/activity-preservation.json --compare
```

## Browser verification

Temporary snapshot servers use port 8791 for corrected source and 8792 for
archived `8f23620`. Playwright CLI runs the existing committed templates via
`run-code`; only the private case URLs/configuration are injected locally.

- Activity Details: **25,033 assertions passed**, all six evidence cases at
  1440/1024/768/390/320px. Exact source readouts, keyboard/pointer/touch, Power
  Curve, Relative Effort colors, disclosure defaults, compact readout styles,
  and sidebar height assertions remain intact; no page/console errors.
- Home: **1,266 assertions passed** at 1440/1024/768/390/320px against archived
  `8f23620`, preserving recommendation position exactly. Covers Home/Plan
  agreement, seven recent rides, effort indicators, actual SVG goal-marker/gap
  pixels, no inline styles, mileage interactions, keyboard/touch, links and
  disclosures; no page errors.
- Cross-page: **1,691 assertions passed**, six routes at
  1440/1024/850/768/650/620/390/320px plus Activities sorting/filtering/paging.
  Tablet readability, Training State, Plan, both Performance views and Settings
  remain correct; no page errors.

Total for this follow-up: **27,990 browser assertions passed**. This is a fresh
rerun, separate from the initial pass's supplemental 53 checks.
Runtime HTTP retains strict `style-src 'self'` without `unsafe-inline`; the
completed Home browser session has zero console messages. Current Home phone
and Activities tablet screenshots were also inspected.

Private logs and artifacts stay under `/tmp/rideworks-home-post-plan/` and
`/tmp/output/playwright/`, including `ar-ui-01-post-plan-*`,
`home-ui-01-post-plan-*` and `rollout-post-plan-after-*` captures. They are not
committed. No Firefox/WebKit, physical-device or screen-reader verification is
claimed.

## Handoff

Return to Analyst review on draft PR #46 after verification. The independent
Astra re-review, Owner visual acceptance and mixed-source calibration decision
remain separate. No merge, deployment, production-store operation or restart of
existing development processes is authorized or performed.
