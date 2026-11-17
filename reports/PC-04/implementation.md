# PC-04 implementation verification

The initial 95%/minimum findings below are superseded by the Owner-directed
revision in the final section of this report.

Power Curve period comparisons now consume the same cached standard elapsed
profiles and shared period aggregation as Activity Review. The selected-ride
minimum and off-grid ride endpoints do not enter period bests. The existing
strict consumers, elapsed calculation rules, cache format and source admission
remain unchanged. The pinned inspector describes elapsed work, coverage,
timing buckets and source evidence.

## Verification

- `env -u DEBUG .venv/bin/python -m unittest discover -s tests`: **662 passed**.
  Focused elapsed tests passed **20** and focused power-curve tests **24**.
  The first sandboxed run could not open local sockets; a run with an inherited
  invalid `DEBUG` value also caused subprocess errors. The final run used local
  networking and removed that unrelated environment value.
- Synthetic elapsed tests cover an independently checked winner, unrounded
  values and tie ordering, equal period evidence across both views, period
  boundaries/timezones, partial and fully stale caches, strict versus elapsed
  windows, excluded minimum/off-grid endpoints, and a standard window with
  pause, estimate and unknown seconds. Strict history and Activity Review
  regression checks passed.
- A disposable copy of retained Dev data was examined at one fixed as-of time,
  without rebuilding or fetching data. Both methods included the selected ride;
  the elapsed period had a longer supported final anchor than the former strict
  period, and the selected ride won three elapsed anchors. Its individual
  recorded-power minimum remained outside the period. The complete selected
  Activity Review comparison payload matched the pre-change implementation.
  Specific personal values and identities were reported privately to the Owner.
- `tools/verify_pc04_presentation_browser.js` passed **35 Chromium assertions**
  covering exact delta and links, missing anchors without bridging, evidence,
  empty/partial periods, square-root mapping, and narrow-width containment.
  Retained-data Chromium checks covered both selectors, pinning, keyboard,
  disclosure and native links at desktop, 390 px and 320 px; no overflow was
  found. Touch pin, link, details and scroll passed. A deliberately stale
  profile on the disposable copy showed the update action and partial curve;
  its signature was restored after the check.
- No schema, strict calculation, production data, production deployment or
  Strava fetch was changed. Private activity data and screenshots are omitted.

This handoff stops at HARD — Analyst Gate 1; Owner running-Dev review follows
Analyst clearance. No merge or production deployment is authorized.

## Owner-directed 90% revision

Both views now use the same 90% observed non-pause floor. An isolated missing
second can still be estimated; remaining unknown time adds no work. The exact
individual endpoint is an ordinary line point, while only common-grid points
compete in period bests. The elapsed method/policy identities changed, so old
profiles are stale instead of being relabeled. Strict consumers are untouched.

The disposable retained-data copy initially reported 1,463 stale profiles; the
existing elapsed rebuild computed 1,463 and left zero pending. No original
source, production store, or Strava data was modified or fetched. A later
release should use the existing **Update power curves** action or normal sync
convergence; stale profiles remain unavailable until the update completes.
The selected ride had all 118 evaluated anchors supported through its endpoint,
with no diamond. Its endpoint is 91 W at 94.26% coverage: 6,177 observed,
1 estimated, 375 unknown and zero confirmed-pause seconds. A separate exact
1:48:00 calculation is 92 W. At the same fixed as-of time as the previous
comparison, Last 6 weeks ends at 1:45:00 / 91 W, won by that ride; it wins
eight common-grid points, all identical to its Activity Review cached points.

Focused elapsed tests passed **23**; the full local-network suite passed **665**.
The tests cover exact 90%/below-90%, observed zero versus unknown, timing
buckets, source/timer admission, former 90–<95% points in history, off-grid
exclusion, stale profiles, and strict regressions. Synthetic Chromium passed
58 Activity Review and 35 period assertions. Twelve checks on the disposable
ride verified the solid endpoint, no diamond, assumption notes, pinned coverage,
period point and no page overflow at desktop, 390 px and 320 px.

### Pinned Sauce comparison (research only)

The same paired retained time/watts have first/last offsets 0 and 6,553 s;
the final observation was already present. Sauce was called directly via
`peakPower` at its pinned revision, with no added terminal observation and no
null-to-zero coercion. Its trainer active stream below is **inferred** from
aligned retained moving/cadence/power streams, not a confirmed pause record.
The no-active variant uses Sauce's own gap rules. Values below are unrounded W;
the observed-only column is an independently optimized elapsed-window baseline
using recorded work only. Window bounds are elapsed offsets in seconds.

| Duration (s) | RideWorks | Observed-only | Sauce inferred (bounds) | Sauce no-active (bounds) |
| --- | ---: | ---: | --- | --- |
| 4,804 | 92.950 | 92.946 | 94.164 (1749–6553) | 92.950 (1749–6553) |
| 5,400 | 90.156 | 90.152 | 91.236 (213–5613) | 90.156 (213–5613) |
| 6,000 | 91.047 | 91.043 | 92.019 (214–6214) | 91.047 (214–6214) |
| 6,480 | 91.529 | 91.526 | 92.429 (36–6516) | 91.529 (36–6516) |
| 6,553 | 90.962 | 90.960 | 91.844 (0–6553) | 90.954 (0–6553) |

The inferred winners contain 55 value pads and 5,851 watt-seconds of pad work;
their zero-pad counts are 51 at 4,804 s and 321 for each longer window. The
no-active winners contain one value pad / 19 watt-seconds and respectively
105 or 375 zero pads. Counts exclude the rolling reference value; no break pads
occurred. The methods assign timestamps to sample intervals differently, so
matching values or differing window offsets do not establish Strava's method.
Reproduce the Sauce portion with the pinned public checkout and private aligned
streams JSON using `node tools/compare_sauce_peak.mjs <checkout> <streams.json>
4804 5400 6000 6480 6553`; inputs and private screenshots remain outside Git.

## Section 3 diagnostic — stop for Analyst review

On the disposable retained-data copy, an unsupported far-tail anchor comes
from one older FIT profile whose reported elapsed duration is vastly longer
than its recorded power and timer summary. The timer boundaries are unverified
and its full elapsed endpoint is not supported.

Separately, the same profile supplies a plotted period winner whose window ends
after the last recorded power observation and includes unknown seconds. The
current rule treats those unknown seconds as zero work. The suspect source
summary therefore affects a supported point, not just an unsupported axis
anchor. Whether that window should be eligible requires Analyst review; this
diagnostic does not alter source data, admission rules, cached calculations or
chart extent.

The longest supported historical comparison point comes from a separate FIT
source whose recorded timestamps and elapsed summary support its duration; it
has complete observed coverage. Per the explicit stop condition, the requested
axis and period-option changes have not been implemented pending review. Exact
personal timings and measurements were reported privately to the Owner.

## Sections 3–4 resolution

The elapsed method/policy identity now invalidates earlier derived profiles.
Native FIT windows are restricted to the observed power span at any boundary
that is not independently corroborated by the verified timer scope. The original
elapsed summary, records and strict results are untouched. Clipped rides expose
the scope reason, have no invented full-ride endpoint, and retain eligible
common-grid efforts. API source admission is unchanged.

On the disposable retained-data copy, all 1,463 old profiles became pending;
the derived-only rebuild completed with zero pending. Among 748 FIT profiles
with supported points, 399 were clipped. Of those, 220 lost at most one second
of reported scope; 14 lost more than five minutes. The latter were investigated:
their removed trailing bounds lacked matching verified final timer boundaries;
one had an otherwise verified timer that stopped before the summary end. No
clipped profile lost all supported points. Longest supported duration decreased
for 376 clipped profiles and stayed the same for 23, including cases where the
previous off-grid full endpoint no longer qualified. Hash comparisons of
retained records, sources, extractions, strict power profiles and performance
history matched before and after the rebuild.

The previously padded winner no longer comes from the suspect FIT profile; a
different ride now supplies the period result at that duration. Shorter
common-grid efforts from the suspect file remain eligible. The selected API
ride's full endpoint and Last 6 weeks winner are unchanged. The All earlier
history chart now ends at the independently supported comparison point instead
of the unsupported far-tail anchor, without imposing a maximum duration.
Exact private measurements were reported to the Owner, not added to Git.

Activity Review now offers prior two- and five-year calendar lookbacks; both
Performance selectors offer last two and five years. They retain their
respective UTC/selected-timezone, half-open and self-exclusion conventions.
The chart domain retains the validated selected-ride endpoint and evaluated
gaps inside the supported domain, while dropping unsupported far-tail anchors.

`env -u DEBUG .venv/bin/python -m unittest discover -s tests` passed **667**
tests; focused elapsed tests passed **25**. Synthetic Chromium passed **63**
Activity Review and **41** Performance checks, including unsupported far tails,
interior gaps, an unsupported selected endpoint, an empty chart, and a
legitimate duration longer than eight hours. Fifteen retained-data Chromium
checks covered the actual All earlier history axis, endpoint, winner links,
new controls, selector reset, clipped-file explanation and desktop/390/320 px
layouts. Tests also cover timer corroboration, invalid timing, measured zeros,
interior gaps, leap day, month end and timezone boundaries. No production
rebuild, source modification or Strava fetch was performed.

Return to HARD — Analyst Gate 1; Owner running-Dev review follows. No merge or
deployment is authorized.
