# HOME-UI-03 — Home Mileage by Year card

**Status:** pending — Analyst-authored JIT, 2026-10-28.
**Scope:** Focused Home dashboard enhancement following accepted and merged HOME-UI-02 and completed P3-01/HOME-UI-01. No reopening those accepted tasks.

## 1. Purpose

Replace the Home Annual Mileage Goal card with a compact Mileage by Year card, comparing current-year cumulative cycling mileage with the two preceding calendar years while retaining current-year goal progress and a rounded-up miles/week requirement.

## 2. Background and Owner decision

The Owner approved a private Home mockup on 2026-10-28. The bottom-right card is titled **Mileage by Year**. It shows three cumulative annual mileage lines (current year and two prior years), current YTD mileage, miles remaining, and the sentence:

**Ride N miles/week to meet yearly goal of T miles.**

The monthly chart axis uses numbers 1–12. The card must be **no taller than the neighboring Mileage Progress card**. Do not include the former goal progress bar, a goal reference line, the old annual-target line or additional calendar-pace text.

The Owner will pass the approved image directly to Dex as a **private visual reference**. Its sample yearly curves, 1,651.9-mile YTD value, 548.1-mile remaining value, 2,200-mile goal and 55 miles/week are **illustrative, not test expectations or permitted hardcodes**. Do not commit the image or private rider activity details.

This is a *new approved Home card design* that specifically supersedes the older P3-01 Annual Mileage Goal Home-card presentation, **not** the established P3-01 distance eligibility, annual goal, timezone or needed-weekly definitions.

## 3. Requirements Used

- [AGENTS.md](../../AGENTS.md): Analyst-owned JIT, repository synchronization, task/PR lifecycle, invocation, verification and privacy.
- [Product requirements](../PRODUCT_REQUIREMENTS.md): PR-001, PR-003, PR-004, PR-006, PR-012, PR-013; Dashboard and goal-progress requirements (DASH-001/DASH-004, GOAL-001/002/003).
- [Phase 3 acceptance](../PHASE_3_ACCEPTANCE.md) and [P3-01 JIT](P3-01.md): cycling and distance selection, browser-local calendar/year, accepted goal progress and needed-weekly arithmetic, data diagnostics and no fabricated distance.
- [HOME-UI-01](HOME-UI-01.md) and [HOME-UI-02](HOME-UI-02.md): accepted Home styling, layout, responsive behavior and preserved Training State/Performance views.
- Existing mileage calculation and presentation in rideworks/dashboard.py and the Home templates/styles/tests; inspect their **current** versions rather than assuming implementation details from this brief.
- Owner-approved private 2026-10-28 Mileage by Year Home mockup and explicit follow-up requests: two previous years, no goal line/bar, compact numeric month axis, limited card height, dynamic whole-number weekly mileage rounded **up**.

## 4. Execution Control

**Allowed Invocation: /TASK or /AUTOTASK.**

One bounded implementation unit. No autonomous product decisions or artificially staged implementation gates. Once verified and pushed, stop at **HARD — Analyst** technical review. After that, **HARD — Owner** running-UI visual approval is required before completion. The mockup approval establishes design direction but is not running-app acceptance. Do not automatically begin another task.

## 5. Scope and required implementation

### 5.1 Header and goal summary

1. Replace the bottom-right Annual Mileage Goal card with **Mileage by Year**, retaining its bottom-row/right-column position alongside **Mileage Progress**.
2. Show current-year actual mileage prominently as **N mi YTD**, using the accepted dashboard aggregate (not a new distance definition).
3. Show **R mi to goal**, where R is the nonnegative remainder from the existing configured year-specific annual mileage target.
4. When a target exists and is not reached, show **Ride W miles/week to meet yearly goal of T miles.** W is the **ceiling of the unrounded existing needed_miles_per_week** value, not a freshly invented formula or a ceiling applied after first rounding to one decimal. Example: 55.0 → 55; 55.1 → 56.
5. Existing P3-01 needed-weekly semantics count *remaining calendar days after the current browser-local date through December 31*. Reuse those semantics so the new displayed whole-number value is consistent with the current Mileage Progress line endpoint before display rounding. Do not derive mileage from a fixed 365-day year or arbitrary timestamp-based fractional weeks.
6. When annual goal is reached, show a concise completion state and 0 miles remaining; do not demand more miles/week. If the remaining days are zero with an unmet goal, avoid division by zero and use an honest unavailable/finished-year state. If no annual target is set, still show YTD and preserve a **Set annual goal** path to Settings. Preserve existing Settings goal editing (do not build an editor or new goal engine in this card).
7. Treat the weekly requirement as **arithmetic to hit a target, not a training recommendation**.

### 5.2 Three annual cumulative series

1. Build cumulative calendar-year mileage for current year, preceding year, and the year before that, advancing automatically on January 1 (for 2026: 2026/2025/2024).
2. Include only accepted cycling activities and the accepted distance selection: known file-backed distance first, current Strava API summary fallback, otherwise unavailable. Exclude unsupported-date activities and future activities according to the accepted Home browser-timezone/as-of rules. No CSV distance unit guesses and no duplicate counting.
3. Group ride distances by date in the accepted browser-local calendar, then compute running totals. Each line starts at zero at the year's start, rises only when accepted mileage exists and stays flat between rides.
4. The current-year line stops at the current as-of date; do not project into future months. Prior-year lines may run to December 31 when source coverage permits. Do not use a missing year as proof of a genuine zero-mile year; show an honest empty/limited-data state as appropriate.
5. Share one calendar-month X-axis across years, preferably by true month/day alignment rather than naive day-of-year offsets that shift March onward in leap years. Handle Feb 29 and year rollover explicitly.
6. Use a reasonably bounded daily series (maximum 366 dates per year) or similarly small representation. Do not recalculate raw FIT streams or fetch Strava on dashboard render. Reuse existing activity-history/presentation data; no separate historical indexing service or additional charting dependency.

### 5.3 Visual and interaction

1. Preserve the approved Home card design: **prominent blue current-year line**, medium-gray previous-year line, lighter-blue two-years-ago line; concise legend labeling each year.
2. Use **numeric months 1 through 12**, readable at the existing card width; subtle mileage Y-axis and grid.
3. Label the current-year last actual value near its endpoint where legible. Use actual data, not mockup values.
4. Hover/keyboard focus details are desirable if supported reasonably by the accepted Home chart pattern: display the actual calendar-date context and available cumulative mileage without implying unavailable data is zero. Preserve accessibility and chart descriptions.
5. No horizontal annual goal line, no goal progress bar, no separate Annual target line, no old target-pace/behind-calendar-pace block.
6. **The Mileage by Year card must not exceed the height of Mileage Progress at the same desktop bottom-row layout.** Keep summary and chart compact within that constraint; do not increase both cards to hide a taller new design. At tablet/mobile widths, preserve readable stacking, no clipping or horizontal overflow and functional Settings navigation.
7. All other Home cards, performance/training-state results, full pages, sync behavior and visible source explanation should remain unchanged.

## 6. Explicit non-goals

- No goal model/schema migrations, generic goal engine, target defaults or changes to accepted P3-01 eligibility/units.
- No changes to Training State, Performance, Plan, FTP, source reconstruction or ride import/sync logic.
- No background jobs, new data pipeline, new chart framework, caching layer or persistent aggregates without measured need.
- No broad Home restyle, production deployment, live OAuth/API requests or personal source-data commits.
- No hardcoded 2026/2025/2024, 2,200, 1,651.9, 548.1, 55, curve shapes or mockup graphs.

## 7. Inputs and local-data expectations

Use current accepted RideWorks Home code, local historical summaries already available to the application, accepted source-selection logic and synthetic fixtures. The Owner privately supplies the approved mockup; do not publish/commit the original screenshot, and do not require personal activity archives as part of the GitHub handoff. Document coverage limitations with synthetic fixtures. Current source data and Year/goal configuration remain Owner-controlled and unchanged.

## 8. Required outputs

- Focused Home dashboard summary/series implementation, card template/SVG/CSS and lightweight interaction updates as needed.
- Focused regression tests and synthetic test data for aggregation, source/date semantics, three-year alignment, missing data, weekly ceiling, goal/no-goal/year-end states, correct layout and behavior preservation.
- Privacy-safe reports/HOME-UI-03/implementation.md with modified files, source/algorithm reuse, commands/results, chart/render verification, limitation notes and evidence references. Use synthetic screenshots only.
- TASKS.md/STATUS.md lifecycle updates, focused commits, pushed task branch and PR for Analyst review.

## 9. Verification

1. Run relevant dashboard/unit tests and full appropriate regression suite; do not report passes not actually run.
2. Independently verify three-year cumulative totals from synthetic dated activities, year change, Feb 29, late/no rides, date-with-unknown-timezone, distance fallback, missing distance, missing date, future activity and noncycling exclusion.
3. Verify YTD/remaining amounts match current Home/Settings accepted calculations. Required weekly number must be ceil(unrounded existing needed-weekly); verify 55.0 -> 55, 55.1 -> 56, reached goal, absent goal, last-day unmet and leap year.
4. Browser-check 1440/1024 desktop and 768/390/320 CSS px using synthetic data. At desktop bottom row verify computed Mileage by Year height does **not exceed** Mileage Progress, with readable months and legend, no overlap/overflow, correct data endpoints and honest limited-data states.
5. Confirm visually against the Owner-provided mockup, and check focus/tooltip/accessibility. Confirm unchanged Recent Activities, Mileage Progress weekly actual/required chart, top Training State and 20-minute Performance cards, relevant navigation and full pages. No production/source mutation.

## 10. Acceptance criteria

- Home shows **Mileage by Year** in place of **Annual Mileage Goal**, no taller than adjacent Mileage Progress at desktop.
- Three actual cumulative lines for current and two prior years, numeric month ticks, readable compact legend; current line ends at as-of, no synthetic projections, leap alignment works.
- Current YTD, remaining distance and dynamic **whole-number ceiling** needed/week displayed; calculations agree with accepted goal/month/week semantics, and completion/absent-target/year-end cases are honest.
- No goal line/bar or retired explanatory block; other Home parts and all accepted services remain intact.
- Focused and regression tests and privacy-safe browser evidence supplied, task PR ready for Analyst review, Owner approves the running presentation before final acceptance.

## 11. Mandatory stop/report conditions

In addition to AGENTS.md mandatory stops, stop and report if existing summary data cannot support the three historical lines without a material new data-source/eligibility decision; goal/needed-weekly rules conflict materially with proposed text; historical-coverage ambiguity would materially mislead the graph; existing layout cannot honor the height/legibility constraint without a product-design choice; or the private mockup conflicts materially with explicit requirements. Do not invent values, weaken evidence rules or broaden scope. Routine implementation or styling defects may be fixed within scope.
