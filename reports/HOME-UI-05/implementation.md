# HOME-UI-05 implementation and verification

## Implementation

Training Overview now uses two compact sections: the existing Fitness, dated recorded FTP and mileage values on the left, and exact 5-, 60-, 300- and 1,200-second observed Virtual Ride Power Curve bests on the right. The existing Training State and FTP History links remain. Missing values are labeled unavailable; if a recent profile is missing or stale, the section says “Update needed” and explains that bests may be incomplete in its title. The other Home cards and recommendation logic are unchanged.

The read-only `recent_bests` path first selects potentially in-window source dates from native session, current API and CSV metadata. A two-day coarse date margin accommodates offsets; unusual date formats are parsed rather than discarded. Every potentially relevant identity is then hydrated once and the existing file → current API → CSV presentation precedence and UTC `[as_of - 90 days, as_of)` bounds are applied. Only in-window Virtual Rides have their current method, policy, grid and source signature checked. The existing envelope selects by exact sum and applies its established tie ordering. Home does not compute curves, read raw records, fetch streams or write Power Curve caches. SQL still examines source-date metadata; it does not hydrate or validate every old activity.

## Correctness

- `.venv/bin/python -m unittest discover -s tests -p 'test_home_power_bests.py'` — 9 tests passed. These exercise exact anchors, different winners and ties, inclusive/exclusive UTC boundaries, offsets and DST, outdoor exclusion, missing/unknown dates, competing file/API/CSV dates, stale/missing/incompatible cache entries, partial coverage, zero watts, and bounded read-only behavior without raw recomputation.
- `.venv/bin/python -m unittest discover -s tests -p 'test_home_training_overview.py'` — 5 tests passed, including existing Fitness, dated FTP and mileage behavior and the shared Home as-of instant.
- `.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_dashboard.py'` — 32 tests passed.
- `.venv/bin/python -m unittest discover -s tests` — 558 tests passed. Loopback access was enabled for local HTTP/OAuth tests; the sandbox-only run could not create those sockets.

## Responsive review

Chromium compared the merged HOME-UI-04 baseline (`0119f6b`) and this branch using equivalent disposable synthetic Stores. The viewport was checked against `window.innerWidth`. At 1440, 1024, 768, 390 and 320 CSS pixels there was no horizontal document or overview-section overflow. Three current-status and four power rows, both links, the lack of old mini-tiles/icons, unchanged recommendation text, and unchanged lower-card text were checked at every width. On 1440px the populated overview was 201.28px high versus 221.38px at baseline. A separate missing-profile case was 202.47px versus 203.88px, displayed unavailable values and “Update needed,” and had no overflow at 1440, 390 or 320px. The two sections stack on small screens; mobile card height is allowed to grow. The lower 42-day Performance chart and its calculation are unchanged.

Only synthetic data appears in the [desktop](desktop.png), [mobile](mobile.png) and [missing-profile](pending.png) captures. The private Owner mockup is not included. Analyst technical review and the Owner's visual review of the running application remain required.

## Performance

A disposable Store created with `tools/preview_home.py` was extended with 250 synthetic activities older than 120 days, for 282 total activities. The same Store, fixed Home clock `2026-10-30T20:00:00Z`, UTC query, process environment and machine were used for both revisions. Each measurement used three warm-up requests followed by 20 complete loopback HTTP Home GETs; p95 is the 19th sorted observation (nearest rank). Runs were sequential:

| Revision | Median | p95 |
| --- | ---: | ---: |
| HOME-UI-04 baseline | 99.2 ms | 114.0 ms |
| HOME-UI-05 | 107.5 ms | 117.4 ms |

The observed median increase was 8.3 ms; this small local sample is not a production latency guarantee. For that Store, the new date query returned 41 plausible source-date rows, yielding 31 distinct in-window candidate identities and 19 in-window Virtual Ride profiles to validate. It did not validate all 282 activities. The SQL engine can still scan old source-date metadata; these counts describe rows returned and hydrated/validated, not the database engine's physical reads.

Reproduction on a fresh synthetic Store (the preview generator uses the current wall date; run on the benchmark date or adjust the fixed clock in the benchmark and regenerate the fixture consistently):

```sh
TASK_DATA=$(mktemp -d)
TASK_BASELINE=$(mktemp -d)
git archive 0119f6b | tar -x -C "$TASK_BASELINE"
.venv/bin/python tools/preview_home.py --data-dir "$TASK_DATA"
PYTHONPATH="$PWD" .venv/bin/python reports/HOME-UI-05/benchmark.py --data-dir "$TASK_DATA" --add-old
PYTHONPATH="$TASK_BASELINE" .venv/bin/python reports/HOME-UI-05/benchmark.py --data-dir "$TASK_DATA"
PYTHONPATH="$PWD" .venv/bin/python reports/HOME-UI-05/benchmark.py --data-dir "$TASK_DATA"
```

The `--add-old` option writes synthetic activities and rebuilds caches once during fixture setup; the timed requests do neither for Power Curve. Use it only with a disposable synthetic Store. Browser capture used the same synthetic preview and a separate synthetic missing-profile Store. No production Store, private activity details, credentials or mockup were used in this evidence.
