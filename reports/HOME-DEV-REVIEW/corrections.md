# HOME-DEV-REVIEW engineering corrections — 2026-10-18

**Initial pass at `8f23620`.** Analyst review subsequently identified a remaining
post-Plan writer-lock window. The original classification-pause test did not
cover it; the follow-up reproduced it and extends deferral through response
completion. See [current follow-up evidence](post-plan-concurrency.md).

Draft PR [#46](https://github.com/k14krug/rideworks/pull/46), branch
`fix/home-dev-review-corrections`, targets `dev`. Implementation started at
`5ca9fb3`, whose application code matches reviewed `dev` at `932f391`.
Production baseline remains `dcd77f1`. No merge, deployment, production-store
operation, or restart of an existing development process was performed.

## Corrections

- **Initial Home FTP correction:** Run the existing Plan calculation before Relative
  Effort can populate stress caches. This restores Plan's deferred stress and
  classification write batch and the existing stale-snapshot retry. No changes
  to timeouts, transactions, training models, or cache invalidation rules.
- **Activities layout:** At widths up to 1100px, put the title across a two-column
  set of labeled fields; retain single-column phone rows at 620px and below.
  Desktop retains its existing five columns. Links, source fields and effort
  labels remain present. The browser verifier now covers 650/768/850px in
  addition to desktop/mobile and checks usable title width and bounded row
  height, rather than relying only on document overflow.
- **Ride sidebar:** Reduce summary-row vertical padding from 10px to 6px and
  the gap between sidebar cards from 18px to 12px. No fixed heights, hidden
  overflow, removed evidence, or reduced type sizes.
- **Chart readout:** Remove the overriding duplicate CSS rule. Browser-computed
  top padding is now 0px and minimum height 24px. The Activity Details verifier
  checks these computed values.
- **History scan efficiency investigated, deferred:** The rating scan still
  executes 7,236 SQL statements over 1,420 cycling rides. Three warm runs before
  the correction took 0.299/0.336/0.308 seconds; after, 0.319/0.411/0.321 seconds.
  Pure classification took about 0.008–0.010 seconds. These variable timings
  establish no improvement. Existing page/model interfaces do not expose one
  reusable full stress result set to all Home consumers. Keep this bounded
  correction focused on transaction correctness rather than expanding those
  interfaces or introducing another cache. The JIT explicitly permits deferral.

`relative-effort-v1`, its mixed HR/power population, date window, duration bases,
thresholds and outputs are unchanged. Calibration remains an Owner decision.

## Reproduction and automated checks

All Python commands used command-scoped `DEBUG=0` and
`PYTHONDONTWRITEBYTECODE=1`; `.env` was unchanged.

```bash
.venv/bin/python -m unittest discover -s tests -p test_rideworks_ftp_page.py \
  -k test_home_get_finishes_plan_batch_before_training_summary_and_allows_ftp_write -v
.venv/bin/python -m unittest discover -s tests -p test_rideworks_ftp_page.py \
  -k home_get -v
.venv/bin/python -m unittest discover -s tests -q
```

Before the fix, the original concurrency test reproduced `database is locked`.
After the fix, it and the added populated-but-FTP-invalidated cache variant
passed. Five repetitions of each also passed (10 runs). Both retain the
concurrent writer, coherent snapshot, retry, refreshed 250W FTP and cache checks.
The full Python suite passed **524 tests** in 28.073 seconds.

First visible Activities row, independently measured in Chromium:

| Viewport | Before title width / row height | After title width / row height |
| --- | --- | --- |
| 1440px | 549 / 68px | 549 / 68px |
| 1024px | 220 / 74px | 792 / 108px |
| 850px | 46 / 301px | 618 / 108px |
| 768px | 0 / 1042px | 536 / 108px |
| 650px | 0 / 1042px | 418 / 123px |
| 620px | 556 / 152px | 556 / 152px |
| 390px | 326 / 152px | 326 / 152px |
| 320px | 256 / 173px | 256 / 173px |

## Browser verification

Used Playwright CLI with temporary loopback servers on 8791 (corrected source)
and 8792 (archived `origin/dev`). Both used the existing disposable private
review store, not the active development store. Script templates were supplied
as `run-code` arguments with private case URLs injected locally.

- `tools/verify_activity_review_browser.js`: **25,033 assertions passed** across
  native power, corrected power, estimated session power, HR estimates,
  partial-only and unavailable evidence at 1440/1024/768/390/320px. Includes
  source-value fidelity, chart controls, keyboard/pointer/touch, Power Curve,
  effort colors, compact readout styles, and unchanged sidebar-height limits.
- `tools/verify_rideworks_visual_browser.js`: **1,691 assertions passed** across
  Activities, both Performance modes, Training State, Plan and Settings at
  1440/1024/850/768/650/620/390/320px. Sorting, filtering, pagination, links,
  disclosure expansion, focus and responsive layout pass.
- Supplemental keyboard disclosure/geometry checks: **53 assertions passed**
  across all six evidence cases at desktop and 320px. The collapsed desktop
  sidebar ends 15.91px above the chart for corrected native evidence and 3.69px
  above it for session/HR estimates, replacing the prior 20–40px overruns.
  Keyboard opens/closes the rating methodology and expanded evidence fits.
- `tools/verify_home_browser.js`: **1,266 assertions passed** at
  1440/1024/768/390/320px with `preserveRecommendationPosition: true` against
  archived `origin/dev`. Covers exact unchanged recommendation position,
  Home/Plan agreement, seven recent rides and effort indicators, Fitness-only
  trend, actual SVG marker/gap pixels and no inline styles, mileage keyboard/
  pointer/touch inspection, links, disclosures and no page errors.
  Runtime HTTP CSP retains `script-src 'self'` and `style-src 'self'` with no
  `unsafe-inline`; the completed browser session has zero console messages.

Total: **28,043 browser assertions passed**, including the supplemental checks.

The first Home template run stopped at its historic redesign-only requirement
that the recommendation move upward compared with the baseline. This task's
baseline already has the accepted layout. Added an explicit
`preserveRecommendationPosition` mode requiring **exactly equal** vertical
position; the default historic improvement assertion remains intact. No product
CSS or layout was changed to satisfy that comparison.

Private browser logs, screenshots and snapshots remain outside Git under
`/tmp/rideworks-home-corrections/`, `/tmp/output/playwright/` and the existing
`/tmp/rideworks-astra-review/`. Screenshots include `ar-ui-01-corrections-*` and
`rollout-corrections-after-*` and `home-corrections-before/after-*`; desktop,
tablet and phone captures were inspected.
No private ride titles, identifiers, database or source files are included here.

## Preservation and remaining review

Six fixed-clock comparisons (Los Angeles/Tokyo; two October times and a January
UTC year boundary) preserve exact Relative Effort, Training State, Plan and
dashboard outputs; FTP and Performance hashes also match. All 26 non-cache
table fingerprints are unchanged. The independent real-data dashboard verifier
also passed:

```bash
.venv/bin/python tools/verify_rideworks_dashboard.py \
  --data-dir /tmp/rideworks-astra-review
```

The existing Activity Review preservation tool also passed against archived
`origin/dev`: **27 representative reviews, all 28 tables including caches,
1,422 original artifact hashes/sizes/modification times, accepted model hashes,
raw payloads, summaries, calculated values, provenance and approved reference**
match exactly. Integrity is `ok`; zero foreign-key violations.

```bash
.venv/bin/python tools/verify_activity_review_preservation.py \
  --data-dir /tmp/rideworks-astra-review \
  --code-root /tmp/rideworks-home-corrections/baseline \
  --snapshot /tmp/rideworks-home-corrections/activity-preservation.json
.venv/bin/python tools/verify_activity_review_preservation.py \
  --data-dir /tmp/rideworks-astra-review \
  --snapshot /tmp/rideworks-home-corrections/activity-preservation.json --compare
```

The baseline source was prepared with `git archive origin/dev` for `rideworks`,
`pyproject.toml` and the approved Elevate reference file. No active branch or
original source artifact was altered to construct it.

This initial pass fixed the original classification-pause failure but did not
close every Home writer-lock window; the linked follow-up supersedes that
conclusion. History-scan optimization is explicitly deferred. Mixed-source
calibration, final visual acceptance and Analyst acceptance remain open.
Chromium was exercised; Firefox/WebKit,
physical-device and screen-reader testing were not performed. Leave PR draft,
task `in_progress`, handoff `ready_for_review`; no automatic merge or deployment.
