# P4-02 — HR summary correction and behavioral validation

**Ready for HARD — Analyst Gate 1; not accepted or cleared.** Implemented under
the latest `/TASK P4-02` and the revised Analyst brief/design at `010eff5` on
existing draft PR #24. Earlier reports remain the historical v1 record.

## Result and source behavior

A defective detailed HR stream no longer vetoes a separately eligible same-source
reported mean HR and duration. A supported stream still wins. The fallback uses
Strava API measured HR with `has_heartrate=true` and positive moving time no
greater than elapsed time; TCX uses one lap's reported average HR and
`TotalTimeSeconds`; the existing FIT summary pairing uses reported mean HR and
timer-active seconds with duration/event compatibility checks. Recording span
and unknown CSV units never supply active duration.

Selected summaries are labeled **HR summary estimate; completeness and pause
treatment unverified**. Inspection retains duration basis, source/extraction or
API observation, mean/duration, assumed or dated HR settings, rejected-stream
reason/coverage, and unverified completeness/mean active scope/pause treatment.
Both the tooltip and persistent details expose the summary limitation; help
explains it. Suitable streams keep their existing coverage/gap screens. Competing
eligible sources at the preferred evidence level remain ambiguous rather than
being ranked by file format. No partial-HR source class is selected.

The HRSS recipe remains `threshold-normalized-average-hr-v1` with the approved
58/158/143 retrospective assumptions and fixed coefficient 1.92. Calculation
version is **training-state-v2**, source policy
**same-source-hr-summary-fallback-v2**; both enter cache signatures. The model,
approved historical FTP, measured-power rules and all power candidates remain
unchanged. HR still precedes materially partial power, and each ride contributes
one selected method. No HR-derived or gap-filled work is manufactured.

## Actual coverage and recent load response

All comparisons use the same retained cohort and frozen
`2026-10-10T00:30:00+00:00` (rider-local October 9), excluding the export's 14
projected days. These are distinct-ride counts, not source candidate totals.

| Cohort | Before scored | After scored | Total rides |
|---|---:|---:|---:|
| All cycling | 1,079 | 1,102 | 1,418 |
| Outdoor | 7 | 10 | 148 |
| Virtual | 1,072 | 1,092 | 1,270 |
| Trailing 42 days, cycling | 34 | 37 | 37 |
| Trailing 42 days, outdoor | 3 | 6 | 6 |
| Trailing 90 days, cycling | 54 | 58 | 59 |
| Trailing 90 days, outdoor | 7 | 10 | 11 |

All three previously identified recent outdoor candidates qualify: two API
summary/moving-time pairs and one TCX single-lap pair. **50 rides change selected
stress** under the same rule: 44 FIT, five API and one TCX summary estimates.
Of these, 23 become scored and 27 switch from partial power to the preferred HR
estimate. This includes eligible virtual summaries whose failed HR streams had
previously suppressed the fallback. **All 1,418 power candidate objects are
identical before/after**, including partial stress, observed work and omissions;
qualified power selections are identical. No source-policy change was made to
Performance-v2 or P4-01 power calculation.

After correction the selected classes are 589 calculated power, 131 FIT power
estimates, 268 HR estimates, 114 partial power and 316 unavailable. Of the selected
HR estimates, 57 are summaries (44 FIT / 12 API / one TCX); the others use streams.
Scored days increase from 985 to 999. There are still 138 unscored outdoor rides,
including all 53 in 2018; the original historical duration problem remains.

Trailing cycling stress changes from **1,568.13 to 1,747.97** over 42 days and
**2,801.12 to 3,000.79** over 90 days. Some preferred HR summaries replace a larger
partial-power subtotal: methods have different input evidence and need not move
in the same numerical direction. These are independently calculated source
changes, without a fitted multiplier. At the frozen endpoint the net changes are
**+2.93 Fitness, +2.11 Fatigue, +0.56 start-of-day Form**. These include all eligible
summaries and replaced partial contributions, not only the three outdoor rides.

## Behavioral validation beyond arithmetic

[Behavioral aggregate evidence](hr-summary-behavior.json) and the reproducible
`tools/verify_training_state_behavior.py` validate:

- all selected summary scores directly against their **original retained source
  fields**, separately from production `hrss()` (57 checks), and exact approved
  HR assumptions/source scope;
- the required private regression and all three recent outdoor candidates;
- high-load, ordinary and low-load sessions selected from each 42-/90-day window
  by relative stress rank (five distinct Activities across overlapping cases);
- actual daily stress, prior/day Fitness and Fatigue, start-of-day Form, next-day
  Form and the isolated contribution of each selected ride;
- exact date/Activity/source and model-value synchronization in both chart hover
  regions, persistent inspection and phone layout.

The required regression now contributes independently calculated summary HRSS
instead of numerical zero. Fitness and Fatigue rise on its date; Form retains
previous-day timing and responds the next day. It uses RideWorks source fields,
not the approximate external score mentioned in the JIT. Exact mean, duration,
score, sources, rejected coverage, before/after values and next-day Form are in
`local_data/p4-02-hr-summary/required-regression-private.md` and
`behavior-private.json`. Detailed identities and screenshots are not committed.

Fitness and Fatigue change directions agree with Elevate for all five inspected
representative dates (five comparisons for each metric). This supports the
intended recognizable load response for these examples; it does not validate
physiology, all history, or exact numerical agreement. The source-reported mean
may describe a recorded subset; a reported lap duration may include pauses.
Different settings, duration/HR semantics, historical inputs and source coverage
remain possible explanations for score differences. The export cannot establish
identical authoritative inputs.

The [updated external sanity comparison](hr-summary-elevate-sanity.json) verifies
the exact approved export and excludes projections. Over the unchanged 3,053-day
overlap, mean absolute Fitness difference changes from 6.42 to 6.19 and Fatigue
from 6.60 to 6.32. These descriptive differences are not acceptance targets or
calibration. Elevate results/settings never enter application calculations or
model seeds, and its FTP remains nonauthoritative.

## Verification and preservation

- **348 full Python tests / 32 focused Training State tests pass.** The obsolete
  stream-veto assertion was replaced according to the revised JIT, checking the
  eligible independent summary and retained failed-stream evidence. New cases
  cover API invalid fields, stream preference, TCX missing/multilap fields,
  source conflicts, FIT duration/known-pause compatibility and uncertain pauses,
  qualified power/partial precedence, and version invalidation/cache reuse.
- **286 general Chromium assertions and 76 private representative-Activity
  assertions pass.** Existing hover, persistence, ranges/toggles, multi-ride,
  missing/no-record, keyboard, phone edges and touch behavior are retained.
  Summary source/uncertainty labels and all five real cases were checked in the
  line area and stress strip. Local desktop/phone screenshots were inspected.
- Independent verification passes for **3,053 daily models, 1,022 observed-power
  calculations and 874 HR formulas**; repeated results and reopened stores agree.
- All **20 preexisting tables / 1,422 originals** are preserved; integrity is `ok`
  with no foreign-key violations. Only the existing replaceable stress cache is
  recalculated. No migration or original/source alteration was added.
- Home's existing content and Performance render identically with the comparison
  clock held fixed; Activities renders identically. Home's subordinate Training
  State snapshot reflects the corrected model. Stable Activity Review routes
  work. The review server alone was restarted on the same verified private copy;
  existing production store/server are retained.
- The unchanged approved Elevate CSV again matches 496,966 bytes and its expected
  SHA-256. The approved canonical and packaged FTP files remain unchanged. No
  private source, case configuration, report, database or screenshot is committed.

Machine-readable checks: [verification/preservation](hr-summary-verification.json).

## Reproduction

The private pre-correction baseline was captured with v1 at `010eff5` before code
changes, using `training_state()` and `ride_results()` at the frozen timestamp.
`before-private.json` contains those results. The private case file names the
required regression and the three previously diagnosed outdoor Activity IDs;
it is a verification input, never production training data.

```bash
.venv/bin/python -m unittest discover -s tests -p test_rideworks_training_state.py -q
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python tools/verify_training_state_behavior.py \
  --data-dir local_data/p4-02-baseline/store \
  --before local_data/p4-02-hr-summary/before-private.json \
  --cases local_data/p4-02-hr-summary/cases-private.json \
  --reference data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv \
  --as-of 2026-10-10T00:30:00+00:00 \
  --aggregate-output local_data/p4-02-hr-summary/behavior.json \
  --private-output local_data/p4-02-hr-summary/behavior-private.json
.venv/bin/python tools/verify_training_state_production.py \
  --data-dir local_data/p4-02-baseline/store --baseline-dir local_data/p2-05-review \
  --as-of 2026-10-10T00:30:00+00:00 \
  --output local_data/p4-02-hr-summary/preservation-and-math.json
.venv/bin/python tools/compare_training_state_elevate.py \
  --data-dir local_data/p4-02-baseline/store \
  --reference data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv \
  --as-of 2026-10-10T00:30:00+00:00 \
  --aggregate-output local_data/p4-02-hr-summary/elevate.json \
  --private-output local_data/p4-02-hr-summary/elevate-private.json
node --check rideworks/static/training_state.js
git diff --check
```

Browser reproduction uses `tools/verify_training_state_browser.js` through the
existing Playwright Chromium CLI session, as in the initial verification report.
The additional private representative checks and route comparisons are retained
locally with frozen before/after clocks.

**Next: Analyst review of the revised code, source selection and behavioral
results at HARD Gate 1.** Task stays `in_progress`, STATUS is `ready_for_review`,
PR #24 stays draft. No merge, Owner Gate 2 acceptance or later task/phase follows
automatically.
