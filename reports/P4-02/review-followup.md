# P4-02 — Analyst review follow-up, 2026-10-10

Gate 1 remains **HARD — Analyst, not cleared**. This responds to PR #24 reviews
5477830562 and 5479107493 under `/TASK P4-02`. Floating inspection and FTP loading
are fixed. Outdoor HR alternatives are read-only diagnostics; production stress,
HR source selection, assumptions and Performance-v2 eligibility remain unchanged.
The initial [verification](verification.md) remains the historical implementation
record. New evidence is [outdoor diagnostics](outdoor-diagnostics.json) and
[follow-up verification](review-followup-verification.json).

## Outdoor evidence and rejected scope

The diagnostic freezes the comparison at rider-local **2026-10-09**, matching the
completed portion of the approved Elevate export. It covers all 148 outdoor rides,
including rides before usable model history. Counts are distinct rides, not sums
of source candidates. Source-signature cohorts and ride-level rejection categories
are disjoint; source-type cohorts and experimental recoveries overlap.

| Cohort | Rides | Any HR evidence | Scored | Ordered unique time evidence | Source duration present |
|---|---:|---:|---:|---:|---:|
| All outdoor | 148 | 85 | 7 | 58 | 13 |
| 2018 | 53 | 48 | 0 | 5 | 0 |
| 2026 | 11 | 10 | 7 | 9 | 11 |
| Trailing 42 days | 6 | 6 | 3 | 6 | 6 |
| Trailing 90 days | 11 | 10 | 7 | 9 | 11 |

Evidence-presence columns mean at least one retained source has that feature;
they do not establish a usable, same-source HR/active-duration pair. CSV HR
presence is included, but CSV duration units are not guessed. API timing is
relative stream timing; native timing is absolute. No outdoor source has
independently corroborated timer/session boundaries.

Disjoint outcomes across all outdoor rides:

- 63 have no HR evidence;
- 52 have an HR timing rejection;
- 1 has both HR timing and unusable summary/duration rejection;
- 22 lack a supported HR active duration;
- 2 have incompatible stream span and active duration;
- 1 has insufficient HR coverage;
- 7 are scored.

All 52 HR-stream timing rejections have duplicate timestamps, rather than missing
absolute timestamps or backward ordering. Other non-HR sources also contain
duplicates, so the 80 rides with duplicate evidence are not 80 HR rejections.
In 2018, 45 rides have timing rejection, one has the combined timing/summary
rejection, two lack supported duration, and five lack HR. The P4-01 **48/53 HR-any**
census is reconciled: **47** have streams; the additional ride has summary
HR evidence without a supported active-duration pair. Multi-lap summary presence
is retained even when it cannot produce a supported summary calculation.

The JSON provides per-year, source-type, source-signature, year/source and recent
cohorts. Detailed source IDs, titles, timestamps, timers and per-ride reasons are
only in `local_data/p4-02-baseline/outdoor-diagnostics-private.json`.

## Bounded alternatives — estimates, not adopted rules

Every alternative keeps the approved HR recipe and assumptions, uses local
retained evidence only, and preserves existing scored rides. No API historical
crawl, inferred CSV units, elapsed-as-moving substitution or vendor score input
occurs. More than one qualifying source is reported as ambiguous, not silently
chosen. Alternative recovery counts must not be added.

| Alternative | Newly recoverable rides | 2018 | 2026 / recent 90 | Recent 42 |
|---|---:|---:|---:|---:|
| Same-source measured summary + supported duration, despite defective stream | 3 | 0 | 3 | 3 |
| Explicitly partial recorded HR intervals | 34 | 10 | 2 | 2 |
| Stream coverage 99%, 98%, 95%, or 90%, retaining 15-second cap | 0 | 0 | 0 | 0 |
| Symmetric 1% overcoverage diagnostic | 0 | 0 | 0 | 0 |

The three summary alternatives use 13,286 seconds of same-source reported
active duration. They do **not** establish observed full coverage, independently
verified mean-HR active scope, or pause treatment. Recording omissions are
unknown, not measured zero. Existing API summary-only eligibility is not changed.

The partial alternative excludes every record at duplicate timestamps, splits
at ambiguous bins, missing HR, long gaps, XML segment boundaries and known timer
pauses, and retains only segments of at least 600 seconds with measured adjacent
endpoints no more than 15 seconds apart. It never selects a duplicate value,
sorts backward timestamps, fills HR samples or asserts elapsed time was moving.
Across 34 recoveries it represents **59,215.30 seconds**, omits **397,214.70 recording
seconds**, and has unverified active/timer scope for all 34. The 10 recoveries in
2018 represent 12,342 seconds and omit 10,182 recording seconds. Recent recoveries
represent 7,955.30 seconds and omit 5,447.70 recording seconds. Such subtotals
cannot be labeled complete ride stress. One-second terminal bins follow the
explicit native-bin convention; they do not extend to distant stop boundaries.

At the frozen comparison date, newly recovered summary estimates alone would
add **3.67 Fitness / 4.25 Fatigue**, changing start-of-day Form by **−1.14**.
The separate partial alternative would add **2.16 / 3.76**, with Form **−2.12**.
These are linear diagnostic effects, not physiological validation or combined
changes. Historical omissions also depress past curves; very old omissions decay
and cannot explain all current disagreement. Recent missing outdoor load remains
a material usefulness limitation.

## Duration/coverage asymmetry

Production accepts source-duration versus recorded-span alignment within
`max(1 second, 1%)`, then rejects `covered / target > 1.000001`. Thus a slight
positive overhang can pass alignment but fail coverage. Lowering only the lower
coverage threshold cannot rescue it. A synthetic 601-second stream paired with
600 seconds demonstrates this asymmetry; the isolated 101% diagnostic accepts
it while production still rejects it. No additional outdoor ride is recovered
by changing that ceiling in this dataset. This establishes the boundary behavior,
not which overhanging samples were active or permission to change HR policy.

## Owner-requested ride and chart diagnosis — private detail

The exact requested Activity was matched against its retained sources and the
approved reference export. The chart, hover guide, strip and persistent panel
inspect that Activity's correct rider-local date and source class. Its zero
numeric contribution is an HR eligibility rejection, not a date/plot mismatch.
Its sparse stream fails even the 90% diagnostic. Summary and partial estimates,
source mean/duration, gap/timer evidence, isolated model deltas, unchanged-day
Form and next-day Form effects are documented privately in
`local_data/p4-02-baseline/requested-ride-diagnosis-private.md` and `.json`.
The vendor value was compared without fitting, importing or seeding it.
Screenshots and the browser check remain under ignored local paths.

## Implementation fixes and verification

- The chart now has a compact floating near-cursor tooltip and vertical hover
  guide in both the line area and stress strip. It shows exact day, full ride
  titles/count, selected stress, Fitness/Fatigue/start-of-day Form, source formats
  and classes, and explicit unavailable stress. Hover leaves persistent selection
  alone; mouseleave hides the overlay/guide. Click/tap, date input and keyboard
  remain synchronized. Overlay width remains stable while it flips/clamps at
  viewport edges, including phone resize and date changes.
- FTP loading validates dates, positive integer watts and contiguous increasing
  intervals without a hard-coded row count. The unchanged initial approved
  artifact still has an independent 66-row test. Deliberately supplying an updated
  dated record changes the content signature and recalculates the cache; valid
  67-row loading, malformed intervals, empty history, recalculation and reuse are
  tested. The packaged default and canonical approved source remain identical.
  No settings UI or automatic source discovery was added.
- **341 full Python tests; 25 focused Training State tests and 5 diagnostic tests**
  pass. **255 Chromium assertions** pass, including actual hovering, both chart
  regions, all four ranges, exact source/value inspection, edges, longest retained
  title, multiple/missing/no-record days, mouseleave and click persistence, phone
  overlay changes, keyboard/date equivalence and touch emulation. Home,
  Performance, Activities and stable Activity Review remain usable.
- Independent verification again checks **3,053 daily models, 1,022 observed-power
  calculations and 803 HR formulas**. All **20 preexisting tables / 1,422 originals**
  remain intact. All 148 outdoor recomputations equal baseline cached results;
  the diagnostic leaves database bytes unchanged. Overall production coverage
  remains **1,079/1,418 scored**, **339 unavailable**.
- Private desktop/phone hover screenshots were inspected. The original approved
  Elevate CSV again passes its 496,966-byte/SHA-256 integrity check; its final 14
  projections are excluded. Elevate FTP is never authoritative. No private ride
  report, DB, source file or screenshot is committed.

## Reproduction and required next review

```bash
.venv/bin/python tools/diagnose_outdoor_training_state.py \
  --data-dir local_data/p4-02-baseline/store --as-of 2026-10-09 \
  --aggregate-output local_data/p4-02-baseline/outdoor-diagnostics.json \
  --private-output local_data/p4-02-baseline/outdoor-diagnostics-private.json
.venv/bin/python -m unittest discover -s tests -p test_rideworks_training_state.py -q
.venv/bin/python -m unittest discover -s tests -p test_outdoor_training_state_diagnostics.py -q
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python tools/verify_training_state_production.py \
  --data-dir local_data/p4-02-baseline/store --baseline-dir local_data/p2-05-review \
  --as-of 2026-10-10T00:30:00+00:00 \
  --output local_data/p4-02-baseline/verification-followup.json
node --check rideworks/static/training_state.js
git diff --check
```

Browser verification uses the existing Chromium CLI session and
`tools/verify_training_state_browser.js`, as documented in the initial report.
Additional private requested-ride checks are saved locally; they verify the
specific Activity without adding personal fixtures to Git.

**Next: Analyst code/data/browser review and explicit JIT source-policy
clarification, followed by the Owner's decision on any material HR eligibility
change.** In particular, decide whether the measured same-source summary can be
used when a present stream fails, and which native/API duration and pause semantics
are acceptable. Consider an explicitly partial HR class and its precedence only
with defined scope, omissions and Owner approval. The three recent summary cases
are a more useful review target than relaxing a threshold that recovered none.
Do not adopt either alternative, cross Gate 1, seek final Owner production
acceptance, merge or begin a later task without the required authorization.
