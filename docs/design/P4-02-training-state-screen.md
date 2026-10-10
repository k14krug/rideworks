# P4-02 — Training State screen design

**Status:** **Owner-approved visual and interaction direction**, with a **taller trend-chart requirement added 2026-10-10**. Not a production implementation approval or Phase 4 acceptance.

**Requirements:** [P4-02 decision record](P4-02-training-state-direction.md), [accepted P4-01 DESIGN-003](DESIGN-003-training-state-model.md), [Phase 4 acceptance](../PHASE_4_ACCEPTANCE.md), and [product requirements](../PRODUCT_REQUIREMENTS.md).

## Purpose and visual reference

A simple, useful single-rider view of training consistency, model-based Fitness, Fatigue, Form, and contributing rides. Reuse RideWorks' current light navy/blue/green visual character, header/brand, compact white panels, and navigation. The Owner approved the locally reviewed interactive mockup on 2026-10-09. Its companion screenshots and HTML contain personal Elevate export values, are **not RideWorks calculations**, and **must stay out of Git**. This source-neutral design text is the durable reference for Dex; pixel-perfect mockup parity is not required.

## Navigation

- Add **Training State** between **Performance** and **Settings** in the existing sidebar.
- Keep the accepted Home mileage, Performance, and Activities content; add only a compact Training State snapshot/link as a secondary area, not a new opaque top-level Fitness Score card.
- The new page opens actual RideWorks Activity Review routes for inspected rides; do not substitute Elevate URLs or activity identities.

## Page hierarchy (Owner-approved)

1. **Heading:** Training State; succinct subtitle; unobtrusive **How these numbers work** disclosure.
2. **Date range:** 6 weeks / **3 months default** / 12 months / All history. No future projected dates.
3. **Selected-day values:** three compact displays with **Fitness** (blue, 42-day), **Fatigue** (amber, 7-day), **Form · start of day** (teal). One decimal and change versus seven days earlier when available.
4. **Main interactive chart:** three independently toggleable daily lines on a shared calendar axis; **Fitness and Fatigue enabled by default, Form disabled by default** (available through its checkbox), negative Form permitted, clearly visible Form-zero axis/reference, selected-day vertical guide, readable hover/focus state. **Owner follow-up (2026-10-10): increase the *actual trend-plot height again*.** The intervening implementation provides 400 CSS px of trends inside a 570-px desktop chart (300 inside 470 on mobile), which is still visually compressed. Target **about 600 px of line plotting area on spacious desktop screens** (a practical range of 560–640), and **about 400 px on smaller screens** (360–440), with optional sensible viewport-aware responsiveness. These are targets for the *trend-line area*, not the overall SVG/card; retain an additional dedicated aligned daily-stress strip, cursor guides, legends and date-axis space. Make the plot noticeably taller in both 3-month and 12-month views, without distorting the axes or merely enlarging whitespace. A tall chart may extend below the viewport; normal page scrolling is acceptable. Reduce height on small/short displays if needed to avoid unusable interaction.
5. **Daily selected-training-stress strip:** aligned horizontally with trend chart, source-distinguishing bars for qualified power, HR estimate, other/mixed or partial stress, and quiet markers for recorded activities with unknown stress. No-record days are not automatically labeled rest.
6. **Selected day:** persistent details (not just floating tooltip): local calendar date, daily selected model stress, each RideWorks activity title/link, selected stress, calculation source, and concise partial/unavailable flag; identify multi-ride days without double-counting methods.
7. **Recent workload:** trailing selected-date 7-/42-day **stress totals** and **distinct observed work kJ** subtotals with contributor/omission counts and source quality. Do not equate the units or present observed partial totals as complete training.

The chart is the dominant feature **by vertical as well as horizontal area**. Increase the trend line plotting region rather than adding whitespace or only enlarging the overall SVG container. Keep the synchronized daily-stress strip clearly visible with sufficient room for date labels. The selected-day and workload panels can appear side by side on desktop and stack on narrow screens.

## Interaction and display behavior

- Click, touch, or keyboard-focus and arrow keys select actual dates; selection persists without hover. Selecting a past date updates the three metric values, seven-day changes, detail panel, and trailing totals together.
- Switching time range retains the selected date when visible, otherwise selects the latest date; the latest calendar day is valid even when no ride occurred.
- All history may be *render*-downsampled if necessary, but computations and day inspection use exact daily data. No future projection or fixed Elevate-style training-zone/overload labels.
- Narrow screens retain usable date selection, synchronized chart/stress strip, readable small metric displays, and stacked lower panels. Maintain keyboard and non-color-only legends. The taller plot must not distort axes, clip labels/tooltip or hover guide, or break pointer-to-date mapping when the SVG/chart dimensions change. Verify actual desktop and narrow-screen browser layout.
- Prefer informational language, no medical or workout-prescription interpretation; include a short how-it-works explanation and source details on inspection.

## Model-display semantics (already decided elsewhere)

- Fitness and Fatigue: 42-/7-day exponentially weighted selected daily stress; Form: **previous day's** Fitness − Fatigue; early curve seeded zero and explicitly a model.
- Preferred inputs: qualified measured power (with approved dated FTP and unchanged P4-01 evidence rules); a practical HRSS-style estimate when qualified power cannot adequately represent the ride; exclude suspect Strava outdoor estimated power as primary stress.
- Under the approved pragmatic curve convention, a recorded unscored ride remains **stress unavailable** in activity evidence but gives **zero numeric contribution** to the trend. No-activity days likewise give zero *recorded* stress, not confirmed rest. Preserve version, assumptions, and source/missing distinctions.
- The exact HRSS formula/HR eligibility, use of approximate current resting/max HR as assumptions for earlier rides, and precedence between partial measured-power and usable HR remain separate **P4-02 algorithm decisions**, not settled by UI approval.

## Implementation boundary

This is a UI design decision, **not** a framework, schema, charting-library or deployment decision. Build a native-feeling RideWorks page with real sources and data. The local mockup's exported Elevate values, ride names, screenshots, and HTML must **not** be committed or reused as production fixtures. P4-02 needs a separate JIT and explicit start authorization. Owner visual acceptance will be sought again on the running real-data application.

## Owner-authorized external-reference privacy exception — 2026-10-09

The Owner explicitly authorized committing the exact unchanged Elevate CSV
[`fitness_trend_export.2026.10.9-15.58.52.csv`](../../data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv)
with its [provenance and limitations](../../data/reference/elevate/README.md).
This later instruction supersedes the earlier CSV prohibition for this one file
only. Original mockup HTML, screenshots, other exports and private activity data
remain local-only. The final 14 export days are projections and are excluded
from completed-training comparisons. Elevate results/settings are a benchmark,
never RideWorks production truth or initialization; the approved RideWorks FTP
history remains authoritative. JIT invocation, scope and Analyst/Owner gates
are unchanged.
