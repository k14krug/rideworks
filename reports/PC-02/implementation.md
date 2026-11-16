# PC-02 implementation verification

Activity Review uses a separately cached elapsed-time power profile. Recorded
zero, confirmed native timer pause, estimated single-second gap and unknown
power are kept distinct. Standard windows require 95% observed non-pause time.
A selected ride with 90–<95% full-ride coverage gets a separate unconnected
recorded-power minimum using only observed watt-seconds. It cannot enter a
historical envelope. Performance and Home retain the strict PC-01 profile.

## Numerical checks

`DEBUG=0 .venv/bin/python -m unittest discover -s tests` passed 657 tests.
`tests/test_elapsed_curve.py` includes an independent small brute-force oracle,
pause and single-hole examples, fractional and integer endpoints, coverage
boundaries, the API-only coverage reproduction, cache separation, historical
bounds, competing sources and interrupted rebuild retry. The output is synthetic.

On a disposable copy of retained data, the affected API-only ride has an elapsed
clock of 6,553 seconds. In that domain there are 6,177 observed seconds and 376
unknown seconds, no verified pause, and no interpolation in the fallback.
Independently summing only in-domain observed samples gives 596,058 watt-seconds:
596,058 / 6,553 = 90.95956050663818 W. Observed coverage is 94.26216999847398%.
The standard full-duration point is unavailable; the separate minimum rounds to
91 W. Diagnostic exact 5,400- and 6,000-second standard windows were ineligible.
The earlier zero-gap illustration was a diagnostic, not a required parity target;
the current fallback excludes all unobserved work, including the repairable second.
The strict 1,200-second profile remained 131,143 watt-seconds / 1,200 =
109.28583333333333 W, rounded to 109 W, before and after the rebuild.

## Rebuild and browser checks

A disposable local copy was used; no new API requests or source changes were made.
`DEBUG=0 .venv/bin/python -m rideworks --data-dir <private-copy> rebuild-power-curves`
computed 1,462 elapsed profiles in 60.680 s; an unchanged warm run reused 1,462
in 0.453 s (0.908 s total including strict-cache checks). A cached Activity Review
comparison took 0.765 s and one local HTTP request took 1.969 s. These timings
are a single local observation, not a deployment guarantee. A forced combined
rebuild took 102.043 s; hashes of records, sources, stream evidence, strict
profiles and Performance history remained equal. Database integrity and foreign
key checks passed on both the source store and the disposable copy.
After finalizing elapsed error reporting, a second forced elapsed-only rebuild
computed 1,462 profiles in 62.116 s and reproduced the elapsed profile payloads
exactly. The first forced comparison was not a valid elapsed parity check because
error reporting had changed between the initial and forced builds.

Chromium on the disposable copy displayed the distinct 1:49:13 minimum at
91 W with 94.3% coverage and 376 unrecorded seconds. End-key selection and
mobile touchscreen selection reached it. The 390- and 320-pixel layouts retained
the marker and comparison choices; the 320-pixel document had no horizontal
overflow. The 320-pixel chart and readout were visually inspected. Browser
console reported no errors. A second supported ride's ordinary full-duration
endpoint was inspected at its exact 3,620-second duration. The original rides
and screenshots remain private.

The 95% cutoff and 90% minimum floor are PC-02 policy, not claims of vendor
parity. Missing work can raise the full-ride average. Analyst and Owner review
remain required; this report is not task acceptance or deployment.

## 2026-11-16 Activity Review presentation revision

The Activity Review curve now has its own presentation script; the existing
Performance curve script and markup remain in use for Performance. The selected
ride and comparison use dark/heavier and lighter/thinner solid strokes. The
Activity Review duration mapping is square-root; plotted paths, ticks, marker
positions and nearest-anchor selection use that same mapping. The three lower
cards and rider-facing provenance links were replaced by an in-plot inspector.
It retains observed coverage, nonzero pause/estimate/unknown explanations and
the distinct recorded-power minimum explanation. No calculation, cache version,
source evidence, historical membership or rebuild path was changed.

### Revision verification

- `DEBUG=0 .venv/bin/python -m unittest discover -s tests` passed **657 tests**;
  focused `test_rideworks_power_curve.py` passed **24 tests**, including the
  new separate Activity Review/Performance markup and asset assertions.
  The first full run had one unrelated flaky privacy-test failure: a randomly
  generated test nonce happened to contain that test's short placeholder
  `123`. A complete rerun passed. `node --check` and `git diff --check` passed.
- Chromium synthetic checks, run with `playwright-cli run-code` and
  `tools/verify_pc02_presentation_browser.js`, passed **26 assertions**:
  sub-minute and single-point domains, fractional endpoint precision, a longer
  comparison domain, square-root mapping, anchor-only selection, unsupported
  breaks, positive/zero/negative deltas, attribution and links, the unconnected
  minimum, unavailable endpoint, empty chart and pending state.
- On a disposable copy of the retained store, the actual affected endpoint
  remained 6,553 s, **91 W**, 94.26216999847398% coverage and 376 unrecorded
  seconds. It remained a minimum with no standard endpoint or delta. The strict
  20-minute result remained **109 W**. Activity Review's full JSON payload was
  identical to the pre-revision payload. At a fixed clock, the Performance
  Power Curve HTML matched the pre-revision rendering exactly. Cached elapsed
  profiles, strict curve profiles and Performance history were byte-identical
  to the source store; no archive rebuild or API fetch was performed.
- Chromium desktop and 390/320 px mobile checks measured chart heights of
  **510/430/430 px**, versus the prior **350/320/320 px**. On the affected
  domain, 120 s maps to **13.53%** of plot width. Tick labels did not overlap,
  the right-edge duration remained visible, inspector bounds stayed within the
  plot, and the page had no horizontal overflow at either mobile width. The
  current and comparison strokes were solid at 3.5 px and 2 px respectively;
  the 320 px chart was visually inspected using a local-only private capture.
- Mouse preview, moving into the unpinned box, pin/unpin, pinned movement and
  leave, and opening the historical activity link worked. Keyboard Home/End,
  arrows, Enter/Space, Tab/Shift+Tab, real link activation and Escape/focus
  return worked. The chart had an accessible name and visible focus; keyboard
  selection and pin state updated the live region while mouse movement did not.
  Touch tap/pin, second-tap unpin, the unpin button, link navigation and a real
  touch drag scrolling the page without selecting a point worked. Resizing kept
  and repositioned the pin; changing the comparison cleared it. Empty/pending,
  supported and coverage-limited endpoints were checked. Chromium reported no
  console errors during the checks.
- The separate Performance chart retained its logarithmic axis, dashed
  comparison, three readout cards and keyboard behavior. Existing Home and
  strict Performance regressions passed in the full suite. Private ride data,
  captures and the disposable copy are not included in this branch.

The revised presentation is submitted for HARD — Analyst Gate 1; Owner
running-Dev review remains a separate subsequent gate.

## 2026-11-16 inspector refinement

The Activity Review inspector is 385 CSS px wide on desktop (previously 335),
capped to the plot on narrow screens. Its header shows exact elapsed time and a
signed displayed-watt difference only for two standard results. The current ride
has no title or self-link; the winning comparison ride's title is its link.
Standard assumptions appear only when nonzero; observed coverage and time are
in a collapsed Recording details disclosure available while pinned. The separate
minimum keeps coverage, unrecorded time and its explanation visible.

### Refinement verification

- `DEBUG=0 .venv/bin/python -m unittest discover -s tests` passed **657 tests**;
  focused `test_rideworks_power_curve.py` passed **24 tests**. `node --check`
  passed for the updated script. Synthetic Chromium verification through
  `tools/verify_pc02_presentation_browser.js` passed **58 assertions**, covering
  exact/fractional headers, positive/negative/zero and absent deltas, title
  links, no self-link, conditional assumptions for both series, on-demand
  evidence, disclosure reset, endpoint cases and retained axis behavior.
- Chromium measured a **385 px** desktop inspector versus the prior **335 px**.
  At 390 and 320 px viewports the actual inspector widths were **290 and 248 px**
  within **328 and 258 px** plots. Long synthetic ride names and expanded
  details wrapped without horizontal overflow; at least 119 px of plot height
  remained available. Pinning survived resize. Mouse, keyboard Tab/Enter,
  Escape and touch activated the comparison-title link and Recording details;
  opening details did not unpin. Period and point changes reset stale details.
- On the disposable retained-data copy, the affected full-duration result
  remained the separate **91 W** minimum at **1:49:13**, with **94.26%**
  observed coverage and **376 s** unrecorded, no standard endpoint or delta;
  strict 20-minute Performance remained **109 W**. The entire Activity Review
  curve payload matched the pre-refinement `6951793` payload; at a fixed clock,
  the Performance Power Curve HTML matched as well. Existing Home and strict
  Performance regressions passed. No schema/cache change, archive rebuild,
  source change or API fetch was performed for this refinement. Private data
  and browser captures remain local.

The refinement returns to HARD — Analyst Gate 1. Owner running-Dev review is
still required after Analyst clearance.
