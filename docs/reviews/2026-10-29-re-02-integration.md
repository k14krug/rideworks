# RE-02 integration and verification

Reference: `origin/dev` at `1b1777c494d3ad1ef33e1285aa310f8d6efae1db`; integration baseline: `origin/main` at `1ca98b9`.

Plan: retain the current Home layout and charts; transplant the unchanged Relative Effort model and small presentation additions to Home, Activities and Activity Review. Adapt the request-local stress and planning cache batches from the accepted dev concurrency fix, retaining main's Training State chart. Selectively bring the compact card and tablet layout styles and verify on a synthetic Store. No schema migration or wholesale dev merge is planned.

Reference test: `.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_relative_effort.py' -v` on the dev archive: 9 tests passed.

## Implementation

The shared classifier is byte-for-byte identical to the dev reference. Home keeps its six recent rides, mileage-by-year, goal and trend renderers; only the accessible effort indicator is added. Activities and Review use the same classification. Review adopts the compact summary and chart readout while retaining main's visible heart-rate and ascent values. The Home request defers its stress and planning cache batches until after response rendering, reuses only signature-matching pending results and retains the stale-snapshot retry. No migration or product decision was needed.

## Verification

- Dev reference: nine Relative Effort unit tests passed; the synthetic browser preview showed matching Home, Activities and Review categories, including Not rated.
- Focused tests: `.venv/bin/python -m unittest discover -s tests -p '<pattern>'` for `test_rideworks_relative_effort.py`, `test_rideworks_home_effort.py`, `test_rideworks_dashboard.py`, `test_home_trends.py`, `test_rideworks_web.py`, `test_rideworks_activity_review.py`, `test_rideworks_training_state.py`, `test_rideworks_planning.py`, `test_rideworks_ftp_page.py`, `test_rideworks_ftp_history.py`, and `test_rideworks_strava_streams.py`: 188 tests passed. The FTP suite includes cold and invalidated caches, concurrent FTP writes during effort calculation and response wrapping, stale-snapshot retries, and pending-result signature checks.
- Full suite: `.venv/bin/python -m unittest discover -s tests`: 533 tests passed. The first sandboxed run had 21 errors because loopback sockets were prohibited; the complete rerun with loopback access passed. An intermediate Review transplant exposed missing visible heart-rate and ascent; these were restored and the full suite rerun.
- Synthetic browser: `tools/preview_relative_effort.py --data-dir <new-empty-directory>` creates a disposable synthetic Store. Serve it on loopback port 18872 and execute `tools/verify_relative_effort_browser.js` with Playwright: 227 assertions passed at 1440, 1024, 850, 768, 650, 390 and 320 CSS px. This checked Home/list dot colors and category agreement, rated and unrated Review cards and reasons, keyboard expansion and chart readout, navigation, current Home charts and goal, and no document overflow. At 850/768 px, minimum title widths were 603/521 px; the maximum row height was 129 px. At 320 px minimum title width was 241 px. No browser script errors occurred. The local browser assertions and synthetic fixture are the evidence; no private screenshots or data are included.
- An isolated synthetic comparison with `origin/main` found identical annual goal, yearly legend, weekly mileage and Fitness chart markup. Dashboard data differed only in request-time fields (`as_of`, performance range timestamps and the initial rolling timestamp). Current Home had six recent rows and the annual card did not exceed Mileage Progress at desktop width. Training State, Plan, Performance and Settings routes returned successfully.
- `git diff --check` passed; `cmp` confirmed the classifier matches the reference exactly. Existing untracked editor files were not included.

## Review boundary

Stop for HARD — Analyst review of the focused draft PR. The Owner's running-UI visual acceptance and explicit authorization remain required before merging to main or deploying.

## Owner-requested Recent Activities update

The Owner subsequently requested removing the ride-type line and fitting more rides into the existing card height, superseding the initial six-row preservation requirement. The Home card now selects up to 24 newest cycling activities and displays the maximum whole rows that fit, retaining effort dots, links and metrics. The desktop card remains aligned to the adjacent trend cards; stacked layouts use height caps based on the previous synthetic card. Additional rides remain accessible through View all Activities. Without JavaScript, the list remains scrollable; an exceptionally tall first row also remains scrollable.

Verification after this update: `.venv/bin/python -m unittest discover -s tests` passed 534 tests with loopback access. Focused Dashboard, Home effort, Relative Effort and Home trends suites passed 55 tests. `tools/verify_relative_effort_browser.js` passed 275 assertions on a disposable synthetic Store at widths 1440, 1024, 850, 768, 650, 390 and 320 px, covering complete ordered rows, whether the next row would fit, effort consistency including Not rated, links, charts, goal and overflow. The displayed row counts were respectively 12, 10, 10, 7, 6, 10 and 8; actual counts vary with title and metric wrapping. A long-title resize sequence across desktop, tablet and mobile retained complete rows. The synthetic desktop card remained 561 px at 1440 px, and the 390 px card was 1032 px versus its previous 1036 px. The classification algorithm and source data were not changed.
