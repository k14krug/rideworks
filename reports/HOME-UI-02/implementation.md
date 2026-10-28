# HOME-UI-02 — Home trend cards

Status: ready for **HARD — Analyst** technical review. **HARD — Owner** running-UI visual acceptance follows; the task remains `in_progress`. Branch: `task/home-ui-02-trend-cards`, based on refreshed `main` at `453a52f`.

## Behavior and implementation

- `rideworks/home.py` renders the existing Training State daily Fitness values for `(six calendar months before the service's local today, today]`, matching the full Training State page's calendar-cutoff convention. It reuses `months_before`, clamps month-end dates, and does not recalculate Fitness. The Y bounds use the displayed values with 10% padding (at least 0.5) and a nonnegative lower bound. Flat/zero series have a usable scale; absent values and missing dates break the line. The last actual point has a one-decimal label; a stale endpoint also has a visible date. Empty/out-of-range history has an unavailable message.
- `rideworks/training_state_page.py` replaces only `training_home`'s numeric Fitness/Fatigue/Form summary with the Home graph and full-page link. Accessible chart descriptions explain the stress model, missing-load limitation, provisional early history and endpoint date. The full Training State page's renderer and service are unchanged.
- The Performance card retains `dashboard()['performance']`, its last-year rolling steps, contributor links and gaps. The endpoint uses `performance['current']`, never `performance['latest']`. An expired current window has no endpoint marker/value, even when older history remains. Chart captions retain the rolling-42-day definition and current Performance evidence source. Quick facts remain separate.
- A shared Home SVG frame supplies axes and calendar labels. Only the trend cards use the new styles. Existing navigation, recommendations, recent activity rows, mileage/goal charts and supporting evidence are preserved.
- Desktop cards share the Recent Activities grid row and align their total height, including the gap, with that card. The recent card can stretch to accommodate legible charts; no rows or chart content are truncated to force alignment. Existing tablet behavior (two cards side by side below Recent Activities) and phone stacking are preserved. On phones, year/month labels show the two range boundaries to avoid overlap. Endpoint overlays pass pointer events through to existing contributor links.

## Verification results

- **509 Python tests passed**, including **12 new Home trend tests** and **25 existing dashboard tests**. New cases cover calendar/month-end/leap-year bounds, exact service values, increasing/decreasing/flat/zero/single/sparse/absent Fitness, dated stale endpoints, twelve-month rolling history, expiry, unknown timezones, and a rolling-best/latest-ride disagreement. The existing Home assertion for the removed Form caption was updated to assert the new Fitness subtitle and absence of that caption.
- **543 Chromium assertions passed** at **1440, 1024, 768, 390 and 320 CSS px**, with no JavaScript errors. This includes seven synthetic edge-state variants per width, endpoint sourcing, SVG label containment/non-overlap, card containment, page overflow, keyboard link focus, working destinations, preserved Home content, ten full Training State/Performance style comparisons and both pages' existing chart controls. See [browser-checks.json](browser-checks.json).
- An additional browser check confirmed endpoint overlays use `pointer-events: none` and existing power contributor links remain keyboard-focusable with working destinations.
- **Six fixed-clock cases across Los Angeles and Tokyo passed before/after comparison**: Home outside the two intentionally replaced cards, five other full pages, Dashboard/Training State/Performance/Planning outputs, all **28 synthetic Store tables**, and **two original synthetic FIT artifacts** match. Original hashes, sizes and mtimes match; integrity is `ok` with zero foreign-key violations. See [preservation.json](preservation.json).
- `git diff --check`, JavaScript syntax and Python compilation passed. `.vscode/settings.json` retains its pre-task SHA-256 `8e03d08816b90e37aea5cbc9215853742b3192a13a46c37d7c412d5885254dd5`.

The desktop review case measures **565.84 px** for both Recent Activities and the combined right column; the two cards are **274.92 px** each, separated by 16 px. See [desktop synthetic capture](desktop-synthetic.png) and [320px synthetic capture](mobile-synthetic.png). The private Owner mockup was compared visually for hierarchy, stacked desktop cards, blue graph/endpoint treatment, links, spacing and alignment; its illustrative values and ride history were not copied.

## Reproduction

Use a fresh disposable data directory. No real rider Store or live network sync is required. Run from the repository root:

```bash
mkdir -p /tmp/rideworks-home-ui-02-baseline
git archive 453a52f | tar -x -C /tmp/rideworks-home-ui-02-baseline
.venv/bin/python tools/preview_home.py --data-dir /tmp/rideworks-home-ui-02-synthetic
.venv/bin/python tools/verify_home_trends.py --data-dir /tmp/rideworks-home-ui-02-synthetic --code-root /tmp/rideworks-home-ui-02-baseline --snapshot /tmp/rideworks-home-ui-02-before.json
.venv/bin/python -m unittest discover -s tests -p 'test_home_trends.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_dashboard.py' -v
DEBUG=0 .venv/bin/python -m unittest discover -s tests -q
.venv/bin/python tools/verify_home_trends.py --data-dir /tmp/rideworks-home-ui-02-synthetic --snapshot /tmp/rideworks-home-ui-02-before.json --compare --report reports/HOME-UI-02/preservation.json
```

Run each fixed-clock server in a separate terminal:

```bash
.venv/bin/python tools/verify_home_trends.py --data-dir /tmp/rideworks-home-ui-02-synthetic --serve-port 8791
.venv/bin/python tools/verify_home_trends.py --data-dir /tmp/rideworks-home-ui-02-synthetic --code-root /tmp/rideworks-home-ui-02-baseline --serve-port 8792
```

Open an existing managed Chromium session, then run the committed browser driver:

```bash
playwright-cli -s=home-ui-02 --config=/tmp/rideworks-home-ui-02-playwright.json open about:blank
.venv/bin/python tools/verify_home_trends.py --data-dir /tmp/rideworks-home-ui-02-synthetic --browser-session home-ui-02 --report reports/HOME-UI-02/browser-checks.json
```

The local Playwright config selects the installed browser, without downloading anything:

```json
{"browser":{"browserName":"chromium","launchOptions":{"executablePath":"/home/kkrug/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome"}}}
```

Adjust the executable path to an installed Chromium when reproducing elsewhere. The ordinary skill wrapper could not reach npm in this environment; the available local `playwright-cli` and installed managed Chromium were used. The first full-suite attempt encountered sandbox socket restrictions and unrelated local DEBUG configuration; rerunning with authorized loopback access and `DEBUG=0` passed all 509 tests. The verification Settings factory explicitly has no credentials, keeping baseline comparison independent of either checkout's private environment. Generated screenshots and intermediate snapshots remain under ignored `output/playwright/` or `/tmp`; only the two deliberately synthetic captures and aggregate JSON results are committed.

## Review boundary and limits

No metric/source/eligibility algorithm, database schema, actual rider data, production service or deployment was changed. No private screenshot was saved in Git or attached to GitHub. Real-rider visual acceptance has not been performed by this verification and remains with the Owner after Analyst review. OPS-03 stays closed and Phase 6 stays deferred. No next task has started.
