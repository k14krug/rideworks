# P4-02 — Interval-power source diagnosis and correction plan

**Ready for HARD — Analyst diagnostic review.** Owner Gate 2 was not accepted.
This diagnostic follows the Analyst's revised [JIT §12](../../docs/tasks/P4-02.md)
at `2942449` and [blocking PR review](https://github.com/k14krug/rideworks/pull/24#pullrequestreview-5479941723).
No production calculation, selection policy, source, UI or cache was changed.
The prior HR-summary Gate 1 clearance does not clear this blocker.

## Finding: distinguish the reported regression from the broader defect

The mandatory short-interval example **passes Performance-v2 best-20
eligibility**. Training State does calculate and retain a power candidate.
That candidate is **observed partial power**, not complete recorded or corrected
power. The approved precedence selects the independently eligible HR summary
before partial power. Removing the best-20 gate alone would therefore leave
this example's current selection unchanged.

The retained API observation contains trustworthy device-watts evidence, but
timestamp omissions and a short observed tail prevent an adequately covering
power result under the current rules. Moving flags do not establish explicit
timer pauses or authorize gap reconstruction. There is no retained original
FIT/TCX/GPX for this example; an API external identifier resembling a FIT filename
is not an imported original. This is incomplete adequately covering power with
usable partial watts, rather than power suppressed by best-20 or an absence of
all usable watts. The private report records the exact source identities,
timestamps/gaps, summaries, candidate score and original-file absence.

The current API `materially_partial_scope` flag compares recording span with
reported moving duration. A false flag does **not** prove adequate stress
coverage: gaps can still make the candidate `partial`. Selection uses that
status. Do not promote partial evidence based on this flag or a workout title.

Separately, the architectural coupling **does suppress valid stress candidates
elsewhere**. Independently evaluating the already accepted recorded-power rules
on best-20-ineligible Virtual Rides finds:

| Diagnostic cohort | Distinct rides |
|---|---:|
| All Virtual Rides | 1,270 |
| Best-20 ineligible | 242 |
| Best-20 ineligible with dated stress candidate | 117 |
| Calculated recorded-power candidate | 53 |
| FIT corrected-estimate candidate | 19 |
| Observed partial-power candidate | 45 |

All 117 candidates are FIT-backed. Performance rejects 84 for a recording shorter
than its required window, 30 for no complete timestamp-contiguous window, and
three for no complete power window. Their current selections are 69 HR estimates
and 48 unavailable. Three occur in the trailing 90 days and 15 in 365 days.
These are diagnostic candidates, **not installed new scores or whole-session
claims**. Missing FTP, invalid/unsupported timing, outdoor watts and unconfirmed
API device watts remain excluded.

## Independent workout selection and actual behavior

Nine distinct private Activities were inspected: four predeclared known
interval/threshold workouts, one predeclared ordinary workout, the mandatory
outdoor HR regression, and three retained ordinary/low comparisons. Dates and
source workout descriptions select the new examples **before examining selected
stress**; recording quality, not titles, establishes source eligibility. Private
Activity IDs disambiguate duplicate date/title cases.

The independent workouts include qualified FIT power selections and two API
workouts selecting HR before a retained partial-power candidate. The latter
illustrate the precedence limitation independently of selected-stress ranking.
The existing high/ordinary/low-by-stress test remains descriptive coverage; it
is not sufficient to detect misclassified demanding sessions.

For every case, the private evidence records source-specific power candidates,
Performance `evaluate()` output, date-effective approved FTP, selected stress,
actual previous calendar-day contribution, prior/day Fitness and Fatigue,
start-of-day and following-day Form, isolated selected contribution and five
surrounding calendar dates. Candidate NP/stress is checked independently with
direct 30-second rolling sums. The low comparison falls on a multi-ride day;
the other ride's load is not attributed to that low-stress Activity.

The mandatory workout's small **net** daily change is distinct from its larger
isolated contribution relative to no workout: prior state decays before today's
load is added. The private report includes both, plus a clearly labeled
same-prior-state sensitivity using the already calculated partial power.
That sensitivity changes neither the selected source nor production curves.

Both the 3-month and 12-month running charts show coherent exponential decay,
larger recorded-session pulses, prior-day Form and consistent source/date
inspection. The two independently identified API cases still have weaker
responses from the selected HR summaries. This is an unresolved usefulness
limitation, not proof of a recurrence defect or visual acceptance.
The complete private daily comparison supports examination of both ranges.

Elevate remains reference-only. Its FTP/HR settings and source-duration/pause
methods differ or are not established. Compare stress source, response and curve
direction; do not import scores, infer a multiplier, select whichever score is
larger, or fit RideWorks to vendor levels. The authorized CSV is unchanged:
496,966 bytes, SHA-256
`407cc7ac2105d5d0c5c8ce4c90775adcb7733957157c2dad6aaa0af05f1ebfb1`.
Its 14 projections are excluded. Approved historical FTP remains authoritative.

## Narrow correction plan for Analyst disposition

1. **Decouple stress candidate eligibility from best-20 eligibility.** Add a
   Training State evaluator for trusted virtual power using the existing native
   extraction integrity and API current-summary/stream pairing, confirmed device
   watts, full-resolution pairing and valid timing/value checks. Pass those
   sources to the existing stress calculation without requiring a 1,200-second
   Performance window. Preserve native/API precedence and reject competing
   usable sources rather than choosing opportunistically. Preserve FIT-only
   15-second/1% correction, timer boundaries/NP resets, observed-only API,
   >=600-second partial segments, dated FTP and honest recorded scope.
   Keep Performance-v2 entirely unchanged. Bump the Training State power-source
   policy/version and signatures when implementing this approved change.
2. **Resolve the mandatory case separately.** Decoupling cannot change its
   existing partial-power-versus-HR selection. The current approved policy
   explicitly prefers usable HR. Analyst/Owner must either retain that rule and
   its known limitation, authorize inspection/import of an available original
   recording, or specify a revised evidence-based partial-power precedence and
   adequacy rule. No coverage threshold, API pause inference, reconstruction,
   workout-title exception or new estimate is proposed as already approved.
   The retained partial is not a complete power result or a vendor replacement.
3. **After authorization only:** implement the bounded evaluator and any
   explicitly revised selection specification, add source/ambiguity/pause/short
   recording regressions, and repeat the independent workout cases, outdoor HR
   regression, ordinary/low cases, 3-/12-month inspection, version/cache
   determinism and original/FTP/reference/Performance preservation. Return to
   Gate 1 before repeating Owner Gate 2.

**Requested review:** assess the private diagnosis and authorize/revise this
bounded plan, distinguishing the best-20 defect from the separate partial-power
precedence decision. No material implementation has begun.

## Verification and reproducibility

- **353 full Python tests**, including five new synthetic diagnostic tests:
  short native/API recordings with stress but no best-20, a best-20-eligible
  API recording retaining partial power while HR wins, excluded outdoor or
  unconfirmed-device power, and duplicate/gap accounting. Read-only diagnostic
  source evaluation leaves database tables and cache unchanged.
- **141 independent power-interval formula checks** and nine prior/day/next-day
  behavioral cases; repeated detailed and aggregate diagnosis identical.
- **218 Chromium assertions** across nine Activities / 16 range inspections:
  3 months and 12 months, actual source alternatives, numeric values, chart and
  strip hover, persistent selection and summary uncertainty. Private screenshots
  of both mandatory-case views were inspected. No UI changes were made.
- Existing HR behavioral verification rerun: all prior aggregate results
  identical, including the outdoor regression and 57 raw-source summary checks.
- **20 original tables / 1,422 artifacts** preserved against the accepted
  baseline; integrity `ok`, zero foreign-key errors. An additional all-table
  digest includes the derived cache and confirms no diagnostic writes.
  Approved FTP, production code, Performance-v2 and original Elevate reference
  remain unchanged. Existing route/phone checks remain the previously verified
  baseline; this diagnostic does not claim to rerun all 286 prior browser checks.

Safe machine-readable results: [interval-power-diagnosis.json](interval-power-diagnosis.json).
The detailed report, cases, timestamps, source IDs, sensitivity, comparison
curves and browser script/screenshots remain in ignored local directories.

```bash
.venv/bin/python tools/diagnose_training_state_power.py \
  --data-dir local_data/p4-02-baseline/store \
  --baseline-dir local_data/p2-05-review \
  --cases local_data/p4-02-interval-diagnosis/cases-private.json \
  --reference data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv \
  --as-of 2026-10-10T00:30:00+00:00 \
  --aggregate-output local_data/p4-02-interval-diagnosis/diagnosis.json \
  --private-output local_data/p4-02-interval-diagnosis/diagnosis-private.json
.venv/bin/python -m unittest discover -s tests -p test_training_state_power_diagnosis.py -q
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python tools/verify_training_state_behavior.py \
  --data-dir local_data/p4-02-baseline/store \
  --before local_data/p4-02-hr-summary/before-private.json \
  --cases local_data/p4-02-hr-summary/cases-private.json \
  --reference data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv \
  --as-of 2026-10-10T00:30:00+00:00 \
  --aggregate-output local_data/p4-02-interval-diagnosis/retained-hr-behavior.json \
  --private-output local_data/p4-02-interval-diagnosis/retained-hr-behavior-private.json
npx --yes --package @playwright/cli playwright-cli -s=p402 run-code \
  "$(cat local_data/p4-02-interval-diagnosis/browser-private.js)"
git diff --check
```

The cases file is a private JSON array with `day`, optional `title`, optional
`activity_id` for disambiguation, and `role`. It must uniquely match every
predeclared example. The diagnostic requires the existing schema-8 review copy,
enforces SQLite query-only mode, and never migrates the accepted production store
or fetches missing sources. Repeated outputs used the same frozen endpoint.
