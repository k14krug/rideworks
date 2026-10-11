# AR-UI-01 — Implement approved Activity Review redesign

**Status:** pending implementation; **Owner-approved visual concept** 2026-10-11.
**Task type:** Scoped user-interface / interaction redesign, not changes to activity evidence, analysis, source ingestion, Performance, planner or Phase 6.
**Objective:** Bring the **real** Activity Review / Ride Details view into the visual hierarchy, responsiveness and clarity approved in `docs/mockups/activity-review-ui-concept.html`, without losing any existing truthful analytical behavior.

## 1. Requirements Used and authority

- **Owner approval:** After reviewing the interactive HTML visual concept, the Owner said, **"I like it, please make it so."** This accepts the *design direction* and authorizes the next implementation task, not the future running implementation or broad other-page restyling.
- [Controlling approved design](../design/AR-UI-01-activity-review-redesign.md); [standalone HTML mockup](../mockups/activity-review-ui-concept.html); [mockup register](../mockups/README.md). HTML source is the editable reference; inspect it locally in Chromium, including desktop/mobile preview and working mock controls. Treat all mock content as synthetic.
- [Product requirements](../PRODUCT_REQUIREMENTS.md), especially Activity Review, provenance and source constraints; accepted Phase 1–5/PC-01 acceptance records and `docs/tasks/PC-01.md`; existing `rideworks/web.py`, `rideworks/static/review.js`, `rideworks/static/power_curve.js`, `rideworks/static/style.css`, and `rideworks/planning_page.py` plus tests.
- [AGENTS.md](../../AGENTS.md) governs branches, source/privacy protection, task state and gate lifecycle.

## 2. Execution Control

**Allowed Invocation: `/TASK or /AUTOTASK`.**

**Gate 0 — HARD — Owner design decision: RESOLVED.** The standalone UI concept is approved for Activity Review; its layout takes precedence over the older Activity Review PNG. Keep original data models and actual feature constraints.

**HARD — Analyst Gate 1 (required stop after implementation/test):** inspect actual source changes, real activity modes, visual desktop/mobile screenshots, semantic interaction tests and accepted behavior/output preservation. No separate SOFT gates needed for this bounded feature. Straightforward UI defects should be fixed and tested within the implementation pass; don't return for a design-policy review because a CSS selector needs adjustment.

**HARD — Owner Gate 2 (required final):** running Activity Review at real FIT, API and limited-evidence routes is shown for visual/usefulness acceptance. Do not merge or mark done on mockup approval alone. Do not start visual changes elsewhere or Phase 6 during this task.

## 3. Required implementation

### A. Page information architecture / visual layout

Build a clearer **hero** with real title, local date, activity/source type, link back to Activities, and a compact four-metric summary (time/distance/average power/average HR). When data isn't available, label it honestly. Hero actions jump to real sections; preserve original title-origin/evidence distinctions. Use a pale gradient sparingly; avoid overdecorated cards.

Provide **local section navigation** to Overview, Power & HR, Power Curve, Best Efforts, Source Evidence, in a sticky or otherwise accessible presentation. Real `href` anchors and accessible focus; avoid obscured scroll targets under the app's fixed header.

Within the page, arrange **ride time series prominently** (~350–400 CSS px on desktop; legible ~300–330 on small screens) with **concise companion Ride Summary, Workout Context and Current Next Ride** cards. No huge uniform text wall; no arbitrary need to fit the entire page above the fold. On smaller widths, stack logically.

Present PC-01 **Power Curve across a prominent full content width**, with full existing period controls, selected-duration readouts, contributor links, provenance and gap/unavailability treatment; it must not be squeezed into a narrow left column. Preserve its exact 42-day historical Activity baseline. Do not substitute generated SVG curve for the existing trusted chart. Existing 20-minute best and separate accepted previous-six-week comparison appear in a compact **Best Efforts** section, avoiding redundant hero-sized comparisons.

Put **Source Evidence & Calculations** toward the bottom as grouped semantic disclosures for FIT source, Strava summary, stream, selection, best-20/PC-01 method, timing, extraction and error/limited-source details. Everything currently exposed must remain findable and accurate, even if its default panel is collapsed. Use readable table/key-value breaks and wrap long IDs on mobile.

### B. Preserve real behavior and semantics

Treat existing **native FIT rich**, **Strava API retained-stream rich**, **metadata-only/thin**, and **outdoor/unsupported** review states as first-class. Do not invent power curves for Outdoor Ride or missing stream, invent an FTP value, infer a confirmed race from a title, or fill missing watts/HR. Retain truthful "source supplied" vs "RideWorks calculated" distinctions, as well as required missing-evidence messages.

Keep working `planning_page.py` activity classification correction/save, actual-vs-intent, current **next future ride** behavior and link to Plan. If current next ride is displayed on a historical activity, call it "Current next ride", not what was recommended on that historical date.

Retain native and Strava API chart samples, hover/focus/touch, timing readouts, gap handling, zero watts, overlays and actual source provenance. The approved HTML contains **Power/HR visibility checkboxes checked initially**; implement if feasible with contained JS modifications, testing redraw, markers and no synthetic samples; if an unavoidable implementation issue makes this material, report a narrow question rather than dropping the functionality silently. Do not alter stream or data calculations.

Preserve current PC-01 MMP caching, period selections, hover/keyboard/touch readouts, contributor links, provenance and exact evaluated-anchor semantics. Preserve Performance history, 20-minute best and its distinct prior-period logic, Training State/Plan, original files, FTP and date settings. No new source fetching/API permissions.

### C. Maintainable visual language

Use the mockup's colors/hierarchy/spacing/card radii as the **starting page-level visual language**. Prefer a narrowly scoped `.activity-review-redesign` wrapper (or comparable) and CSS variables/classes; keep existing global shell, app sidebar and routes. If needed, make *small explicitly scoped* changes to the page renderer and original JS, rather than copying the self-contained mockup's synthetic chart code into production. The new markup should be maintainable and avoid brittle string replacements where a narrow safe template restructure works; preserve existing route anchors and tests.

Document the small subset of design tokens/patterns that could later be reused across Home/Performance/Training State/Plan, **but do not apply them to other pages now**. Candidate tokens are the palette, border/radius, card padding, clear section headings, hero/stats, responsive large charts, current-context cards and source disclosure panels. Only do a global style adjustment when it is strictly required and demonstrate unaffected pages in browser checks.

## 4. Explicit non-goals

**No redesign of the Activities list** (the Owner-supplied screenshot and approved mockup are for **Ride Details**, not activity search/list), Home dashboard, Performance, Plan or Training State. No new training analytics, best-effort calculations, interval detection, classification algorithm, summary field invention, service integrations, data schema/migration, external charting framework or new font downloads. Don't convert the reference's synthetic labels into data. No Phase 6.

## 5. Required verification

1. **Visual fidelity:** Compare the running Ride Details screen against the [HTML visual reference](../mockups/activity-review-ui-concept.html) for 1440px desktop, 1024px, 768px, 390px and **320px** CSS widths. Inspect full-page captures for actual **native FIT**, **API rich** and **metadata/thin** routes (use private captures locally). Ensure big readable charts, intended visual hierarchy, no horizontal scrolling, clipping, excessive blank space or duplicate giant cards. Record deliberate differences.
2. **Interaction:** Every section-nav and breadcrumb/ride/contributor/Plan link goes to a valid route/anchor. All forms for category override and any existing planning controls submit unchanged. Charts remain functional for hover, touch and keyboard; Power/HR toggles checked by default and truly hide/show the intended series if implemented. PC-01 baseline period switching, readouts and source links remain correct. No JavaScript console errors, wrong HTML IDs, phantom buttons or inaccessible forms.
3. **Source/analysis invariants:** Independently compare fixed-clock server/source output **before/after** for summary/card values, chart raw sample payloads (FIT and API), best-20 result + recent-context, PC-01 series and chosen default prior 42 days, activity classification/intent, current next ride, original timestamps and source provenance. CSS can move sections but cannot recompute or quietly relabel values. Check historic same-ride/future exclusion and eligible/ineligible/outdoor reasons.
4. **Missing evidence:** Confirm no false watts or blank plots for an activity missing power/HR; source ambiguity, unavailable summary/stream and error states remain readable and navigable.
5. **Regression:** Full Python suite, existing real/synthetic Chromium browser smoke checks for Activity, Power Curve, Performance, Home, Plan and Training State; focused visual/keyboard/touch browser coverage. Preserve original artifacts, data source tables and approved FTP/Elevate reference contents; do not expose private store/screenshot/paths in public commits.
6. **Accessibility:** Heading structure, named sections, labels, contrast, focus, reduced motion, screen reader landmarks, 320px layout, no visually-hidden-but-unclickable actions. Mobile must actually be usable, not merely a scaled desktop screenshot.

## 6. Handoff artifacts and closeout

Dex will push a **draft AR-UI-01 PR**, code and tests, plus `reports/AR-UI-01/implementation.md` with UI fidelity notes and source-neutral preservation/check summaries. Desktop/mobile synthetic screenshots may be committed if clearly synthetic; **private real-ride screenshots and activity titles stay ignored/local**. Record accepted model equality and original-source preservation. Move task `pending -> in_progress -> ready_for_review` per `AGENTS.md`; keep `TASKS.md` `in_progress` at Gate 1.

**STOP at HARD — Analyst Gate 1** for technical/source/UI review, then show the running page at HARD — Owner Gate 2. Passing tests or HTML mockup approval is not final implementation acceptance. No merge or next-page overhaul until gates clear.

## 7. Stop/report only for material conflicts

Pause if a proposed visual change requires changing numerical calculations, losing currently inspectable provenance, fabricating absent fields, breaking source-mode layouts, altering planner intent/classification semantics, changing chart period rules or touching original files. Present a narrow proposed resolution. A responsive CSS bug, component rearrangement or small JS behavior issue is routine implementation work, **not** another research round.

**Start:** A permitted explicit `/TASK AR-UI-01` or `/AUTOTASK AR-UI-01` after refreshing `main`; use the existing approved concept and current real application code.
