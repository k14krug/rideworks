# HOME-UI-04 implementation

## Source contracts

- The Home overview and six-month Fitness chart share one Training State result, evaluated at the dashboard's as-of instant and timezone. Fitness and its seven-day point change are the existing daily values; missing or short history is labeled, and a stale value includes its date. Early history remains provisional.
- The FTP value is the existing Plan result's recorded date-effective FTP, resolved using the accepted athlete calendar. No estimate or comparison against a guessed baseline is displayed. The FTP history link remains available when FTP is unknown.
- Last-seven-day mileage and its signed difference use the dashboard's existing calendar periods and distance rules. Missing totals make the comparison unavailable; partial missing distance is disclosed. A supported zero remains zero.
- The existing Next Recommended Ride, lower charts, activity list, mileage cards and diagnostics retain their existing sources and behavior. Home presents the recommendation with a cycling icon and a compact completed-ride row; its date, category, target, reason, provisional warning, Plan link and completed-ride links remain available. The overview keeps its natural height when the recommendation contains additional details. No calculation, persistence, synchronization or schema changes were made.

Implementation: `rideworks/home.py`, `rideworks/planning_page.py`, `rideworks/training_state_page.py`, scoped `rideworks/static/style.css`, focused tests and `tools/verify_home_ui04.js`.

## Verification

- `.venv/bin/python -m unittest discover -s tests`: 548 passed, including Plan, FTP, Training State, Home, mileage and Performance regressions.
- `.venv/bin/python -m unittest discover -s tests -p 'test_home_training_overview.py' -v`: 4 passed, covering modeled Fitness and change, stale and early history, FTP date boundaries and missing history, and mileage boundaries and missing values.
- `npx --yes --package @playwright/cli playwright-cli -s=home-ui-04 run-code --filename tools/verify_home_ui04.js`: 67 checks passed at 1440, 1024, 768, 390 and 320 CSS pixels, with an empty synthetic Store for missing values. Checked card geometry, horizontal overflow, long and unavailable values at 320px, links and keyboard focus, chart/summary parity, mileage parity, recommendation and lower-card text preservation, completed-ride details and links, and browser errors.

Browser checks used disposable Stores. Create one with `tools/preview_relative_effort.py`, serve the updated checkout on loopback port 18888, serve a pre-change `rideworks` tree and a copy of that Store on port 18890, and serve a new empty Store on port 18889. For the completed-ride case, add a synthetic same-day API observation to a copy of the fixture and serve it on port 18891, with its baseline copy on 18892. The screenshot fixtures contain only generated synthetic data:

| View | Before | After |
| --- | --- | --- |
| Desktop | [Before](before-desktop.png) | [After](after-desktop.png) |
| Mobile | [Before](before-mobile.png) | [After](after-mobile.png) |

The [320-pixel card](after-320.png) was also inspected for wrapping. The [completed-ride view](after-completed-desktop.png) shows the overview at its natural height alongside the longer recommendation. The top-row proportions, metric hierarchy, spacing and typography were compared with the Owner's privately supplied mockup. Fitness and mileage comparisons use neutral, accurately labeled application values; the existing dynamic recommendation and its controls remain intact. The private mockup is not included in this report. Owner acceptance of the running UI follows Analyst review.
