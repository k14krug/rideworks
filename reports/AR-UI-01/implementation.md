# AR-UI-01 — Activity Review implementation

Owner-approved visual reference implemented in the real RideWorks Activity Review.
**Ready for HARD — Analyst Gate 1; not accepted.** Owner Gate 2 remains required.

## Delivered behavior

- Shared source-neutral review composition for native FIT, retained API streams,
  thin/unsupported and outdoor modes. A coherent hero and four source-labelled
  metrics precede local section links, the ride chart and real companion cards.
- The overview places the large chart alongside Ride Summary on desktop, followed
  by the full-width Power Curve, then Workout Context and Current Next Ride.
  These stack in the same reading order on smaller screens. Classification correction retains its original save action,
  nonce, timezone and activity-return semantics; current next ride uses the live
  Plan and never invents a historical recommendation or confirmed race.
- Ride Power/HR charts are 380 CSS px on desktop and 320 px on phones. Independent
  initially checked controls hide/show real series, axes and inspection markers;
  unavailable signals are labelled and disabled. Readouts explicitly say Hidden
  when a signal is hidden. Raw limits, samples, gaps, zero watts and timing remain
  unchanged. Both-hidden and all-missing states have explicit messages.
- Existing PC-01 chart spans the complete content width (350/320 CSS px height).
  Unsupported comparisons collapse the unused plot area and remove its empty
  keyboard target; an available historical baseline remains fully visible.
  Exact duration inspection, independent prior-period choices, contributor links,
  source details and historical previous-six-week default remain intact.
- Accepted best-20 and its distinct previous-six-week comparison are compact and
  retain the exclusive lower boundary. PC-01 retains its inclusive lower boundary.
  Calculation details and all native/API/associated evidence remain inspectable
  through semantic disclosures; no source fields or unavailable reasons are lost.
- Layout is scoped to `.activity-review-redesign`. Global navigation, branding,
  source selection, metrics, Training State, Home, Activities, Performance and Plan
  retain their established contracts. No external fonts, frameworks, source fetches,
  schema migrations or Phase 6 work.

## Fidelity and deliberate differences

The approved HTML reference was opened in Chromium, its Power/HR controls exercised,
its historical selector inspected, and desktop/320px captures compared with the
production page. Actual FIT, API-rich and thin full-page captures were produced at
1440, 1024, 768, 390 and 320 CSS px. Private titles and screenshots remain local.

The reference's hero, pale gradient, blue/teal hierarchy, stat strip, section links,
chart/summary arrangement, full-width curve, context row and bottom disclosures
are retained. Adaptations follow available evidence and the Owner’s explicit follow-up:

- **Owner section-order update (2026-10-11):** Power Curve now appears above
  Workout Context and Current next ride on desktop and mobile. This supersedes
  the reference’s placement of the context cards before the curve; sources,
  calculations, controls and review gates are unchanged.

- Real global shell remains unchanged, including its mobile navigation. Mobile
  local navigation sticks at the top after the global shell scrolls out of view.
- Existing numerical PC-01 chart and three readout panels replace the mock chart's
  invented curve and bespoke side readout. Evaluated-anchor semantics stay visible.
- The native summary can lack average HR even with recorded HR samples. API supplied
  averages can differ from returned samples. Neither is replaced by a calculation.
- Thin API metrics use only its current supplied summary. Competing/unsupported
  file and CSV pages show Unavailable hero metrics with complete source summaries
  in disclosures; no new cross-source canonical summary or CSV-unit guessing.
- Best Efforts contains the real accepted best-20 and prior comparison, without
  the mockup's illustrative extra metrics. Source-specific details, inferred
  classifications and provisional planner caveats remain visible and accurate.
- Final inspection corrected the inherited tablet summary-grid rule and collapsed
  the no-duration plot, retaining missing-source messages and accessible controls.
- Readout detail and complete source evidence naturally make some real pages
  longer than the mockup. No content is hidden merely to fit one viewport.

## Candidate page language for future work

These are scoped implementation patterns, not an authorization for other pages:

| Token/pattern | Current review value |
| --- | --- |
| Ink / blue / teal | `#132b48` / `#2563eb` / `#0c9c92` |
| Canvas / stroke | `#f4f7fb` / `#e0e8f1` |
| Muted text | `#526780` (stronger contrast than mockup captions) |
| Card radius / padding | 14px / 24px desktop, 20px tablet, 18px mobile |
| Chart heights | Ride 380/320px; Power Curve 350/320px |
| Information patterns | identity/stat strip; named local anchors; large inspectable charts; compact live context; grouped evidence disclosures |

## Verification

Final verification: **445 Python tests**, five focused source-mode tests,
**26,463 Chromium checks** (14,127 synthetic / 9,837 private review checks;
1,945 existing Power Curve, 510 Training State, 14 accepted-page/touch and
30 unchanged-page geometry/style checks). Zero browser errors. Aggregates are
recorded in `checks.json` and `preservation.json`. Five focused source-mode tests supplement the full suite.
The Owner section-order follow-up reran the full Python suite, both private and
synthetic review browser matrices, and the fixed-clock preservation comparison.
The review matrix now checks the requested physical section order at every width.
Browser checks cover section/link targets and scroll clearance, unique IDs,
expanded-source wrapping, sample/curve readouts, controls, exact period membership,
keyboard, actual Chromium touchscreen, save/return and reduced-motion contexts.

`verify_activity_review_preservation.py` reads the same disposable retained-source
store using detached accepted `main` and task code at **2026-10-11 12:00 PDT**.
It compares 27 representative source combinations, all 26 store table hashes (including the 20 previously preserved source tables),
all artifacts, raw native/API sample JSON, summaries, best-20/context/provenance,
PC-01 JSON for every prior option, classification/intent and live next-ride content.
Performance, Training State, Plan and Dashboard model outputs use the same clock.
New thin hero metrics are separately validated against the current supplied API
summary or explicit missing values. Snapshot files contain private source data and
must remain in ignored local storage; only aggregate equality is committed.

All cached profiles are covered by exact full-table equality; analytical code and
sources remain unchanged. This task does not claim to rerun the prior PC-01
122,112-window numerical oracle or new source imports/sync. Existing full tests
continue covering cache invalidation and ordinary sync behavior.

## Reproduction

Use a disposable copy of the retained store; never an original archive as a write
target. The detached baseline is accepted `main` at `d951a14`.

```bash
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -m unittest discover -s tests -p 'test_rideworks_activity_review.py' -q
.venv/bin/python tools/preview_activity_review.py --data-dir /path/to/new-synthetic-store
.venv/bin/python -m rideworks --data-dir /path/to/disposable-review-store serve --port 8791
.venv/bin/python tools/verify_activity_review_preservation.py \
  --code-root /path/to/accepted-main-checkout --data-dir /path/to/disposable-review-store \
  --snapshot /path/to/ignored-private-before.json
.venv/bin/python tools/verify_activity_review_preservation.py \
  --data-dir /path/to/disposable-review-store --snapshot /path/to/ignored-private-before.json \
  --compare --aggregate-output /path/to/safe-preservation.json
```

Run `tools/verify_activity_review_browser.js` through Playwright CLI `run-code`,
replacing `CASE_INPUT` locally with an object containing `base`, a `private` or
`synthetic` capture prefix, and cases `{mode, path, capture}`. Choose actual native,
API and thin UUID routes (`capture: true`), plus outdoor and missing-signal cases.
No private config belongs in Git. The synthetic preview supplies these modes.
Existing `verify_power_curves_browser.js` and
`verify_power_curves_regression_browser.js` run through the same CLI session.
Open the synthetic Performance route with `?synthetic=1` for the former tool's
synthetic-only assertions. Training State's existing smoke can be run with its
local server origin substituted in an ignored copy. Screenshots remain in ignored
`output/playwright/`; only explicitly synthetic selected captures are committed.

## Handoff

Running disposable review: `http://127.0.0.1:8791/activities`; open any actual ride.
Native FIT, retained-stream API and limited-evidence pages are available. The
accepted original store is untouched. [Draft PR #30](https://github.com/k14krug/rideworks/pull/30) contains implementation commit
`f708eb2`; branch and current handoff are recorded in `STATUS.md`. Analyst review must clear Gate 1 before Owner running-page Gate 2.
No merge, done status, next-page redesign or Phase 6 is authorized at this handoff.

## Computed synthetic production captures

These screenshots contain only the generated source-neutral preview, rendered by
actual RideWorks code. They contain no personal activities or source paths.

| Mode | Desktop | 320px phone |
| --- | --- | --- |
| Native FIT | [Desktop](synthetic-native-desktop.png) | [Phone](synthetic-native-320.png) |
| API retained stream | [Desktop](synthetic-api-desktop.png) | [Phone](synthetic-api-320.png) |
| Metadata only | [Desktop](synthetic-thin-desktop.png) | [Phone](synthetic-thin-320.png) |
