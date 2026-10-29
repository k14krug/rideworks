# HOME-UI-03 — Mileage by Year

Status: ready for HARD — Analyst technical review in [draft PR #51](https://github.com/k14krug/rideworks/pull/51). HARD — Owner running-UI visual approval follows. The task remains `in_progress`; no production rollout is authorized.

## Implementation

`rideworks/dashboard.py` groups the existing eligible presentation rows by browser-local date and accumulates their already-selected file or current API distances. It uses the same as-of exclusion as YTD. It creates at most one point per recorded date plus year-start/current-as-of endpoints, and no series when a year has no known distances. Current YTD ends at the as-of date; prior years stop at their last known distance because the store does not establish historical coverage through December 31. The card explicitly warns that history may be incomplete and counts activities with unavailable distance. Source dates without a timezone retain their supplied date; missing dates remain excluded and are reported in existing diagnostics.

`rideworks/home.py` renders the three series as calendar-month-aligned steps, using each month's actual length so March aligns across leap and common years. It retains the existing YTD, remainder and unrounded needed-weekly arithmetic, applying a ceiling only for display. It handles reached, absent, unknown-distance and year-end goals, with Settings navigation for absent goals. It removes the superseded progress bar and calendar-pace block. `rideworks/static/style.css` and `rideworks/static/home.js` add compact styling and pointer/keyboard endpoint details. The existing weekly tooltip remains functional.

## Verification

- `.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_dashboard.py' -q`: 28 passed. Added synthetic checks for source/date selection, missing and future activities, noncycling exclusion, timezone and rollover, leap-day alignment, absent years, prior-year cutoff, goal states and the 55.0/55.1 ceiling boundary. The existing integration test exercises file precedence and API fallback.
- `DEBUG=0 .venv/bin/python -m unittest discover -s tests -q`: 512 passed after enabling loopback for existing local-server tests. The sandboxed attempt failed with socket permission errors; it was rerun with loopback access. The last subsequent changes were the tooltip markup/JavaScript and its targeted browser verification; the focused Python suite was rerun afterwards.
- `node --check rideworks/static/home.js`: passed.
- Chromium checked the synthetic preview at 1440, 1024, 768, 390 and 320 CSS px: 12 month ticks did not overlap and no page overflow occurred. At 1440 the cards share a row: Mileage Progress was 359.58 px high and Mileage by Year was 337.04 px. At 1024 and below the accepted layout stacks them. The current endpoint matched the accepted YTD aggregate; prior endpoints stopped at the last known synthetic ride. Focus and hover exposed dated endpoint values, Escape dismissed the readout, and the weekly tooltip still appeared. Activities, Performance, Training State, Plan and the Settings annual-goal anchor loaded successfully. The synthetic card was visually compared with the private reference for hierarchy, colors and compact presentation; no private image or rider data was copied.
- The synthetic preview's 2024/2025/2026 dates and goal are fixture values only. Browser measurements are from an interactive integrated Chromium session; no screenshot is included in this report. Owner running-app acceptance remains outstanding.

## Reproduction

Use a new empty directory and an installed project environment:

```bash
.venv/bin/python tools/preview_home_ui03.py --data-dir /tmp/home-ui-03-preview
.venv/bin/python tools/verify_home_trends.py --data-dir /tmp/home-ui-03-preview --serve-port 8791
.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_dashboard.py' -q
DEBUG=0 .venv/bin/python -m unittest discover -s tests -q
node --check rideworks/static/home.js
```

Open `http://127.0.0.1:8791/?home_tz=America%2FLos_Angeles` in a browser and inspect the five widths, card heights, numeric month labels, endpoint focus/hover, and destination pages. The fixture uses synthetic source summaries and the existing synthetic preview generator; no live API requests are made. The fixed-clock server uses 2026-10-28, while the base preview generator also uses the current date for some synthetic activities.

## Limits

Coverage is not independently known. Missing years are not represented as confirmed zero years; a line represents recorded mileage, not proof of complete history. The current YTD still follows the accepted dashboard aggregate, including its existing empty-period behavior. No schema, source eligibility, training model, personal data or production configuration was changed. Technical acceptance and the Owner's visual acceptance are separate remaining gates.

## Owner-directed refinement (§12)

The existing branch incorporates the Analyst's §12 amendment. The chart now clips the previously computed January-to-date series to the previous three months, current month and next month, bounded by January and December. It carries the cumulative value into the left edge, preserves the current as-of endpoint, and allows past-year records through the right edge. The legend uses the full recorded year rather than the viewport, with YTD, recorded and no-data labels; the coverage warning remains. Blue, amber and teal lines also use distinct solid/dash patterns. Goal arithmetic and source selection were unchanged.

- `.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_dashboard.py' -q`: 29 passed. Synthetic coverage includes October, January, February, November and December windows, cumulative values before the viewport, past-year November data, full-year totals after the window, the exclusive end boundary, and the original leap/date/source/goal cases.
- `DEBUG=0 .venv/bin/python -m unittest discover -s tests -q`: 513 passed with local loopback enabled.
- `node --check rideworks/static/home.js` and `git diff --check`: passed.
- The synthetic fixed-clock preview was checked in Chromium at 1440, 1024, 768, 390 and 320 CSS px. October labels read Jul–Nov without overlap; no page horizontal overflow was observed. At 1440 the annual card measured 332.05 px against Mileage Progress at 359.58 px; at 1024 and below the cards stacked. At 320 the legend wrapped without clipping. Computed series colors were blue `#2563eb`, amber `#d97706`, and teal `#0d9488`, with solid, long-dashed and short-dashed strokes. The synthetic current endpoint and YTD both read 1,163.7 mi; prior legend totals were 874.4 and 852.0 recorded miles. Keyboard focus and Escape operated the endpoint readout; dispatched pointer-enter/leave events exercised its pointer handler. The weekly readout and all five Home section headings remained present, and Activities, Performance, Training State, Plan and the Settings annual-goal page returned successfully. The synthetic rendering was inspected; the private reference remains uncommitted. Owner running-app approval remains outstanding.

Reproduce using the commands above with a new disposable data directory. Inspect abbreviated month labels and full-year legend totals in place of the superseded numeric-axis check. The browser's direct pointer-hover automation did not reliably reach the SVG endpoint in this integrated session; keyboard focus and the dispatched pointer handler were verified, but a physical-pointer check remains for running-UI review.
