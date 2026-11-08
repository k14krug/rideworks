# HOME-UI-06 — implementation and verification

## Source and scope

Home selects the existing dashboard cohort (at most 24 cycling Activities) first. One parameterized `race_results WHERE activity_id IN (...)` query retrieves only their current results; no query is made for an empty cohort. `activity_id` is the table's primary key. The query does not read removal/history tables, call an API, or alter the underlying Activity power, Activities page, training models, importer or schema. A current result's integer `avg_watts` is displayed verbatim, including zero; absent or null values display a dash. Activity Avg Pwr remains independent. The Race Avg W cell identifies the Zwift screenshot source.

## Verification

- `env DEBUG=0 .venv/bin/python -m unittest discover -s tests -p 'test_home_race_power.py'` — 1 test passed: active 169 W beside 222 W Activity power, no result, removed result, null, zero, out-of-cohort exclusion, one bounded query and no empty-cohort query, links and escaping; rows located by Activity ID.
- `.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_dashboard.py'` — 32 tests passed, including bounded recent selection, sorting, empty Home, escaping, and existing source precedence.
- `env DEBUG=0 .venv/bin/python -m unittest discover -s tests -p 'test_rideworks_home_effort.py'` — 1 test passed.
- `env DEBUG=0 .venv/bin/python -m unittest discover -s tests` — 642 tests passed with loopback enabled. The first run inherited an invalid `DEBUG` value and failed three subprocess tests; the valid-setting rerun passed.
- `git diff --check` — clean.

## Responsive comparison

Chromium compared refreshed main `3a81633` and this branch using the same disposable synthetic Store and UTC query, at 1080px viewport height. `tools/verify_home_race_browser.js` checks 1440, 1280, 1100, 768, 740, 620, 390 and 320px: unchanged existing row fields/order and link destinations, active 169 W and 0 W and missing values, no page overflow, checked cell/header overflow, mobile source label, and desktop card/visible-row preservation. The first six rows were checked for cell overflow. Synthetic screenshots were inspected at desktop and 320px; screenshots remain ignored locally. No real rider data was used.

| Viewport | Baseline card (px) | New card (px) | Fully visible rows, before → after |
| --- | --- | --- | --- |
| 1440 | 783.36 × 565.84 | 783.36 × 565.84 | 12 → 12 |
| 1280 | 680.95 × 575.44 | 680.95 × 575.44 | 9 → 9 |
| 1100 | 900 × 466.09 | 900 × 466.09 | 10 → 10 |
| 768 | 580 × 487.09 | 580 × 459.47 | 7 → 5 |
| 740 | 552 × 487.06 | 552 × 459.47 | 7 → 5 |
| 620 | 596 × 1003.09 | 596 × 983.09 | 16 → 12 |
| 390 | 366 × 1032.47 | 366 × 988.28 | 13 → 10 |
| 320 | 296 × 987.69 | 296 × 999.28 | 11 → 9 |

At 900px and below the existing stacked treatment starts earlier to prevent cramped columns. A new labeled line makes rows taller and reduces initially visible rows at small widths; the existing list remains scrollable. At 320px some labels and values wrap, but remain readable. This is synthetic evidence; Owner review of the running real UI and its title lengths remains necessary.

Reproduce with a fresh synthetic preview and baseline archive (the preview uses the current date):

```sh
mkdir -p /tmp/home-ui-06-baseline /tmp/home-ui-06-data output/playwright
git archive 3a81633 | tar -x -C /tmp/home-ui-06-baseline
.venv/bin/python tools/preview_home.py --data-dir /tmp/home-ui-06-data
PYTHONPATH=. .venv/bin/python - <<'PY'
import json
from rideworks.store import Store
with Store('/tmp/home-ui-06-data') as s:
    ids = [r[0] for r in s.connection.execute('select activity_id from strava_api_activities order by external_id limit 4')]
    s.connection.execute('insert into race_imports values (?,?,?,?,?,?,?,?,?,?,?,?,?)', ('synthetic','zwift_racing_profile_screenshot','synthetic',1,'image/png','synthetic','2026-10-01',None,'synthetic','v1','v1','[]',None))
    for identity, watts in zip(ids, [169, None, 0, 200]):
        s.connection.execute('insert into race_results values (?,?,?,?,?)', (identity,'synthetic',json.dumps({'avg_watts':watts}),None,'2026-10-01'))
    s.connection.commit()
PY
# Run these two servers in separate terminals:
cd /tmp/home-ui-06-baseline && env DEBUG=0 PYTHONPATH=. /home/kkrug/projects/rideworks/.venv/bin/python -m rideworks --data-dir /tmp/home-ui-06-data serve --port 18861
cd /home/kkrug/projects/rideworks && env DEBUG=0 .venv/bin/python -m rideworks --data-dir /tmp/home-ui-06-data serve --port 18862
# Open the current server in Playwright CLI, then:
playwright-cli run-code --filename tools/verify_home_race_browser.js
```

The same synthetic database is used only for local preview. Measurements are not a production latency or visual acceptance claim. HARD — Analyst Gate 1 and subsequent HARD — Owner Gate 2 remain open; no deployment is authorized.
