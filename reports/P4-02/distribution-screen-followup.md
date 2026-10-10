# P4-02 — Taller plot and session-estimate distribution screen

**Stopped at HARD — Analyst Gate 1 / §13 method review.** This follow-up implements
the authorized visual refinement and proposes a diagnostic-only distribution
screen requested in [Analyst feedback](https://github.com/k14krug/rideworks/pull/24#issuecomment-6101574511),
after refreshing the branch through `50df1a3`. It supersedes the plot dimensions
and representativeness proposal in [the previous report](power-source-followup.md).
Production session-PSS selection is still held; PR #24 remains draft and Owner
Gate 2 is unaccepted.

## Delivered visual behavior

The actual Fitness/Fatigue/Form plot is **600 CSS pixels on desktop and 400 on
narrow screens**, inside 770-/570-pixel SVGs. The remaining 170 pixels retain the
top inset, separate 50-pixel stress bars, labels and date axis. JS derives all
geometry from the actual container dimensions; SVG units map one-to-one to CSS
pixels even at 320-pixel phone width. Normal vertical page scrolling is retained.
Axes, zero reference, guides, bars, hover, keyboard and touch share the same date
coordinate transformation. No calculation values change with chart dimensions.

Keyboard inspection now remains anchored when focusing or scrolling the taller
chart. Pointer inspection still dismisses on scroll. This corrects an interaction
found by browser verification rather than hiding it with test timing.

Chromium checks cover all ranges and three line toggles; actual geometry,
3-/12-month desktop and 320-/390-pixel layouts; exact trend/strip hover and touch
dates; keyboard selection/readout; viewport-bounded tooltip; persistent source
inspection; multi-ride, unscored and no-record dates. Private screenshots of both
required ranges and phones were visually inspected. The source-neutral public
artifacts contain no screenshot or private activity identity.

## Exact diagnostic proposal for Analyst approval

Retain the pinned Elevate time-buffer math, supported same-source duration,
historical FTP and deterministic source protections from the previous report.
The added proposed policy is **diagnostic-distributed-observations-v1**; the
diagnostic method is now **diagnostic-elevate-time-buffer-session-pss-v2**.
Neither is installed in production or in its cache signatures.

1. Define the screening timeline from **closed, consistent timer intervals**
   where supported. Exclude known stops and concatenate those intervals into
   an active-time clock solely for distribution screening. The NP calculation
   still resets its separate buffers at real timer boundaries.
2. Otherwise require a **same-source elapsed timeline with a supported origin**:
   API offset zero through reported `elapsed_time`, or FIT `start_time` through
   reported `total_elapsed_time`. Do not replace this with moving time or the
   first/last available watt samples. Include unrecorded beginnings and endings.
3. Count the union of actual non-null watt bins `[timestamp, timestamp+1)`,
   clipped to that timeline. An endpoint sample at the reported end does not
   extend coverage beyond the elapsed boundary. Overlapping bins cannot increase
   coverage. No forward-hold across gaps, interpolation or missing-watt zero fill.
4. Require **at least 80% total observed timeline** and **at least 50% observed
   time in every sliding 300-second window**. For a timeline shorter than 300
   seconds, use its entire length. Evaluate every possible minimum exactly at
   interval/window boundary events; fixed aligned blocks could hide a hole that
   straddles their boundary. Retain the already proposed >=600-second contiguous
   observation floor and all existing source/FTP/duration/timer rejection rules.
5. Reject independently **known omitted effort** even if the timing screen
   passes. A workout title alone cannot establish that fact. Unknown gap
   intensity remains an uncertainty, not a silently inferred recovery or pause.

The 80% proposal limits the supported-duration/observed-time ratio to roughly
1.25; it does not bound intensity-dependent stress error; the local requirement prevents even a relatively
dense recording from leaving most of an entire five-minute neighborhood absent.
Five minutes provides a multi-minute distribution test, and the half-window
allowance permits imperfect streams without reintroducing complete-stream
99%/15-second rules. **These are transparent policy choices for review, not
validated physiological cutoffs or guarantees of small score error.** They were
not fitted to the external export score. Sensitivity is reported rather than
concealing that a stricter choice can reject the mandatory case.

### Moving, elapsed and watt-time semantics

Same-source moving/timer duration supplies the proposed session-PSS formula;
elapsed/verified-active time supplies the omission screen. They serve different
purposes. API watt samples may include nonmoving points, and the sample count can
exceed reported moving duration. This does not establish full active coverage.
API moving flags do not establish timer stops or explain a gap; without timer
proof the screen deliberately includes the full elapsed timeline. This can reject
a source with a long genuinely inactive but undocumented gap. That targeted
exception is disclosed instead of treating a pause hypothesis as evidence.

The pinned reference still uses available-sample arithmetic means and its actual
nonoverlapping time-buffer emission convention. Screening does not change the
weighted-power formula, synthesize samples, reconstruct intensity or infer work.
Estimated session stress must remain labeled **estimated session power;
representativeness and pause semantics unverified**, preserving P4-01's distinct
measured/corrected/observed-partial candidates and observed work separately.
Production class, source order and cache version still require Analyst approval.

## Private-case results and sensitivity

The existing **13 independently predeclared cases** are retained; none was chosen
by ranking current RideWorks stress. Seven reach distribution evaluation, six
pass the proposed screen. The previously proposed paused-source estimate is now
excluded for concentrated omissions. Three other cases retain timer/duration
conflicts, one unsupported duration, and two lack an unambiguous trusted power
source. This is not an archive-wide estimator qualification claim.

The mandatory interval case passes the proposed rule using its elapsed timeline,
available measured watts, source moving duration and approved dated FTP. Its
numeric diagnostic candidate is unchanged; its **production HR selection is
also unchanged**. The private report records exact samples, terminal clipping,
worst sliding window, gaps, source references, FTP, selected/alternative scores,
same-day Fitness/Fatigue and next-day Form. The mandatory outdoor HR regression
and all other production scores are unchanged.

| Alternative screen (other proposed settings retained) | Private cases passing / 7 evaluated |
|---|---:|
| Proposed: total 80%, local 50%, 300 seconds | 6 |
| Total 70%, 90% or 95% | 6 |
| Total 99% | 5 |
| Local 40% | 6 |
| Local 60% or 75% | 5 |
| Window 180 seconds | 5 |
| Window 600 seconds | 6 |

The mandatory case is the additional exclusion under total 99%, local 60%/75%
or a 180-second window. Its eligibility is therefore sensitive to the proposed
approximation boundary; a pass does not resolve the unknown intensity inside
its omission. The stricter alternatives and the explicitly rejected paused case
are grounds for a concrete Analyst decision, not automatic production adoption.

There are **13 controlled synthetic counterexamples**. Equal observation totals
with dispersed versus concentrated omissions produce different screen outcomes;
one isolated 600-second segment in a long session and missing starts/endings
are rejected. Closed known pauses compress the screening clock and exclude
nonzero stopped samples from weighted-power calculation. Uniformly sparse
observations remain unsupported, without creating per-second values.

**Residual counterexample:** an unknown 90-second hard-effort omission can pass
this screen while the reference score is approximately **11.42% too low**.
An equally long recovery omission changes the score approximately **+1.20%**.
The known-hard case is rejected when independent evidence exists; the unknown
case cannot be distinguished by timestamps alone. Even 99.17% sample density
can conceal a short hard interval. The screen targets **clearly unrepresentative
time distribution**, not all intensity-dependent bias. This is an explicit
limitation of the proposed approximation, not proof that every passing trace
represents whole-session effort.

The uninstalled case-limited scenario now has **two substitutions rather than
three**; complete/corrected results remain unchanged. Its frozen 42-day total
would change 1,747.97 to 1,795.64; 90-day total 3,034.25 to 3,081.92; endpoint
Fitness/Fatigue/Form approximately +0.971/+2.969/−2.430. This illustrates the
method's modeling effect, not current app behavior or a validated archive policy.
The [safe aggregate output](distribution-screen-evaluation.json) records exact
thresholds, synthetic results, case counts, window effects and the retained 117
decoupling outcomes. Detailed case evidence remains local-only.

## Verification and preservation

- **373 Python tests pass**, including 10 diagnostic method/distribution tests.
  Sliding-window results match independent direct bin counts; boundary equality,
  leading/trailing gaps, nonzero source origin and timer-clock distinctions pass.
- **465 general Chromium assertions** and **438 representative assertions** pass,
  covering 13 activities / 32 date-range inspections, including both mandatory
  regressions. Actual plots are 600/400 CSS pixels; stress-strip alignment and
  exact-date mouse/keyboard/touch checks pass on desktop and 320-/390-pixel phones.
- **24 normalized-power results match the actual integrity-bound pinned upstream
  function**. Repeated detailed diagnostic outputs are identical.
- Independent current checks pass for **3,053 daily models, 1,263 observed-power
  calculations and 874 HR formulas** at the frozen completed-day endpoint
  `2026-10-10T00:30:00+00:00`. The running page also includes the current local day.
- Every one of **1,418 production ride results / 3,053 frozen daily results**
  matches the preceding v3 implementation exactly. HR candidates, all 117
  decoupling outcomes, Performance-v2, cache/source versions and algorithms are
  unchanged. Coverage stays 1,150/1,418; outdoor coverage stays 10/148.
- **All 20 original tables and 1,422 originals** remain intact; integrity is `ok`
  and foreign-key violations are zero. Diagnostic transactions preserve all
  tables including caches. No new migration, source import or dataset change.
- Existing Home outside its Training State snapshot is unchanged at an identical
  clock; Performance is unchanged at an identical clock; Activities body is
  unchanged at the same timezone. Stable Activity Review routes pass in-browser.
- Approved historical FTP and the original 496,966-byte Elevate CSV match their
  recorded hashes. The reference's final 14 projected days remain excluded from
  completed-training comparisons. Previous external comparison results remain
  applicable because the complete production series is identical.

See [verification aggregate](distribution-screen-verification.json). Private
source/detail reports and screenshots remain ignored. The current exact proposal
and per-case sensitivity are in
`local_data/p4-02-power-followup/distribution-screen-private.md`.

## Reproduce and review

```sh
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python tools/verify_training_state_production.py \
  --data-dir local_data/p4-02-baseline/store \
  --baseline-dir local_data/p2-05-review \
  --as-of 2026-10-10T00:30:00+00:00 \
  --output local_data/p4-02-power-followup/distribution-preservation.json
.venv/bin/python tools/evaluate_training_state_session_power.py \
  --data-dir local_data/p4-02-baseline/store \
  --before local_data/p4-02-power-followup/before-private.json \
  --after local_data/p4-02-power-followup/after-private.json \
  --blocked-cases local_data/p4-02-interval-diagnosis/diagnosis-private.json \
  --cases local_data/p4-02-power-followup/cases-private.json \
  --reference data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv \
  --reference-source local_data/p4-02-power-followup/activity-computer.ts \
  --aggregate-output reports/P4-02/distribution-screen-evaluation.json \
  --private-output local_data/p4-02-power-followup/distribution-screen-final-private.json
npx --yes --package @playwright/cli playwright-cli -s=p402 run-code \
  "$(cat tools/verify_training_state_browser.js)"
npx --yes --package @playwright/cli playwright-cli -s=p402 run-code \
  "$(cat local_data/p4-02-power-followup/browser-private.js)"
```

The upstream source pin/hash and source download procedure remain in the previous
report. Open the skill-managed Chromium session before the browser commands.
Private source inputs and independently declared cases must already be available;
these commands do not fetch activity history or modify original files.

**Review needed:** accept/revise the proposed 80% total / 50%-of-every-300-second
distribution rule, its demonstrated bias limitations, duration/pause semantics
and existing source/class proposal before authorizing a production estimator.
Review the implemented 600/400-pixel plot and preserved behavior separately.
No gate release, merge, Owner acceptance or subsequent task is claimed.
