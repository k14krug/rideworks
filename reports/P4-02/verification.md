# P4-02 — Analyst review package

**State:** ready_for_review at **Gate 1 — HARD — Analyst**. `/TASK P4-02`
was explicitly invoked on 2026-10-09. This is implementation/verification evidence,
not Analyst acceptance, Owner production/visual acceptance or Phase 4 completion.
**Branch / PR:** `task/p4-02-training-state` / [draft PR #24](https://github.com/k14krug/rideworks/pull/24).

## Delivered behavior

Training State adds the approved interactive Fitness/Fatigue/start-of-day Form
page, four history ranges, independent line toggles, aligned daily stress,
selected-day ride links/source inspection, synchronized seven-day changes and
separate 7-/42-day stress and observed-work context. Home retains its accepted
cards and adds a subordinate snapshot/link. No new frontend framework, runtime
dependency, service, API crawl, planning, readiness zones or projections.

`rideworks/training_state.py` implements `training-state-v1`,
`recorded-power-stress-v1`, `threshold-normalized-average-hr-v1` and
`daily-exponential-42-7-prior-form-v1`. Schema 8 adds one replaceable cache table;
source/extraction, current API stream, FTP content and parameter signatures drive
recalculation. The approved 66-entry FTP CSV is byte-identically packaged for
installed applications; the original source is unchanged. Unknown FTP prehistory
and uncertain date boundaries withhold power stress. Historical FTP/settings dates
use the accepted America/Los_Angeles athlete calendar independently of browser display timezone.

Power uses unchanged Performance-v2 source eligibility. Calculated recorded
intervals take precedence, followed by FIT-only interior-gap estimates (<=15 s
each and <=1% total), covering HR estimates, partial >=600 s observed power and
unavailable. FIT correction uses the arriving sample backward. Timer intervals
exclude known pauses and reset NP; boundaries/timer summaries must exactly agree
before an observed calculation receives a verified-session label. Missing/invalid
or duplicate sample rows are never silently repaired. Major source-duration losses
keep a nominally continuous recording partial. API power is observed-only.

HR stream screening requires **>=99% recorded active-time coverage**, adjacent
measured endpoints **<=15 s**, and recorded active duration aligned with the
same-source timer/active-duration evidence within **max(1 s, 1%)**. A trapezoidal
time-weighted native-endpoint mean estimates mean HR without generating samples.
Paired timers are clipped to recorded bounds and exclude pauses; mismatched outer
timer envelopes do not extend the recording or establish a complete session.
Absent streams may use measured same-source summary HR and compatible active
duration. Defective streams cannot be bypassed by their summary. CSV duration with
unknown units is never guessed. Multiple usable native HR sources are unavailable
rather than silently ranked. The approved 58/158/143 HR values remain explicit
retrospective assumptions; accepted dated contexts can replace them. Coefficient
1.92 is a fixed model constant, never a sex/gender inference.

Each ride selects one stress method. Missing stress remains null/unavailable,
with zero applied only to its numeric curve contribution. Recorded work contains
observed eligible-power bins only, including real zeros; no HR/FIT correction
creates kJ. Interior missing time, verified boundary missing time and discarded
short segments remain distinct. Unverified outer timer spans are not claimed known
missing active effort. No-record days are not confirmed rest. Zero initialization
starts before the first usable stress date; first 126 model days are flagged
provisional (three 42-day time constants, an informational initialization label).

## Aggregate evidence and limitations

The preserved store contains **1,418 cycling rides**. **1,079 scored**:
589 calculated power intervals, 131 corrected FIT interval estimates,
218 selected HR estimates and 141 selected partial power contributions.
**339 remain unscored**; 118 precede the first usable model date. This means
missing stress is rare in some recent windows, but **not rare across the complete
archive**. Do not read historical model coverage as complete training history.
There are 3,053 exact modeled calendar days and 985 scored dates.
By cohort, 1,072/1,270 Virtual Rides score, but only **7/148 outdoor Rides**
qualify for the HR fallback. **141 outdoor rides remain unscored.** This is a
material source/duration limitation, surfaced under the JIT stop-and-report rule;
no coverage rule or historical duration has been invented to hide it. Analyst
review must specifically assess outdoor HR/duration eligibility and whether a
revised brief/source interpretation is required before proceeding. The 131 FIT
estimate class agrees with the accepted P4-01 source-specific screen; production
timer clipping and omission accounting differ from historical envelope comparators.

[Aggregate evidence](coverage-and-verification.json) gives all-history selection
counts separately from the 1,300 rides inside the modeled date span. Major HR
omissions are insufficient coverage, incompatible duration, unknown active
duration and unsupported timing. Short Virtual Rides remain subject to unchanged
power eligibility; usable HR may score them. Outdoor estimated power is excluded.
The screen does not loosen itself to increase coverage. The Analyst must assess
whether the documented conservative policy is suitable before Owner acceptance.

The initial uncached private-store run took about 17 seconds. Cached routes were
responsive in browser checks. The initial computation serializes a store snapshot;
no background analytics platform was introduced. No live Strava request was made.
Normal sync/invalidation was covered through the existing full sync suite and
synthetic current-summary/stream updates, idempotent reruns and setting changes.
The current accepted live store was not migrated or restarted for this review;
the new app ran on a verified private copy to preserve the existing running app.

## Required verification performed

- **334 full Python tests / 23 focused P4-02 tests pass.** Independent synthetic
  values cover zero seed/days, consecutive and multiple rides, exponential decay,
  lagged Form, leap dates, exact FTP boundaries, HR normalization/bad parameters,
  pause/reset behavior, FIT 15 s / 1% bounds, API no correction, nonconstant NP,
  source precedence, cache updates and schema migration/failure rollback.
- Independent verification checked **3,053 daily models** by closed-form
  convolution, daily/rolling totals and prior-day Form, **1,022 observed-power
  calculations** by direct 30-s sums and observed-bin work, and **803 HR formulas**
  from retained mean/duration/settings. The HR formula check is arithmetic;
  stream coverage/mean eligibility is also tested synthetically, not a claim of
  independent physiological validation of all real HR recordings.
- **20 preexisting tables / 1,422 original artifacts preserved** across schema 8,
  restart and repeated recomputation; integrity `ok`, no FK violations. Performance
  result rows and original/source/extraction evidence are unchanged.
- Before/after Home diagnostic content, Performance points/eligibility/summaries
  and Activities rows match. Current-clock view endpoints/age displays naturally
  advance and were excluded from this content comparison.
- **86 Chromium assertions pass**: all four ranges, all three toggles, exact date
  selection, metrics/details synchronization, multi-ride links, unavailable and
  no-record days, keyboard/Home/End, source disclosure, stable Activity Review,
  retained Home/Performance/Activities routes and 390 px phone without horizontal
  overflow. Desktop and phone screenshots remain ignored/local-only. No browser
  console errors or warnings. Mouse selection, date-input/keyboard selection and Chromium mobile-touch
  emulation passed; no physical touch device was available. Phone tick density was reduced for readable date labels.
- An isolated wheel build passes; its approved FTP resource loads outside the
  repository and includes the UI asset. Elevate is not packaged as production data.
  A preliminary no-build-isolation attempt failed because this local environment
  lacked wheel build tooling; the declared isolated build succeeds without adding
  a RideWorks runtime dependency.

## Elevate external sanity comparison

The Owner explicitly authorized committing only the exact reference CSV, verified
as **496,966 bytes** with SHA-256
`407cc7ac2105d5d0c5c8ce4c90775adcb7733957157c2dad6aaa0af05f1ebfb1`.
Its README, AGENTS.md and P4-02 design/JIT privacy text record the exception;
invocation, acceptance criteria and Analyst/Owner gates are unchanged.

**5,911 completed reference rows** were compared; the final **14 projected rows**
were excluded. Exported CTL/ATL and prior-day TSB reproduce from rounded selected
stress within approximately 0.010 / 0.010 / 0.012 points. This verifies vendor
arithmetic, not its source quality. Over 3,053 overlapping days, mean absolute
RideWorks-versus-Elevate differences are about **6.42 Fitness, 6.60 Fatigue and
3.21 Form points**. [Safe aggregate comparison](elevate-sanity.json).

Latest, multi-ride and unscored representative date comparisons are retained
**local-only**. The largest daily disagreement is about 476 stress points on an
unscored ride; other major differences also reflect unscored evidence, unknown
prehistory FTP, incomplete/unsupported HR and historical source/setting choices.
No multiplier, reclassification, score import or vendor seed was used to force
agreement. Elevate's FTP/settings/zones are not authoritative. RideWorks continues
using its approved dated FTP. Analyst review should assess historical coverage and
these intentional policy disagreements before Owner usefulness review.

## Reproduction commands used

Private store snapshot and before-change pages were captured before implementation.
The copy excludes OAuth credential/settings files. The following are the final
verification commands; paths point to local-only runtime artifacts.

```bash
.venv/bin/python -m unittest discover -s tests -p test_rideworks_training_state.py -v
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python tools/verify_training_state_production.py \
  --data-dir local_data/p4-02-baseline/store \
  --baseline-dir local_data/p2-05-review \
  --as-of 2026-10-10T00:30:00+00:00 \
  --output local_data/p4-02-baseline/verification-final.json
.venv/bin/python tools/compare_training_state_elevate.py \
  --data-dir local_data/p4-02-baseline/store \
  --reference data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv \
  --as-of 2026-10-10T00:30:00+00:00 \
  --private-output local_data/p4-02-baseline/elevate-comparison-private.json \
  --aggregate-output local_data/p4-02-baseline/elevate-comparison.json
.venv/bin/python -m rideworks --data-dir local_data/p4-02-baseline/store serve --port 8772
.venv/bin/python -m pip wheel . --no-deps -w local_data/p4-02-baseline/wheels
node --check rideworks/static/training_state.js
git diff --check
```

Browser review used the Playwright skill wrapper to open the Chromium session.
The installed CLI rejected the wrapper's injected config for interaction commands,
so subsequent commands used the same session through direct `npx`:

```bash
npx --yes --package @playwright/cli playwright-cli -s=p402 open http://127.0.0.1:8772/training-state
.venv/bin/python - <<'PY'
from pathlib import Path
import subprocess
subprocess.run(['npx', '--yes', '--package', '@playwright/cli', 'playwright-cli',
    '-s=p402', 'run-code', Path('tools/verify_training_state_browser.js').read_text()], check=True)
PY
```

**Next:** Analyst code/data/test/browser review at Gate 1. After explicit Analyst
authorization, proceed to the Owner production/visual/usefulness Gate 2. No merge,
substantive acceptance, Phase 4 completion or later task is authorized here.
