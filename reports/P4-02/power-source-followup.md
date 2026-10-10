# P4-02 — Independent power stress, taller plot and session-method proposal

**Ready for HARD — Analyst Gate 1 and the §13 session-method gate.** Implemented
under `/TASK P4-02`, the revised JIT/design at `fb9b0c1`,
[decoupling authorization](https://github.com/k14krug/rideworks/pull/24#pullrequestreview-5480095855)
and [updated method/chart direction](https://github.com/k14krug/rideworks/pull/24#issuecomment-6100472191).
Owner Gate 2 remains unaccepted; PR #24 stays draft. Session estimation is
**diagnostic-only** and has not changed production selection.

**Later follow-up:** [Second height refinement and distribution-screen proposal](distribution-screen-followup.md) supersedes the dimensions and representativeness proposal below; these results remain historical evidence.

## Delivered behavior

Training State now evaluates trusted virtual power independently of Performance's
1,200-second best-20 requirement. Native extraction counts, values and absolute
timing are checked; native power evidence retains precedence over API fallback.
API requires a unique current summary/observation pairing, confirmed device watts,
full high-resolution paired streams, and valid ordered times/watts. Competing
usable sources are rejected rather than ranked by format, completeness or score.

Existing P4-01 calculations are unchanged: observed work only, FIT correction
<=15 seconds per gap and <=1% overall, explicit timer exclusion/NP reset, API
observed-only power, >=600-second partial segments, dated FTP and honest scope.
Current HR-before-partial selection remains in effect pending the separate
session-method approval. The HR algorithm, stream/summary fallback and every HR
candidate remain unchanged. Performance-v2 is untouched.

Version **training-state-v3** and power policy
**virtual-recorded-stress-evidence-v1** enter cache signatures. Candidate sources
and exclusions are retained separately and visible in source inspection. Existing
power scores/work/scope are preserved; eligibility provenance now describes
stress rather than best-20 eligibility. The cache recomputes once and is reused
deterministically. No schema migration was added.

The actual trend plot is now **400 CSS pixels on desktop / 300 on narrow screens**,
inside 570-/470-pixel SVGs with a separate aligned stress strip. All curve, axis,
zero-line, bar, guide, hover and keyboard coordinates follow that geometry.
The SVG uses its actual CSS width, including 320-pixel phones, so aspect-ratio
scaling cannot shrink the promised plot or distort cursor selection.

## All 117 previously suppressed candidates: actual selection outcomes

| Recorded candidate | Rides | Before selected | After selected |
|---|---:|---|---|
| Calculated | 53 | 43 HR / 10 unavailable | 53 calculated power |
| FIT corrected estimate | 19 | 15 HR / 4 unavailable | 19 FIT estimates |
| Observed partial | 45 | 11 HR / 34 unavailable | 11 HR / 34 partial power |

**106 selections change; 11 keep HR.** Forty-eight become scored; 58 switch
from HR to qualified calculated/estimated power. Existing qualified/partial
power selections stay identical. No score is selected because it is larger.
All changes belong to the originally diagnosed 117; all HR candidates are
identical. Observed work additionally becomes available from trusted short
recordings, including intervals too short for stress or lacking dated FTP.

Coverage changes **1,102 -> 1,150 / 1,418 cycling rides**; unavailable falls
316 -> 268. Selected classes: 642 calculated, 150 FIT estimates, 210 HR estimates,
148 partial power. Scored days: 999 -> 1,025. Outdoor coverage remains 10/148.

At the frozen completed-day endpoint, trailing 42-day stress remains 1,747.97;
90-day stress changes 3,000.79 -> 3,034.25 (three changed rides), and 365-day stress
8,083.88 -> 8,289.61 (15). Endpoint Fitness/Fatigue/Form change approximately
**+0.362 / +0.003 / +0.367**. Earlier differences decay over time. The mandatory
interval workout's selected HR score remains unchanged; its current-state levels
can move because earlier eligible training now contributes. Decoupling alone
does not resolve that workout's session-power issue.

## Diagnostic method and exact approval proposal

Reference inspected and pinned at
[`df9e2cebf5055d28b652628c8654a701845935cc`](https://github.com/thomaschampagne/elevate/blob/df9e2cebf5055d28b652628c8654a701845935cc/appcore/modules/shared/sync/compute/activity-computer.ts).
Its time-buffer implementation uses **non-overlapping batches**, with a time
threshold checked before adding the arriving time delta, and drops an unfinished
final batch. It is not the overlapping 30-second rolling NP used by P4-01.
The diagnostic reproduces these available-sample arithmetic means/fourth moments
and applies `100 * reported_active_seconds / 3600 * (weighted_power / dated_FTP)^2`.
The proposal retains unrounded intermediates and rounds presentation; the
reference rounds intermediates to three decimals. This difference is explicit.
The reference's [fitness selector](https://github.com/thomaschampagne/elevate/blob/df9e2cebf5055d28b652628c8654a701845935cc/appcore/src/app/fitness-trend/shared/services/fitness.service.ts)
prefers available power-meter PSS to HRSS. No reference export score or setting
enters RideWorks calculations.

**Proposal for review, not an approved production specification:**

- Method `elevate-time-buffer-session-pss-v1`, class **Estimated session power**,
  with explicit unverified representativeness/full-session inference. Preserve
  the original measured/corrected/partial candidate and observed work separately.
  The implemented experimental method has a `diagnostic-` prefix.
- Use only the independently trusted, unambiguous measured-power source and
  approved date-effective FTP. API duration is the paired summary's positive
  moving time <= elapsed time. FIT uses reported timer duration; permit only
  a documented one-bin boundary discrepancy between integer seconds and elapsed
  endpoints. Do not invent moving duration from CSV or recording span.
- Use available watt/time pairs without synthesizing samples. Missing watts are
  omitted, not treated as zero. Invalid watts or ambiguous/nonascending time,
  absent FTP, unsupported duration, recordings exceeding reported elapsed bounds,
  contradictory/unclosed timers and competing trusted sources are exclusions.
- Split valid known timer intervals, exclude stopped samples and reset the
  buffer. Require timer-interval duration to agree with reported active duration
  within one bin. This is a targeted departure from literal reference processing
  justified by known pause evidence. It does not change P4-01 interval results.
- Retain the existing >=600-second observed segment as an initial evidence floor
  for this proposal. Report observed bins, native gaps, excluded/missing watts,
  short segments, duration basis and sampled/moving ratios. **Do not use a
  percentage as proof of representativeness.** Known workout evidence establishing
  omitted intense effort excludes a session estimate even at high sample density.
  A title does not establish such evidence; the controlled experiment has known
  intensity ground truth. Unknown gap intensity remains an explicit estimate risk.
- Prefer supported recorded/corrected power; evaluate a separately eligible
  session estimate ahead of HR when recorded stress is partial. If the estimate
  is excluded, preserve supported HR/partial/unavailable fallback. Never choose
  the larger numeric score. A proposed future version/power-policy change must
  invalidate caches; no new production class is installed in this continuation.

The Analyst must review the time-batch algorithm, pause pooling, one-bin FIT
duration convention, 600-second floor and how unknown representativeness is
handled **before this proposal becomes a production selector**. The floor alone
does not establish full-session accuracy, and no arbitrary global coverage/gap
threshold has been adopted. Further eligibility refinement may be needed.

## Evidence and exceptions

Thirteen private real cases include the independently predeclared interval,
threshold and ordinary workouts, mandatory outdoor HR case and ordinary/low
comparisons, plus recordings independently selected by corrected gaps, sparse
coverage, unresolved timer and known pause evidence. Seven yield numerical
session candidates; three fail explicit timer/duration agreement, one has an
implausible duration, and two have no unambiguous trusted power source.
Numerical candidates are not asserted verified representative sessions.

The required interval candidate uses the retained measured API arrays and
paired moving duration. Its raw sample/moving-time ratio is slightly greater
than one because recorded points include nonmoving observations; that ratio is
not active coverage. The private report records the exact gap, source/device
evidence, >=600-second subtotal, weighted power, session PSS and isolated
Fitness/Fatigue/next-day Form response. Its disagreement with Elevate is largely
explained by the approved FTP denominator, without fitting or adopting vendor FTP.
The original FIT is absent from the retained store. Legitimate Owner download is
available through the normal Zwift activity interface, documented by
[Strava's official instructions](https://support.strava.com/en-us/articles/15401915-zwift-and-strava);
availability/quality of that particular file has not been verified. No source
fetch, archive scan or import was performed.

Controlled cases demonstrate material risks rather than just arithmetic:

- Equal **97.5%** sampling produces **-11.42%** reference-score error when a hard
  interval is omitted versus **+1.20%** when recovery is omitted.
- **99.17%** sampling can omit known intense effort and produce **-3.84%** error.
- Removing all hard blocks leaves 33.33% sampling and **-74.32%** reference error;
  known omitted effort excludes the proposed selection.
- Uniform sparse samples can still produce reference weighted power, but fail
  the proposal's established continuous-segment floor.
- Known pauses with nonzero recorded watts show why stopped samples must be
  excluded and buffers reset. Actual paused partials still have unknown omitted
  intensity; their numerical estimate requires quality review.

Complete recorded-power examples also differ between rolling NP and reference
batches. These are method/duration effects, not defects repaired by a multiplier.
The private evidence retains both values. A three-case **uninstalled** scenario
shows daily and 7-/42-/90-/365-day effects; it is not an archive-wide estimator
policy or a production trend. Mandatory outdoor HR remains selected unchanged.

## Verification and handoff

- **368 Python tests**, including 10 independent power-source tests and five
  experimental session-method tests. Short FIT/API, corrected gaps, partial
  fallback, native/API precedence, competing sources, stream pairing, dated FTP,
  cache-policy invalidation/reuse and unchanged Performance are covered.
- **305 general Chromium assertions** and **435 private assertions** over
  13 Activities / 32 range inspections; 3-/12-month/all-history curves, actual
  sources, line/strip hover, selection, summary uncertainty, keyboard, touch and
  390-/320-pixel phones. Desktop/mobile screenshots inspected privately.
- Independent checks: **3,053 daily models, 1,263 observed-power calculations,
  874 HR formulas**. **18** real/synthetic NP cases match execution of the actual
  pinned reference function body in Node. Repeated experimental outputs identical.
- **20 original tables / 1,422 artifacts preserved**, integrity `ok`, zero FK
  errors. Diagnostics enforce query-only mode and an all-table/cache digest.
  Both stores are schema 8 at verification; the existing derived cache is
  excluded from authoritative-table comparison. This work adds no migration.
- Home outside its Training State snapshot and Performance are identical at
  equal clocks; Activities HTML is identical. Source data, approved FTP and
  the unchanged authorized Elevate CSV remain intact; 14 projections excluded.

Artifacts: [selection/method aggregates](session-power-evaluation.json),
[math/preservation/browser verification](power-source-verification.json), and
[updated reference sanity](power-source-elevate-sanity.json). Detailed cases,
source timing, exact scores, before/after and diagnostic curves, downloaded
reference source and screenshots remain ignored/local-only.

**Next:** Analyst review of the implemented decoupling/taller plot and the exact
experimental session-estimate proposal. After explicit method authorization,
implement its selected class and repeat independent cases/full preservation and
Gate 1 before Owner Gate 2. No merge, task acceptance or next phase.

```bash
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python tools/verify_training_state_production.py \
  --data-dir local_data/p4-02-baseline/store --baseline-dir local_data/p2-05-review \
  --as-of 2026-10-10T00:30:00+00:00 \
  --output local_data/p4-02-power-followup/preservation-and-math.json
.venv/bin/python tools/evaluate_training_state_session_power.py \
  --data-dir local_data/p4-02-baseline/store \
  --before local_data/p4-02-power-followup/before-private.json \
  --after local_data/p4-02-power-followup/after-private.json \
  --blocked-cases local_data/p4-02-interval-diagnosis/diagnosis-private.json \
  --cases local_data/p4-02-power-followup/cases-private.json \
  --reference data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv \
  --reference-source local_data/p4-02-power-followup/activity-computer.ts \
  --aggregate-output local_data/p4-02-power-followup/session-evaluation.json \
  --private-output local_data/p4-02-power-followup/session-evaluation-private.json
npx --yes --package @playwright/cli playwright-cli -s=p402 run-code \
  "$(cat tools/verify_training_state_browser.js)"
npx --yes --package @playwright/cli playwright-cli -s=p402 run-code \
  "$(cat local_data/p4-02-power-followup/browser-private.js)"
git diff --check
```

The pinned public `activity-computer.ts` is downloaded to the ignored local path
shown above; its SHA-256 and commit are in the aggregate report. Private cases
use the previously documented date/title/optional Activity ID/role format.
Before/after files contain the frozen `data` and `rides` calculation outputs.
