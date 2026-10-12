# HOME-UI-01 — Home dashboard visual refinement

Implemented the Owner-requested Activity Review visual language on real Home.
**Ready for HARD — Analyst Gate 1; not accepted.** Owner running-page Gate 2
remains required. Baseline: accepted `main` at `516cbd7`.

## Delivered presentation

- A compact Home title/subtitle and source-accurate last successful sync link.
  Missing sync is explicit. The application shell and navigation are unchanged.
- Four compact facts lead the page, with **Next Recommended Ride** beside them:
  This Week, Last 7 Days, current 42-day best, and latest eligible 20-minute ride.
  These preserve their distinct periods, supplied values and contributor links.
- Recent Activities leads the body, with real dates, titles/types, distance,
  duration and source-supplied average power. Narrow rows stack with visible
  field labels and retain every source value and activity link.
- Training State and the accepted 20-minute Performance chart are companion
  sections. Fitness/Fatigue/Form and start-of-day Form meaning remain visible.
  No illustrative Training State sparkline or extra analytical widget was added.
- Mileage Progress and Annual Mileage Goal appear together. The actual 12-week
  bars, outlined partial current week, needed-average line, YTD/goal percentage,
  remaining distance, calendar pace and edit-goal link remain unchanged.
- Recent performance context, weekly detail and complete source/calendar evidence
  remain in semantic supporting disclosures. Duplicate comparison prose moved
  out of the latest-effort fact; the exact comparison and method stay inspectable.
- Scoped `.home-redesign` rules use accepted ink/blue/teal and stroke colors,
  restrained 14px panels and 18–24px padding. The header has no banner/gradient.
  All other page styles and global navigation retain their accepted behavior.

The Owner's latest running-page corrections are implemented on the same PR:
facts first/left in actual DOM and keyboard order, recommendation second/right
with a 1:1.25 width ratio. Both align at the top without stretching the shorter
card. The eight main cards have thin #2563eb left edges: 3px except the next ride's
existing 4px. Individual facts, nested completed context, charts and disclosures
have no additional blue stripes. The restrained treatment is retained for Owner
review. The Owner corrected "not" to "now" on 2026-10-12: the Activity Review/Home
design language should extend to the remaining RideWorks pages through separate,
focused tasks and running-page reviews. HOME-UI-01 changes Home only; its scoped
styles preserve unrelated pages within this PR. The correction requires no
additional Home implementation changes. Phase 6 remains deferred.

## Reference and deliberate adaptations

The Analyst HTML proposal and historical Dashboard PNG were inspected in Chromium.
Real before/after captures at **1440, 1024, 768, 390 and 320 CSS px** were compared;
private captures, titles, routes and store snapshots remain ignored/local.

The proposed hierarchy is retained: facts/recommendation, recent rides and
companions, mileage/goal, then supporting evidence. The existing global shell
stays intact, including its mobile navigation. No invented FTP, fitness points,
race classification, recommendation, chart traces or example values were copied.

The four facts form a 2×2 matrix on desktop/phone; intermediate widths use a
compact four-column strip above the recommendation. Missing/long values wrap.
Advice has no arbitrary minimum height; supported completed-today context remains
inside the shared recommendation, so multiple actual rides naturally need more
space. Training State retains its real text values rather than the proposed fake
mini chart. The accepted SVG chart generators are untouched; mobile text size is
increased through scoped CSS while SVG values, paths, points and links stay exact.

On the captured real desktop Home, facts and recommendation start at **155px**,
with widths **544 / 680px** and Recent Activities starting at **449px**. At 320px
the facts start at **423px**, followed by the recommendation at **771px**. The
requested stacked order moves advice below the facts; it remains much higher
than accepted main's **1709px** placement. The unchanged global mobile shell
accounts for the preceding navigation space.
This is measured placement, not a claim that every source state fits one screen.

## Interaction correction

Browser testing found that focusing an offscreen mileage week scrolled the chart
into view, then its scroll listener immediately hid the keyboard tooltip. Home's
small existing script now repositions the focused readout on scroll/resize.
Escape clears that focus-readout state so subsequent scrolling/resizing does not
reopen it. Pointer, keyboard and actual touch still display the original server
mileage value; no chart arithmetic or source calculation moved into JavaScript.

## Verification and preservation

The full Python suite passes **446 tests**, including the existing source/calendar,
Plan/Home parity and completed-today contracts plus one new scoped markup/source
state contract. Prior three-card layout assertions now verify the JIT-required
four facts; numerical expectations and independent mileage checks remain intact.

Before/after fixed-clock comparison covers **six cases**: Los Angeles and Tokyo,
October 11 morning/evening and the January 1 UTC year boundary. It compares exact
`dashboard-data`, each chart's entire SVG by ID, fact/recommendation/training
content, rendered comparison/method and evidence rows, plus Dashboard,
Performance, Training State and Plan model hashes. Every comparison passes.
**All 26 tables and 1,422 source originals** retain hashes, sizes and modification
times; approved FTP/Elevate hashes, integrity and foreign keys also pass.

The existing synthetic Dashboard browser acceptance passes normal fake sync,
goal set/update/clear/restart, LA/Tokyo calendar boundaries, independent SQL/
Decimal mileage and direct-scan Performance checks, source averages, immediate
bar/needed-line pointer/keyboard inspection, and intentional failure/recovery.
Its pre-Phase-4 fingerprint assumption was updated for the three accepted derived
caches populated/invalidated by that deliberate sync flow; source tables and v1
results remain protected. The separate unchanged-input check compares **all**
tables, including those caches. Its reported schema now reflects the actual
fixture instead of the older hardcoded schema 7.

**14,256 counted Chromium checks** pass after the Owner corrections:
940 real / 883 synthetic Home,
9,962 Activity Review, 1,331 existing Power Curve, 510 Training State, 14 accepted-page,
28 before/completed/empty recommendation, 10 focus-scroll/resize/Escape, and 48
unchanged-page computed-style checks across eight routes and three widths,
plus 530 refinement checks over four scenarios at all five widths. Those cases
cover before a ride, one completed ride, empty history and generated long
contributor names/large mileage. Real and synthetic Home also cover short advice,
long explanations and multiple completed rides. DOM/focus order, all eight
3px/4px rounded borders and no nested blue stripes pass. Normal fact/link text
meets 4.5:1 contrast and the blue accent exceeds 3:1 on the actual white cards.
An initial overlapping-database comparison received a server error; repeating
without competing requests passes all 48 other-page style/geometry comparisons.
The final unchanged-input preservation check also passes after browser regressions.
The standalone Dashboard acceptance also passes its independent checks, calendar
cases, fake sync/failure/recovery, goal settings and 48 tooltip lifecycle cases;
these are reported separately rather than added to the counted total.

Browser aggregates are in [checks.json](checks.json); fixed-clock equality is in
[preservation.json](preservation.json), and the standalone Dashboard result is in
[dashboard-regression.json](dashboard-regression.json). Private snapshots and
routes never belong in these artifacts.

## Reproduce

Use a disposable retained-source copy; the accepted source store is untouched.
Snapshots contain private evidence and must stay in ignored local storage.

```bash
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python tools/preview_home.py --data-dir /path/to/new-synthetic-preview
.venv/bin/python tools/preview_home.py --long-facts \
  --data-dir /path/to/new-synthetic-wrapping-preview
.venv/bin/python tools/verify_home_preservation.py \
  --data-dir /path/to/disposable-store --code-root /path/to/accepted-main \
  --snapshot /path/to/ignored-before.json
.venv/bin/python tools/verify_home_preservation.py \
  --data-dir /path/to/disposable-store --snapshot /path/to/ignored-before.json \
  --compare --output /path/to/safe-preservation.json
.venv/bin/python tools/verify_rideworks_dashboard_ui.py \
  --synthetic-dir /path/to/new-synthetic-store --session home-ui-legacy \
  --output /path/to/safe-dashboard-regression.json
```

Run `tools/verify_home_browser.js` through Playwright CLI `run-code`, replacing
`CASE_INPUT` locally with `{base, baseline, source}` (`private` or `synthetic`).
Both servers must use the same disposable store and equivalent local configuration;
Settings' credentials-configuration status can otherwise change panel height.
The configuration is read locally and never copied into reports or Git.
Existing Activity Review, Power Curve and Training State browser tools were rerun
against the disposable current server. Scenario previews reuse
`tools/preview_planning_v2.py` with and without `--before-ride`, plus an empty store.
Run `tools/verify_home_refinements_browser.js` with `CASE_INPUT` replaced locally
by an array of `{name, base, longFacts}` cases: `before`, `completed`, `empty` and
`long-facts` (only the last sets `longFacts: true`). All fixtures are generated,
disposable source evidence, including the intentionally exaggerated wrapping case.

## Synthetic screenshot comparison

These captures render generated source evidence through actual RideWorks. They
contain only synthetic activities and an explicitly set synthetic annual target.
The extended Activity Review preview includes several completed-today source
modes; their retained completion context makes the advice card longer than the
real single-ride case. It is evidence of responsive behavior, not fabricated advice.

| View | Before | After |
| --- | --- | --- |
| Desktop | [Before](synthetic-before-desktop.png) | [After](synthetic-after-desktop.png) |
| 320px phone | [Before](synthetic-before-320.png) | [After](synthetic-after-320.png) |

The Owner-refinement comparison uses the previous Home implementation, rather
than accepted main, as its before state. All five widths were captured and
inspected locally; representative source-neutral captures are retained here.

| View | Before Owner corrections | Refined Home |
| --- | --- | --- |
| Desktop | [Before](synthetic-owner-before-desktop.png) | [After](synthetic-after-desktop.png) |
| 320px phone | [Before](synthetic-owner-before-320.png) | [After](synthetic-after-320.png) |

## Review handoff

Running real-source review: `http://127.0.0.1:8801/?home_tz=America%2FLos_Angeles`.
Synthetic review: `http://127.0.0.1:8803/?home_tz=America%2FLos_Angeles`.
Branch `task/home-ui-01-dashboard`; [draft PR #32](https://github.com/k14krug/rideworks/pull/32),
current head and handoff are recorded on the PR and in `STATUS.md`. Stop again at **HARD — Analyst Gate 1** for code, source parity, interaction
and visual review. Owner Gate 2 must accept the running dashboard before merge.
Task remains `in_progress`. Future page-specific visual updates follow the Owner's
corrected direction; they are outside this Home PR. Phase 6 remains deferred.
