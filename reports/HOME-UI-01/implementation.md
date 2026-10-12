# HOME-UI-01 — RideWorks visual refinement

The established Activity Review/Home styling now covers **Activities, both
Performance views, Training State, Plan and Settings in draft PR #32**, as required
by controlling JIT §10. All main pages are implemented and locally verified.
**Ready for the reopened HARD — Analyst Gate 1.** The Owner's holistic running-app
Gate 2 remains pending; the PR is unmerged and the task remains in progress.

## Delivered presentation

Home retains the approved four facts first/left, Next Recommended Ride
second/right, recent rides, companion charts, mileage/goal and supporting
source disclosures. Activity Review retains its accepted compact header,
section navigation, charts and provenance. Neither anchor was redesigned again.

The new pages opt into `.rw-page` through the existing shell. This shares ink
`#132b48`, blue `#2563eb`, teal `#0c9c92`, stroke `#e0e8f1` and muted `#526780`,
with 14px main cards, 18–24px padding, 28px desktop/25px phone titles and visible
3px focus outlines. Existing chart series and semantic completion/warning colors
remain intact. Major standalone cards use 3px blue left edges; the Plan's
recommendation and confirmed completion retain their purposeful 4px blue/green
edges. Nested statistics, disclosures and chart plots acquire no extra stripes.
The global header/sidebar are unchanged. No framework or asset pipeline was added.

| Page | Final presentation and preserved behavior |
| --- | --- |
| Activities | Compact heading/count and filter card; one results card with aligned desktop columns and complete labeled mobile rows. Source, type, date, distance, duration, sorting, filters, pagination and activity links remain available. |
| Performance: 20-Minute History | Four aligned facts inside one compact summary; existing range/view controls, full chart, source readout and paged evidence. Long contributor titles wrap. Rolling, monthly and yearly calculations are unchanged. |
| Performance: Power Curve | Matching outer chart card and readable comparison/readout panels. Both period selectors, original series colors, hover/keyboard/touch and contributor navigation remain intact. |
| Training State | Trend and controls precede the supporting method disclosure. The actual plot remains **600px desktop / 400px mobile**, at scale 1, plus its stress strip. Fitness/Fatigue/Form, ranges, line toggles, selected-day evidence and tooltip behavior are preserved. |
| Plan | Schedule-first summary, three hard-session milestones and daily rotation receive consistent framing. Confirmed completion stays green; recommendations stay blue. Feedback, saved intent, inference corrections, dates and Home parity are unchanged. |
| Settings | Strava status/actions and annual goal form are grouped in two desktop cards, stacking on narrower screens. Labels, help, primary/secondary actions, OAuth, sync, disconnect, failure recovery and goal persistence are preserved. |

At 1440/1024/768px, the newly styled page headers measure about **36–59px**;
phone headers remain below 100px in the tested states. These measurements exclude
the existing shared navigation. Charts retain their accepted dimensions rather
than shrinking to reduce page height.

## Verification

The final full Python run passes **446 tests**. **15,435 counted Chromium
assertions** pass in this expanded verification round:

| Suite | Counted assertions |
| --- | ---: |
| Six new page surfaces × five widths, retained sources | 1,001 |
| Same matrix, generated sources | 1,028 |
| Same matrix, empty store | 553 |
| Plan before/completed controls, corrections and jumps | 76 |
| Activity Review: FIT, thin, API-only and outdoor states | 9,962 |
| Existing Power Curve: 25 comparison combinations | 1,331 |
| Training State ranges, toggles, evidence and touch | 508 |
| Real-source Home, source values and keyboard/touch | 940 |
| Home/Activity Review before/after styles and geometry | 24 |
| Actual phone touch: monthly contributor, activity rows, Settings | 12 |

All matrices cover **1440, 1024, 768, 390 and 320 CSS px**. Browser tests check
normal/empty states, complete text and source disclosures, filters/date boundaries,
unique IDs, focus, usable controls, no horizontal overflow and no browser errors.
Plan exercises actual saved intent, heavy-leg downgrade/reset, race confirmation
and restoration of automatic inference, three milestone jumps and Home parity.
Activity Review and Power Curve exercise genuine chart/source navigation and
native/thin/API distinctions. Training State retains all four ranges, three
line toggles, multi-ride/unscored/no-record states and persistent hover behavior.
Phone touch checks navigate an actual monthly-best contributor, open an activity
row and focus the annual-goal input at 390/320px. Monthly peaks provide an exact
contributor target without a rolling step boundary's pixel rounding ambiguity.

Standalone existing acceptances also pass; their uncounted assertions are **not**
added to the total:

- [Performance](performance-regression.json): independent raw-power monthly/yearly
  maxima, ties, missing-period gaps, all range/view combinations, LA/Tokyo,
  complete paged evidence, pointer/keyboard and source navigation/back.
- [Settings](settings-regression.json): entirely synthetic fake HTTP/OAuth,
  missing/configured/connected/attention, decline/reconnect, clean URLs,
  disabled sync actions, refresh, restart, disconnect retaining evidence,
  failed rebuild/manual retry/later sync convergence, no browser secrets and
  embedded FIT/API Activity Review regression.
- [Dashboard](dashboard-regression.json): synthetic sync/failure/recovery,
  annual-goal set/update/clear/restart, independent SQL/Decimal mileage and
  Performance scans, calendar boundaries and 48 tooltip lifecycle cases.

The Settings harness now scopes duplicated navigation labels to Main navigation.
The older Performance harness now recognizes accepted PC-01 mode navigation and
policy wording. Its synthetic page stub also matches `/performance` after the
existing `curve_tz` redirect, while excluding static scripts. The old exact-URL
stub served real history after redirect; this mismatch was reproduced against
pre-rollout code. Numerical oracle assertions remain intact. No Performance,
Power Curve or Training State calculation JavaScript changed in the expanded pass.
An initial Training State navigation timeout under overlapping heavy store checks
passed when the complete suite was repeated separately.

## Content, model and source preservation

Expanded baseline is pre-rollout branch head **`747e388`**, which already contains
the refined Home. [Cross-page preservation](cross-page-preservation.json) compares
**36 page states across six fixed-clock cases and two timezones**: Los Angeles and
Tokyo, October 12 morning/evening and the January 1 UTC calendar boundary.
All page text, destinations, controls/forms and embedded JSON match. The
comparison allows CSS classes, visual regrouping/order and normalized nonces;
it does not discard evidence text, links or numerical payloads.

Dashboard, Plan, Training State, Performance history/view and both Power Curve
comparison models match exactly. All **26 tables**, **1,422 original artifacts**
(hashes, sizes and mtimes), approved FTP/Elevate references, integrity and foreign
keys match. Retained-source verification uses a disposable copy; the original
accepted store is untouched. Baseline and current browser servers use separate
SQLite copies to avoid competing requests. No real source sync was performed.

Home and three Activity Review source modes have equal before/after computed
styles and geometry at desktop/390/320px. Earlier accepted Home-only evidence is
retained in [home-only-checks.json](home-only-checks.json) and
[preservation.json](preservation.json); it is separate from this round's total.
The earlier Home change also retains its keyboard mileage-tooltip scroll/resize/
Escape fix and its original source/calendar arithmetic.

## Visual evidence

Actual retained-source and generated before/after captures were compared for all
six new surfaces at all five widths. Source titles, routes, Settings/private
captures, store snapshots and full HTML stay ignored/local. These public images
contain generated activities and synthetic goal/status data only.

| Surface | Desktop before / after | 320px before / after |
| --- | --- | --- |
| Activities | [Before](cross-page/activities-before-1440.png) / [After](cross-page/activities-after-1440.png) | [Before](cross-page/activities-before-320.png) / [After](cross-page/activities-after-320.png) |
| History | [Before](cross-page/performance-history-before-1440.png) / [After](cross-page/performance-history-after-1440.png) | [Before](cross-page/performance-history-before-320.png) / [After](cross-page/performance-history-after-320.png) |
| Power Curve | [Before](cross-page/performance-curves-before-1440.png) / [After](cross-page/performance-curves-after-1440.png) | [Before](cross-page/performance-curves-before-320.png) / [After](cross-page/performance-curves-after-320.png) |
| Training State | [Before](cross-page/training-before-1440.png) / [After](cross-page/training-after-1440.png) | [Before](cross-page/training-before-320.png) / [After](cross-page/training-after-320.png) |
| Plan | [Before](cross-page/plan-before-1440.png) / [After](cross-page/plan-after-1440.png) | [Before](cross-page/plan-before-320.png) / [After](cross-page/plan-after-320.png) |
| Settings | [Before](cross-page/settings-before-1440.png) / [After](cross-page/settings-after-1440.png) | [Before](cross-page/settings-before-320.png) / [After](cross-page/settings-after-320.png) |

Earlier Home desktop/phone comparisons remain in this directory. Empty history,
missing power, long titles/advice, stale sync and disconnected Settings were
inspected alongside normal data. Fake sync acceptance covers loading/disabled
and exception recovery; source-unavailable rows remain explicit rather than
receiving illustrative values.

## Reproduce and review

```bash
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python tools/preview_home.py --data-dir /path/to/fresh-synthetic-store
.venv/bin/python tools/preview_planning_v2.py --before-ride \
  --data-dir /path/to/fresh-before-ride-store
.venv/bin/python tools/preview_planning_v2.py \
  --data-dir /path/to/fresh-completed-store
.venv/bin/python tools/verify_rideworks_visual_preservation.py \
  --data-dir /path/to/disposable-store --code-root /path/to/747e388-checkout \
  --snapshot /path/to/ignored-before.json
.venv/bin/python tools/verify_rideworks_visual_preservation.py \
  --data-dir /path/to/disposable-store --snapshot /path/to/ignored-before.json \
  --compare --output /path/to/safe-preservation.json
.venv/bin/python tools/verify_rideworks_dashboard_ui.py \
  --synthetic-dir /path/to/fresh-dashboard-store --session dashboard-regression \
  --output /path/to/safe-dashboard-result.json
.venv/bin/python tools/verify_rideworks_strava_settings_ui.py \
  --synthetic-dir /path/to/fresh-settings-store --session settings-regression
```

Run browser templates through Playwright CLI `run-code`. Locally replace
`CASE_INPUT` in `verify_rideworks_visual_browser.js` with `{base, source}` for
retained/synthetic/empty servers; in `verify_rideworks_visual_plan_browser.js` with
`[{name:'before',base,completed:false},{name:'completed',base,completed:true}]`;
and in `verify_rideworks_visual_touch_browser.js` with the synthetic base URL.
The completed Plan fixture's synthetic ride must precede the current instant
on its rider-local day; this run set it ten minutes before fixture generation
and reapplied its synthetic confirmed Recovery classification. Before/after
fixtures are disposable and browser Plan mutations never touch retained sources.
Existing Home, Activity Review, Power Curve, Training State and Performance
templates run against the retained-source review copy; Performance also takes
`BASE_URL` and `EXPECTED_COUNT`. Snapshots are private and must remain ignored.

Material files: `rideworks/static/style.css`, the existing shell/page modules,
new `tools/verify_rideworks_visual_*` verification tools and this report.
[Checks](checks.json) record current aggregate results.

Branch: `task/home-ui-01-dashboard`; [draft PR #32](https://github.com/k14krug/rideworks/pull/32).
The unified real-source app remains running locally at
`http://127.0.0.1:8801/?home_tz=America%2FLos_Angeles`, with synthetic preview at
`http://127.0.0.1:8803/`. Visit all six navigation destinations and an Activity
Review for one holistic review. Analyst Gate 1 and Owner Gate 2 are pending;
there is no implementation blocker. Do not merge or mark done before acceptance.
