# Home dashboard cleanup — development review, 2026-10-17

Owner-directed review of the already committed cleanup on existing `dev`, based
on `dd1dc31eebb5fbc3c1be4922eabdb7b827528992`, then the concurrent annual
target-pace additions through `b57ea98`. Comparison baseline is refreshed
`origin/main` at `dcd77f1401fb1f1949b19b16c934ad33af88454f`.

The application changes were retained as committed. Recent Activities selects
seven cycling rides, without the type subline. The specified Home commentary is
removed. Home suppresses provisional recommendation commentary through optional
presentation flags; Plan and Activity Review retain their existing defaults.
No FTP, stress, planning, Performance, distance, goal, source-selection or
provenance algorithm changed.

## Corrections and automated verification

- Full suite: **499 tests passed** with
  `DEBUG=0 .venv/bin/python -m unittest discover -s tests -q`.
- The first run found one stale dashboard assertion requiring the intentionally
  removed Training State explanation. Updated it to require the compact empty
  training state and its destination link, and reject the removed explanation.
- Three first-run subprocess errors came from the agent shell's inherited
  `DEBUG=release`, which is invalid under the existing startup contract. The
  rerun uses a valid command-scoped value; runtime code and `.env` were unchanged.
- The synthetic Chromium suite initially expected the browser timezone to
  override the accepted Los Angeles default. Its check now verifies that default
  first, then tests the existing explicit `home_tz` query in LA and Tokyo.
- Synthetic Chromium acceptance passed: independent SQL/Decimal mileage and
  Performance evidence, source precedence, date/year/leap-year boundaries,
  annual-goal set/update/clear/restart, 48 tooltip lifecycle checks, responsive
  layout, fake sync convergence, failure/retry and later-sync recovery.

Reproduce the synthetic check with a fresh ignored store and an open Playwright
CLI session:

```bash
.venv/bin/python tools/verify_rideworks_dashboard_ui.py \
  --synthetic-dir local_data/home-cleanup-review/fresh-synthetic \
  --session rideworks-dev-review \
  --output output/playwright/home-cleanup-review/synthetic-result.json
```

## Calculation and source preservation

A consistent SQLite backup of the development store was used for comparisons;
no private credentials were copied. Baseline application source was extracted
with `git archive origin/main rideworks pyproject.toml`, without switching or
creating a branch. The snapshot references existing original artifacts for reads.

Compared exact model hashes in **six fixed-clock cases**: Los Angeles and Tokyo,
2026-10-17 at 07:00 and 20:00 Los Angeles time, plus the January 1 UTC boundary.
Dashboard mileage/goal/Performance/diagnostics match exactly after separating the
recent list. The first six recent rows match exactly; the current list has seven.
Training State, Plan, Performance history and FTP snapshots match exactly.
All **27 compared table fingerprints**, including FTP and source evidence, match;
the unrelated Power Curve profile cache was excluded. Integrity and foreign-key
checks pass. The snapshot retains 1,444 activities, 2,885 Performance rows and
66 FTP entries. Separately verified **1,422 referenced original artifacts** by
stored SHA-256 and byte size against the development store.

Private reproducibility scripts, snapshots and detailed browser results are
retained under ignored `output/playwright/home-cleanup-review/` and
`local_data/home-cleanup-review/`. Original artifacts were never modified.

## Development availability and Owner review

Real development Home acceptance passed **996 Chromium assertions** at
**1440, 1024, 768, 390 and 320 CSS px**, including 320px touch input. It verifies
all seven ride rows and source values, removed commentary, Home/Plan date/type/
duration/power agreement, preserved Training State values, mileage bar/line
inspection with pointer/keyboard/touch, working destinations, collapsed/open
supporting disclosures, focus order, unique IDs, no horizontal overflow and
zero JavaScript errors. Desktop, 390px and 320px screenshots were also visually
inspected. Private before/after screenshots remain ignored under
`output/playwright/home-ui-01-cleanup-review-*.png`.

The existing `verify_home_browser.js` template was invoked through Playwright
CLI with the live development URL and an isolated baseline server. Its historical
"recommendation closer to top" assertion was adapted locally to require no
downward movement: the `main` baseline already has the accepted Home layout.
Recommendation top positions match at every width. No layout code was changed.

The established development command is `.venv/bin/python -m rideworks serve`,
with checkout `.env` selecting port **8766** and the default repository-root
`data/` store. The existing process on 8766 already serves the committed cleanup;
no application-source correction was needed. After integrating the concurrent
commits, only that development process was restarted with its original environment
and normal command so it serves the updated annual target-pace wording. Owner review URL:
**http://127.0.0.1:8766/**.

A pre-existing older local process also listens on port 8765; it was left
untouched. Port 8766 is the instance verified for this review. The temporary
baseline comparison server was stopped after verification.

Production was not contacted, deployed or merged. `main` was not modified.
Three concurrent remote commits arrived before the first push. The verification
commit was rebased cleanly onto them, preserving the new wording and regression
tests. Final full Python, synthetic Chromium and fixed-clock/table comparisons
passed again. The new annual target-pace label derives its displayed weekly
target from annual goal × 7 / days in year; the underlying goal model is unchanged.
An additional **61 Chromium assertions** passed against the restarted final
development release at all five widths, verifying the new target-pace label,
the seven requested cleanup changes, card/page containment and no JavaScript
errors. Final desktop and 320px captures were visually inspected again and are
retained privately as `output/playwright/home-cleanup-review/final-*.png`.

No unresolved dashboard regression was found. Final Owner review remains pending.
