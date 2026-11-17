# PC-03 implementation verification

Power → Power Curve now uses a square-root duration axis, taller plot, solid
weighted A/B lines, and a pinned in-chart inspector. Both independent period
selectors and their existing strict observed-power payload remain in place.
The inspector links each period's winning activity and retains exact mean,
integer sum/sample count, window, source and timer evidence in pinned Effort
details. It contains no elapsed-window assumptions or recorded-power minimum.
The common PC-01 grid is reconstructed only to retain breaks at unsupported
evaluated anchors; it is bounded by each series' last supported point and does
not calculate new values. An independent comparison through 100,000 seconds
matched all 160 grid anchors to `duration_grid`.

## Verification

- `DEBUG=0 .venv/bin/python -m unittest discover -s tests` passed **657 tests**.
  Focused `test_rideworks_power_curve.py` passed **24 tests**; it also checks
  pending messaging and the separate Performance and Activity Review assets.
  `node --check` and `git diff --check` passed.
- Chromium synthetic verification using `playwright-cli run-code` and
  `tools/verify_pc03_presentation_browser.js` passed **35 assertions**: exact
  strict evidence, per-duration winner links, positive/negative/zero/absent
  deltas, same-period role labels, unsupported gaps, square-root mapping,
  short/single-point/longer-comparison domains, empty and partial periods,
  and long titles with expanded details at narrow widths. The existing PC-02
  synthetic Activity Review browser checks passed **58 assertions**.
- Chromium on a disposable retained-data copy measured old/new chart heights of
  **370/510 px** desktop and **300/430 px** at both 390 and 320 px. Both series
  used solid lines with distinct weights and marker shapes. The inspector fit
  the plot with no page overflow, retained a usable plot target, and preserved
  its pin on resize. Mouse preview, pin/unpin, keyboard navigation and native
  link activation, Escape/focus return, touch pin/link/disclosure/scroll, and
  both period selectors were exercised. Same and overlapping periods were
  checked. Seventy displayed duration/series values and winner links matched
  the strict payload. The expanded 320 px evidence panel was visually reviewed;
  private captures remain local. Browser console had no errors.
- At a fixed clock the complete strict comparison payload matched pre-change,
  including period bounds, winners and per-effort evidence. The Activity Review
  panel HTML matched pre-change exactly. No calculation, source, schema, cache
  version, rebuild or API-fetch behavior changed. Home and strict 20-Minute
  History regressions passed; Performance navigation and period selection
  survived view switching. Existing cached results on the disposable copy were
  used without rebuilding.
- The retained-data copy predates one activity in the current local store.
  Among shared rows, strict and elapsed curve profiles matched exactly;
  Performance history results and signatures matched, with only calculation
  timestamps differing. This comparison is not a claim that the two stores are
  identical snapshots. Private data and screenshots are not included here.

This is a draft handoff for HARD — Analyst Gate 1. Owner running-Dev review is
required after Analyst clearance; no deployment is authorized.
