# HOME-UI-01 — Dashboard visual refinement

**Status:** Pending Dex implementation; Owner requested the same cleaner visual treatment for Home immediately after accepting AR-UI-01 on 2026-10-11.
**Task:** A **presentation-focused** redesign of the existing Home/dashboard, not a new dashboard data model or adaptive training feature.
**Reference:** [Proposed responsive HTML mockup](../mockups/home-dashboard-ui-concept.html). It is an Analyst-authored starting layout based on Owner-approved Activity Review style; individual card-placement details are proposals for Owner's eventual running-app review, not additional hard user decisions.

## 1. Requirements Used

- Owner direction: **“This looks good. Now I'd like to do the same thing with the dashboard.”** Applies the clean, compact and readable Activity Review visual direction to **Home**.
- Accepted AR-UI-01 [implementation evidence](../../reports/AR-UI-01/implementation.md) and [design](../design/AR-UI-01-activity-review-redesign.md): scoped RideWorks palette, card radius/spacing, compact page header, readable charts, consistent section organization, truthful source captions and mobile behavior.
- Existing approved [Dashboard PNG](../mockups/dashboard.png) as product-history context; [HTML Home concept](../mockups/home-dashboard-ui-concept.html) as suggested new visual reference. Do **not** copy its fabricated figures or synthetic curves.
- [Product requirements](../PRODUCT_REQUIREMENTS.md), accepted Home/Performance/Training State/Plan models, current `rideworks/home.py`, `rideworks/static/home.js`, `rideworks/static/style.css`, `rideworks/planning_page.py`, and relevant Home/browser tests.
- [AGENTS.md](../../AGENTS.md) controls task/branch lifecycle, sources, privacy and review gates.

## 2. Execution Control

**Allowed Invocation: `/TASK or /AUTOTASK`.**

**Gate 0 — Owner direction resolved:** Restyle **Home** to have the same compact, considered look-and-feel as the approved Activity Review, eliminating wasted space and making recommendations and recent rides easier to find. The mockup supplies an implementation proposal for detailed arrangement. It is not advance Owner acceptance of every mockup detail.

**HARD — Analyst Gate 1:** Implement and test the real dashboard; review production markup/styles, behavior preserved, responsive design, screenshots, chart interactions and absence of unrelated-page style changes. Stop with draft PR and evidence.

**HARD — Owner Gate 2:** Owner reviews the **running real Home page** for visual usefulness; no merge or task done before this gate. Do not restyle other pages or start deferred Phase 6.

## 3. What to implement

- **Compact Home header:** Home title, concise descriptive subtitle and source-accurate last-sync/status link; use modest vertical padding, no huge gradient/banner or duplicate controls. Mobile must display readable sync status.
- **Above-the-fold priority:** the existing **Next Recommended Ride** should be prominent and easy to scan, with correct actual date, duration/power and explanation from the **current Plan engine**, not an invented recommendation. Keep `View Plan` working. If today was ridden already, the card must still name the **next future ride**, honoring accepted P5-01 semantics.
- **Four compact quick facts:** preserve supported **This Week** and **Last 7 Days** mileage and both current 42-day best and latest eligible 20-minute effort. The mockup shows a compact stat matrix instead of three oversized top cards; make responsive layout work with unavailable/long values and source links. Do not reinterpret current best vs latest qualifying effort as equivalent.
- **Recent Activities** remains a readable linked list/table with actual source-supported dates, ride title/type, distance, duration and average power. Avoid unnecessary horizontal scrolling at 320px; use labelled stacked ride rows/cards for small screens. No hardcoded race labels/inferring training type from illustrative names.
- **Training State and Performance** appear as legible companion sections close enough to be useful, without taking priority over ride advice/history. Preserve existing Fitness/Fatigue/Form reporting, form-at-start-of-day meaning and source limitations. The small Training State sparkline in the HTML is **illustrative only and not yet an accepted Home feature**: either use existing actual supported data with proper provenance or retain the current text metrics rather than fabricate points. Preserve actual 20-minute performance chart/links, no new smoothing/resampling.
- **Mileage Progress and annual goal:** keep interactive accepted rolling 12-week bars + needed-average line, current-week outline/partial-week explanation, YTD value, annual target, percent, remaining and needed pace, edit-goal link, weekly detail and evidence. The mockup's split chart/goal layout is preferred where it helps readability. No modification to mileage totals/calendar logic or target calculation. Keep Year-to-Date and source-evidence caveats inspectable without exposing them as large default paragraphs.
- **Recent context & diagnostics:** retain previous-six-week best-20 comparison and Home diagnostics in concise collapsible/secondary sections. Never drop source explanations, as-of timezone semantics, unsupported data messages or evidence tables.
- **Maintainable styling:** Follow the implemented Activity Review palette (#132b48 ink, #2563eb primary, #0c9c92 teal, #f4f7fb canvas, #e0e8f1 stroke), restrained 14px cards, readable type and controlled 18–24px padding. Scope Home style under a class such as `.home-redesign` or additive Home-only selectors. Reuse shared design variables if harmless; do not globally change Activity Review, Activities list, Performance, Plan, or Training State. Keep the real application shell/navigation.
- **No numerical/data changes.** Preserve RideWorks charts and their real interaction, Plan recommendation, evidence provenance, dates, source priority, goal setting, training stress, historical FTP and activity results. Mockup controls are only illustrative in-page references and must become genuine links or be omitted.

## 4. Required verification

1. **Visual:** actual Home at desktop 1440, laptop 1024, tablet 768, phone 390 and **320 CSS px**, compared with [mockup](../mockups/home-dashboard-ui-concept.html), including panel sizes, viewport fold, readable KPI hierarchy and no overflow. Annotate deliberate deviations and inspect real screenshots privately. Avoid a large wasted blank column or oversized recommendation when text is short.
2. **Behavior:** real Next Recommended Ride matches Plan on same clock/sync including after a completed ride, before a ride and when source classification is uncertain. No false recommendation from mockup; valid View Plan, Activity, Performance, Training State, Settings/Edit Goal routes. Preserve current source-qualification/uncertainty text and accessibility.
3. **Dashboard values:** compare all current computed Home values/data before and after with fixed timezone/clock and source snapshots: This Week, Last 7, 42-day best, latest eligible 20-minute, chart points, current/partial week, YTD percent/goal pace, linked activities, Training State and current Plan. No changed backend formulas merely for layout.
4. **Charts:** actual 12-week mileage bars/needed line, performance series, pointer/keyboard/touch, legend/screen-reader labels; honest empty or partial datasets. A new Training State mini chart requires only real accepted series and explicit eligibility/provenance, or should be omitted.
5. **Responsive/accessibility:** 320px width no overflow, useful mobile recent ride cards, 4 KPIs wrapping, correct heading/landmark order, labels and visible focus, reduced motion where relevant.
6. **Regressions/preservation:** full Python and browser suites, Activity Review compact header/PC-01/Plan/Performance/Training State visuals and calculations unchanged, no original file/store mutation, FTP/reference preservation. Reuse existing test fixtures and sanitization, no private titles/paths/screenshots in public branch.

## 5. Deliverables and gates

Implement as one bounded task and push a **draft PR** with source-neutral `reports/HOME-UI-01/implementation.md` and synthetic screenshots only if necessary; keep private ride captures local. Update `TASKS.md` to in_progress and `STATUS.md` as lifecycle requires. Stop at **HARD — Analyst Gate 1** with before/after Home captures, actual source/value parity and tests. Then Owner sees running dashboard at **HARD — Owner Gate 2**; no premature merge or start of further-page refinements. Unapproved analyses/extra widget functionality are not part of this visual task.

## 6. Stop/report only for material policy conflicts

Stop if proposed layout requires dropping accepted evidence, changing calculation/source policies, materially altering Plan logic, replacing honest unavailable states with estimated data, or breaking accepted pages. Normal CSS/layout/browser defects are routine fixes inside this task, not another research gate. Phase 6 remains deferred.

**Start:** Explicit `/TASK HOME-UI-01` or `/AUTOTASK HOME-UI-01` after Dex refreshes `main`.

## 7. Owner running-Home review: top-card order, blue edges and final style boundary (2026-10-11)

**Status: REFINEMENTS REQUIRED WITHIN EXISTING PR #32.** The Owner inspected the running Home and said **"Home now looks much nicer"**, then requested two small changes: **swap the top two cards** and consider a **blue left edge on all Home cards**. The Owner also explicitly said **"we should not carry the look we've given to the activities and home page to the other pages of the app."** This latest statement **supersedes** earlier exploratory proposals to roll the Home/Activity visual system out to Performance, Training State, Plan, Settings or the Activities listing. Treat this as an explicit *scope boundary* rather than assuming broader adoption. This is feedback on the existing implementation, **not** final Gate 2 acceptance until the refinements are viewed.

### 7.1 Specific changes

1. **Swap the top-level lead cards** at desktop/tablet: the four-metric quick-facts **summary is first/left** and the shared **Next Recommended Ride is second/right**. Update actual DOM/keyboard reading order as well as visual order, not only `order:` CSS. Where responsive layout stacks, the four metrics appear **above** the next ride. Preserve content/links and Plan-parity semantics. Allow the right next-ride card slightly more width where helpful for variable-length explanations; ensure both cards line up comfortably when one is taller or the recommendation has completed-today context.
2. **Blue left edges:** try a **restrained, consistent 3px left accent** on the *main Home cards only*: the four-fact summary container, Next Recommended Ride, Recent Activities, Training State, 20-minute Performance, Mileage Progress, Annual Mileage Goal and the supporting-details outer card. Retain the Next Recommended Ride's slightly stronger **4px** blue edge. Use a modest blue matching the current RideWorks palette rather than a strong saturated stripe that dominates every card. **Do not put an additional blue border on each individual fact, nested insight, chart region, `details` disclosure, or component already inside a main card.** Maintain rounded corners and padding, avoid visually double-thick borders. If every card accented equally looks too repetitive, show the before/after and recommend the minimally accented alternative, but try the Owner-requested treatment rather than declining without demonstration.
3. **Keep everything else:** preserve the current Home card hierarchy, metrics, existing current next-ride sourcing, links, Training State/Performance charts, weekly mileage, annual goal, supporting details, mobile usability, full source/FTP/provenance and calculation rules. No changes to another page's layout or visual styling.

The [editable HTML Home reference](../mockups/home-dashboard-ui-concept.html) has been updated to show **quick facts left / next ride right** and thin blue left edges. All its text, number and chart traces remain illustrative. Actual UI source and accepted models remain authoritative.

### 7.2 Verification and handoff

- Compare pre/post Home at 1440/1024/768/390/**320px**, including long recommendation text, a completed ride today, short/missing data, and a long name/number in quick facts. Check actual DOM order, focus sequence, no chart/table overlap, no overflow, accessible contrast and 3px/4px border color/shape. Check that there is no accent double-up inside main cards.
- Assert **all other pages unchanged** visually (Activity Review compact header, Activities listing, Performance, Plan, Training State, Settings). No global border rules outside `.home-redesign`, and **do not start a future page-by-page restyle**; this is the Owner's latest explicit design decision.
- Rerun source-preservation and ordinary Python/Chromium regressions; use actual data and local screenshots to verify. Retain the accepted source/method model checks. Update the existing `reports/HOME-UI-01/` implementation report and draft PR #32.
- **Stop again at HARD — Analyst Gate 1** with new screenshots/verification; then show the refined running Home to the Owner for **HARD — Owner Gate 2**. Do not merge or mark done based on the prior positive statement; the blue accents and swap must be seen first.

**Execution:** Continue the existing task on `task/home-ui-01-dashboard` after refreshing its current branch, using permitted `/TASK HOME-UI-01` or `/AUTOTASK HOME-UI-01`. Do not open a duplicate task or PR.
