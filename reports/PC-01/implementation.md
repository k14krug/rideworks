# PC-01 implementation — Analyst Gate 1 review

PC-01 is implemented on `task/pc-01-power-curves`, draft PR #28. This handoff
stops at **HARD — Analyst Gate 1**; the task remains `in_progress`, with
`STATUS.md` `ready_for_review`. Owner Gate 2, acceptance and merge are pending.
Phase 6 remains deferred. The prior source-contract stop is resolved by the
Analyst's committed JIT §13; the historical preflight report is retained.

## Working feature

- Performance retains its existing default **20-Minute History**, calculation,
  summaries, Range/View/Evidence controls and historical values. **Power Curve**
  offers two independent periods: Last 6 weeks, Previous 6 weeks, Year to date,
  Previous calendar year and All time. Its initial comparison is Last 6 weeks
  versus All time, the design's working default. Overlap is disclosed.
- Activity Review preserves its streams, source summary, best-20/recent context
  and planning content. A separate curve section after the stream chart and a
  header jump link provide **This ride vs Previous 6 weeks**, Prior 12 months,
  and All earlier history. For thin/unsupported reviews it still shows honest
  current/baseline availability. A baseline can be inspected without a current
  curve, and a current curve can be inspected with an empty baseline.
- Both views use logarithmic duration axes, watts, distinguishable solid/dashed
  lines and circle/square inspection markers. Hover, keyboard, pointer and
  actual Chromium touch selection snap to evaluated durations. The readout
  exposes actual contributing activity/date/link for each series and neutral
  displayed-watt differences. Exact mean, integer sum/sample count, source,
  extraction/API identity, observed window and timer limitations are inspectable.

The actual private review copy runs at:

- `http://127.0.0.1:8782/performance?curve=1`
- Activity Review through its contributing links or Activities. A selected
  October 7 review route is retained in the ignored local handoff file
  `local_data/pc-01-implementation/owner-activity-route.txt`.

The accepted original store was not used as a write target. The running copy
comes from the accepted P5-01 review snapshot. No live API fetch was needed.

## Numerical/source contract

`rideworks/power_curve.py` implements `observed-mmp-grid-v1` /
`virtual-duration-power-v1`. Integer prefix sums search supported continuous
runs; maxima use exact sums and retain the earliest source-order window.
Each run has valid absolute one-second timestamps and nonnull nonnegative
integer watts. Zero is valid; nulls, missing/duplicate/backwards timestamps
and distinct verified active intervals split runs. No interpolation, pause
stitching, smoothing, summary substitution or estimated watts occurs.

FIT event endpoints are observations under JIT §13. Independently
session-verified intervals use inclusive observed endpoints; a shared
stop/start observation belongs deterministically to the earlier group.
Distinct groups are never stitched. Unverified/contradictory timer reports
do not mask recorded samples. Source timer quality distinguishes absent,
unpaired/invalid, paired-but-unverified and session-verified evidence. Evaluated
efforts extending outside an unverified paired scope retain an inspectable
discrepancy flag. This is not a claim of timer-verified active duration.

For a native source with an accepted best-20, a changed 1,200-second maximum
or earliest maximal window after verified segmentation raises an explicit
Analyst-review error. No such concrete conflict occurred in the retained
dataset. `analysis.py`, `performance.py`, `performance_view.py`,
`recent_context.py`, Training State and planning algorithms are unchanged.

Source selection reuses existing classification and file watt precedence.
At each duration, one supporting native candidate is defensible; competing
supporting files make that duration ambiguous. A short second file cannot
replace the accepted lone 20-minute candidate. Summary/file watt evidence
blocks API rescue even when native long windows are missing. With no file
watt evidence, current paired device-confirmed high-resolution full-length
API streams may qualify at supported durations, including short ones.
RFC3339 `Z` starts are explicitly supported on Python 3.10. API timing,
pairing and current summary identity are validated; no network behavior changed.

The common duration grid calculates every second 1–30, then integer-ceiling
7% geometric steps (`ceil(d × 1.07)`), plus familiar anchors such as 60/300/
1,200/3,600/7,200 seconds. It extends without a fixed upper cap. This is
approximately 7% spacing, with at most one extra second from ceiling, not an
every-second fitted curve. A curve ends at its last supported **common grid**
anchor, potentially slightly before the longest observed run; the endpoint is
not extrapolated or treated as another exact arbitrary duration.

Period membership uses absolute `[start, end)` boundaries. Activity prior six
weeks is exactly `[ride start − 42 × 24 h, ride start)`, excluding identity,
same-start and all future rides. Its lower boundary is inclusive as directed
by PC-01, unlike the preserved older best-20 recent-context panel's exclusive
lower endpoint. Prior 12 months uses UTC calendar subtraction; Performance
years use the browser's IANA calendar timezone. Unknown absolute starts cannot
establish historical membership. Exact period ties choose earliest absolute
activity start, then Activity ID.

## Verification and scale

[Independent verification](verification.json), [runtime](runtime.json),
[concurrent build checks](build-availability.json), [browser/test counts](checks.json),
and [accepted-behavior equality](accepted-behavior.json) are source-neutral.

| Check | Result |
| --- | ---: |
| Activities evaluated / current cached profiles | 1,443 / 1,443 |
| Profiles with supported observed power | 1,271 |
| Native FIT / GPX / API power profiles | 1,262 / 2 / 7 |
| Independently verified exact duration results | 122,112 |
| Shared native best-20 raw/display/earliest-window parity | 1,022 |
| Shared API best-20 raw/display/offset parity | 7 |
| Profiles available below 20 minutes only | 242 |
| Profiles with hour-plus anchors | 241 |
| Shortest / longest calculated anchors | 1 s / 15,189 s (4 h 13 min 9 s) |
| Longest supported observed run | 16,240 s (4 h 30 min 40 s) |
| Distinct common anchors across the archive | 133 |
| Full Python / focused feature tests | 440 / 24 |
| Private / synthetic Chromium checks | 1,331 / 614 |
| Additional accepted-page / native-review / true-touch checks | 14 |
| Source tables / original artifacts preserved | 20 / 1,422 |
| SQLite integrity / foreign-key violations | ok / 0 |

The independent archive oracle uses prefix missing/edge counts over the
original sequence, separate from production's contiguous-run search. It
checks **every cached duration result**, not only selected familiar points,
including sums, raw averages, rounding, earliest record indices, timestamp
bounds and qualifying-window counts. It verifies a real historical envelope
independently (109 anchors). All native/API shared best-20 sources are counted,
so missing API cases cannot silently pass. Small independent brute-force
tests cover many synthetic durations, zero/low values, ties, nulls, gaps,
duplicate/backwards timing and changes in best windows.

Tests cover exact stop endpoints, distinct verified groups, unverified
post-stop observations, source ambiguity, short-only evidence, API restrictions,
no summary/outdoor substitutes, no future leakage (including next-day/2027
and same-day later rides), inclusive/exclusive period bounds, timezone calendars,
missing absolute starts, empty baselines, native reextraction, current API
selection, stale/method signatures, restart, migration rollback, atomic build
failure, changed evidence during a build and normal sync failure/retry. Mocked
sync confirms committed sources/checkpoints survive a derivation failure,
later sync retries without extra stream fetches, unchanged native profiles are
reused, and changed API observations update only their derived profile.

Cached chart/history access is verified with raw native/API read methods
disabled. Browser hover/keyboard/touch/period changes create no network requests.
Both period selectors exercise all 25 combinations. Arrow/Home/End/Enter,
tabbed source links, exact readouts, correct contributor links, historical
baseline checks, empty/outdoor states and 1440/390/320 layouts pass with no
JavaScript errors or horizontal overflow. Additional checks exercise the
original Performance controls, Home mileage/next ride, Plan milestones,
Training State and a real `hasTouch` Chromium context.

Source table rows are equal to the read-only baseline; originals match retained
SHA-256 and byte sizes. Approved FTP and Elevate hashes remain unchanged.
Performance, Training State v4 and Plan outputs match a separate baseline copy
at fixed `2026-10-11T17:00:00Z`. Detailed activity outputs and actual screenshots
remain ignored locally.

## Build behavior and practical limits

Schema 10 adds only `power_curve_profiles`, containing version/signature,
calculated time and derived profiles. It does not duplicate raw streams.
Source/extraction/classification/date/current API observation and timer evidence
invalidate inputs. Changed profiles are not plotted until rebuilt. Normal sync
converges local profiles after committing existing sources; explicit rebuild
is available from the panel and CLI. Hover/page views never rebuild.

An initial archive build took ~22 seconds. Final isolated forced build took
**22.810 seconds**, with **0.693 seconds** for publication; an unchanged rebuild
reused all 1,443 profiles in **0.368 seconds**. Three cached comparisons took
**611–690 ms**. Peak builder RSS was **140.6 MiB**; the process including a
full cached comparison reached **340.2 MiB**. The JSON cache size is recorded
in `runtime.json`. This simple local cache trades memory for fast reproducible
inspection; arbitrary-duration exact requests are outside the evaluated grid.

The first builder held an archive-long write transaction and a concurrent
Home request could fail on a lock. That implementation defect was corrected:
computation now uses short per-ride read snapshots, followed by one atomic
publication transaction that rechecks signatures. A source changed meanwhile
stays pending. **18 accepted-page requests during a real forced archive build
passed**, across Home, Plan, Training State and Performance, with no SQLite
lock failures. Under that deliberate same-process CPU stress the build took
52.788 seconds, publication 0.875 seconds, and page times were 1.675–4.845 s;
the process peaked at 449.5 MiB. Full builds still compete for CPU, so the
initial explicit update can slow pages, but it no longer holds a long write
lock or recomputes on ordinary inspection. This is reported, not hidden as
an instantaneous background update.

## Visual review

The actual two-screen mockup was inspected locally in Chromium before coding.
Production follows its large plot, independent comparison controls, two-series
legend/readouts, source actions and RideWorks palette/sidebar. Intentional
differences: Activity uses an added section/jump link rather than hiding
existing ride charts behind tabs; the shared readout supplies exact source
details instead of an illustrative coaching sidebar. Mobile keeps the existing
RideWorks navigation, stacks controls/readouts and thins axis ticks for legibility.
Rendered plot lines use no area fill (the illustrative mock SVG had a black
fill artifact). No mock wattages were copied into production results.

Only computed **synthetic** production captures are committed:

- [Performance desktop](synthetic-performance-desktop.png),
  [390px](synthetic-performance-390.png), [320px](synthetic-performance-320.png).
- [Activity desktop](synthetic-activity-desktop.png),
  [390px](synthetic-activity-390.png), [320px](synthetic-activity-320.png).

The final Activity capture uses a synthetic interrupted interval ride with two
real synthetic prior-six-week contributors. Its current curve stops naturally
before the longer baseline; the gap is never repaired. Screenshots of actual
source-backed Performance and both native/API reviews remain under ignored
`output/playwright/`. All final captures were visually inspected.

## Reproduction

All tools accept supplied local store paths. The review copy is disposable;
the baseline path below is used read-only by source verification.

```bash
.venv/bin/python -m rideworks --data-dir /path/to/review-copy rebuild-power-curves --force
.venv/bin/python -m rideworks --data-dir /path/to/review-copy rebuild-power-curves
.venv/bin/python tools/verify_power_curves.py --data-dir /path/to/review-copy \
  --baseline-dir /path/to/baseline --aggregate-output /path/to/safe-verification.json
.venv/bin/python tools/verify_power_curve_build_availability.py \
  --data-dir /path/to/review-copy --aggregate-output /path/to/safe-availability.json
.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_power_curve.py' -q
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python tools/preview_power_curves.py --data-dir /path/to/new-empty-preview
.venv/bin/python -m rideworks --data-dir /path/to/review-copy serve --port 8782
```

Playwright uses the installed skill wrapper for Chromium startup, then the CLI
directly for commands (the wrapper's default `--config` is accepted by `open`,
but this CLI version rejects that option on `run-code`):

```bash
/home/kkrug/.codex/skills/playwright/scripts/playwright_cli.sh --session pc01 \
  open http://127.0.0.1:8782/performance
npx --yes --package @playwright/cli playwright-cli --session pc01 \
  run-code "$(cat tools/verify_power_curves_browser.js)"
npx --yes --package @playwright/cli playwright-cli --session pc01 \
  run-code "$(cat tools/verify_power_curves_regression_browser.js)"
```

Synthetic browser coverage uses a separately served preview on 8783. Its
generated titles are explicitly synthetic. Actual Activity identities,
source dates/titles, original recordings, local databases, credentials and
private screenshots are not committed. Gate 1 needs Analyst review of this
implementation/evidence; Owner Gate 2 needs the running two-view feature.
