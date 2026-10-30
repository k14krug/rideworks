# HOME-UI-04 — Home top-row Training Overview redesign

**Status:** pending — Owner approved the visual direction on 2026-10-30; final private mockup will be supplied directly to Dex at invocation.
**Scope:** Replace only the Home top-left four-fact summary with a three-metric Training Overview; preserve the adjacent Next Recommended Ride and the accepted lower Home dashboard.

## 1. Purpose

Make the Home top row answer two questions immediately: **Where do I stand today?** and **What should I ride next?** Replace the current four-cell summary's redundant 20-minute performance facts with Fitness (42-day) and its 7-day change, current recorded FTP, and last-7-day cycling mileage with an appropriate prior-7-day comparison.

The completed Training State and 20-minute Performance charts below already supply longitudinal context. Do not reproduce either chart in the new card.

## 2. Background and Owner decision

On 2026-10-30, the Owner reviewed iterative private Home mockups and explicitly selected the last three-column Training Overview layout, without a separate “Latest Ride” or other best-20 summary in the top card. They will send the selected visual mockup privately to Dex together with the invocation.

**The private mockup is a visual reference only.** All numbers, arrows, comparison amounts and recommendations in it (for example 23.9, 185 W, 29.7 mi, +2 W, 17%, and an Easy ride) are illustrative. Render real current RideWorks values and existing accepted recommendations; do not hardcode example figures or infer missing history. Never commit the private image or rider-identifiable data.

This task specifically supersedes HOME-UI-02's instruction to preserve the previous four quick-fact values **in the top summary only**. It does not change the already accepted six-month Fitness chart, rolling 42-day best 20-minute chart, underlying Performance rules, or other Home cards.

The current mainline Home implementation is in `rideworks/home.py`; mileage and Performance snapshots in `rideworks/dashboard.py`; Fitness and 7-day changes in `rideworks/training_state.py`; dated FTP in `rideworks/ftp_history.py` and `training_state.ftp_on`; shared Next Recommended Ride in `rideworks/planning_page.py`; relevant scoped styles in `rideworks/static/style.css`. Verify interfaces from the refreshed repository before changing code.

## 3. Requirements Used

- `AGENTS.md`, `TASKS.md`, `STATUS.md` and `docs/PRODUCT_REQUIREMENTS.md` — scope, source fidelity, task lifecycle, data restrictions, and review gates.
- Accepted HOME-UI-01, HOME-UI-02 and HOME-UI-03 design/implementation: existing white/blue/navy card treatment, desktop Home composition, six-month Fitness trend, 12-month rolling best-20 trend, and mileage cards.
- Accepted dated FTP behavior in FTP-01 and FTP-02; manual effective-dated setting is **not** an automatically derived FTP test result.
- Accepted Training State source eligibility and `changes7` definition; Fitness is a model of cycling training load, **not** a direct readiness/recovery score.
- Owner's final private top-row mockup, supplied directly at invocation. In any visual/data conflict, accurate accepted data behavior takes priority over illustrative mockup copy.

## 4. Execution Control

**Allowed Invocation: `/TASK or /AUTOTASK`.**

This is one bounded presentation implementation. Dex must refresh Git and inspect open branches/PRs, `TASKS.md`, `STATUS.md`, this JIT and current accepted code before implementation. **RE-03 has an open draft PR #54 as this brief is authored; do not displace any in-progress task.** Start HOME-UI-04 only when current work is finished/cleared or the Owner explicitly reprioritizes it under repository rules.

After focused implementation and verification, open a **draft PR** and stop at **HARD — Analyst** technical review, then **HARD — Owner** visual acceptance of the running UI. No autonomous merge or deployment authorization.

## 5. Required UI and behavior

### 5.1 Top-left: Training Overview

Replace the current `home-summary` four-fact grid with **one compact panel** titled **Training Overview**, containing exactly these three clearly separated metric groups:

1. **Training State** — label the displayed number **Fitness (42-day)**. Show the latest supported daily Fitness from the accepted Training State service, at the same as-of/local-day context as the existing Home chart. Directly below show the **signed 7-day change in Fitness points** from the accepted daily `changes7['fitness']` evidence, labeled “vs. 7 days ago.” It is not a change in percentage. For insufficient history/unavailable state, use honest unavailable text. A decline is not necessarily bad and an increase is not necessarily readiness; arrows/colors must not claim otherwise. Link/accessible route to `/training-state` where useful.
2. **FTP** — show the currently effective **recorded, date-effective FTP** in watts from the accepted FTP history, resolved for the proper athlete/calendar date using existing timeline logic. The image's FTP value is not authoritative. Optionally show an absolute watt change **vs. the preceding recorded FTP entry** if one exists; label that basis unambiguously rather than implying “last 7 days” or an automatically measured improvement. If no preceding entry or no current FTP exists, omit the change or use an honest unavailable display; never fabricate 0 or estimated FTP. Include **View FTP History** linking to the existing `/performance/ftp` route.
3. **Last 7 Days** — use the existing accepted seven-calendar-day cycling distance aggregate. Show actual miles and a compact comparison with the **preceding seven days** using the already calculated data. Prefer a signed difference in **miles** (or a genuinely computed percentage when well-defined) over the mockup's illustrative percentage; when prior-period mileage is zero/missing, avoid undefined percentages. Preserve source/date/timezone and missing-distance rules, and do not equate mileage with training stress.

No “This Week”, current-42-day-best 20-minute power, “Latest eligible 20-minute ride”, “Latest Ride” or 20-minute result in this top panel. These concepts remain available in the established dashboard detail and Performance view as appropriate.

Keep the summary compact and at approximately the height of the Next Recommended Ride panel, subject to real content; no additional charts, sparkline, gauge, stacked subcards, empty decorative space, or extra metrics. Avoid duplicate charts from the Training State and 20-minute Performance cards below.

### 5.2 Top-right: Next Recommended Ride

Retain the **existing dynamic** Next Recommended Ride component and all meaningful behavior: recommendation date, category, duration, power target, explanation, provisional/uncertain-history status, link to Plan, and completed-today handling. Do **not** replace dynamic text with mockup wording or change the planning algorithm.

Adjust only scoped layout/spacing as necessary to complement the new left panel. The Owner's selected mockup shows a left Training Overview around 60% of the combined top-card area and a right recommendation around 40%; adapt proportion responsively rather than hardcode pixel widths.

### 5.3 Visual fit and responsive behavior

Match the **currently accepted RideWorks Home** presentation: white panels, restrained blue left rule, navy headings, modest blue icons, thin dividers, 14px rounded corners, subtle shadow, compact metadata and consistent typography. Three evenly organized metric groups; large primary values; small readable period/comparison captions. Do not create a new visual system or introduce large decorative imagery.

Use actual supplied private mockup as the primary **visual** comparator for this top row, but preserve accessible and truthful text if its placeholder labels/values conflict with live data.

At desktop, keep the two top cards side by side and visually balanced; at narrower widths, stack/reflow without clipped values or horizontal overflow (including at 390px and 320px). Preserve keyboard and screen-reader access to links and contextual labels. Prefer scoped CSS and current HTML patterns; no new CSS/JS framework.

## 6. Explicit non-goals

- No change to Training State/Fitness/Fatigue/Form modeling, 7-day delta semantics, stress eligibility, FTP history or automatic FTP inference.
- No change to Performance's source/eligibility definitions or the existing 20-minute Performance graph.
- No change to Plan logic, recommendations, provisional-status semantics, recent ride classifications/Relative Effort, mileage/annual goal computations, sync, import, persistence, or production Store.
- No redesign of Recent Activities, Training State, 20-minute Performance, Mileage Progress, Mileage by Year, or other pages.
- No schema changes, migrations, external API calls, new chart library, speculative metrics, or deployment.
- No hardcoded personal values, mockup placeholder numbers, or committed private images.

## 7. Inputs and local-data expectations

Implement using the **actual current** Home/Training State/FTP/mileage services on refreshed `main`. `training_state()['days']` already includes daily Fitness and `changes7`; use the final supported as-of row, do not invent a new scoring rule. FTP settings are manually date-effective; consult the accepted FTP timeline and resolution rather than deriving FTP from best-20 watts. `dashboard()` already supplies `last7` and `prior7` totals. Prefer reusing the existing Training State result used for the lower chart, or otherwise keep any added calculation bounded; do not duplicate full costly analysis unnecessarily.

Use synthetic fixtures for reproducible tests. Private rider data stays local. If the private mockup isn't attached, ask the Owner for it **before** final visual verification; do not commit it.

## 8. Required outputs

- A focused Home top-row implementation plus minimal corresponding scoped styles and tests.
- A privacy-safe `reports/HOME-UI-04/implementation.md` with modified files, source contracts reused, calculated/unknown display cases, commands and verification results, and known limitations.
- Synthetic before/after desktop and mobile screenshot evidence in the report or appropriate privacy-safe artifacts; no personal ride values committed.
- Updated task/STATUS lifecycle state, focused commits, pushed task branch, **draft PR** for Analyst review.

## 9. Verification

1. Focused Python tests and relevant regressions must show Fitness display matches the accepted final-day Fitness figure; the 7-day difference matches existing `changes7['fitness']`, with valid positive, negative, zero, missing/early-history and stale/as-of cases.
2. FTP resolution must use current effective dated entry, not 95% of best-20; verify no-history, one-entry, multiple-entry, future-effective entry and exact-date-boundary cases. Check any displayed comparison against the **previous entry**, not a guessed recent baseline.
3. Verify last-seven-day mileage and previous-seven-day comparison match accepted Home totals across year/week boundaries, unavailable cases, and positive/zero prior-period behavior.
4. Verify that no top-panel 20-minute summaries remain, while the existing 20-minute Performance card and detail links/series are unaltered. Preserve the Training State six-month chart, recent activities, both mileage cards and source diagnostics.
5. Verify the Next Recommended Ride still uses Plan's actual dynamic recommendation, reason, provisional warning and controls, with real lifecycle and completed-today examples.
6. Inspect synthetic rendered Home at approximately **1440, 1024, 768, 390, 320** CSS px, comparing **top-row proportions, spacing and typography** to the private mockup. Verify no overflow/overlap, readable metric labels and deltas, working links and accessible text. Test where results are unavailable or long.
7. Run required regression suite and capture commands/results; avoid changing source eligibility, source provenance, persisted data or production.

## 10. Acceptance criteria

- Home top-left is a single compact **Training Overview** card with exactly Training State Fitness + 7-day change, current recorded FTP (history link; properly labeled prior-entry change when available), and Last 7 Days mileage + valid prior-week comparison.
- Top-right remains the existing live Next Recommended Ride; its full semantics, dynamic values and Plan link survive.
- No top-row 20-minute power metric or redundant Training State chart. The existing lower Training State/Performance chart cards and rest of Home are visually and numerically preserved.
- Source/absence rules are accurate; no sample data, false readiness claim, undefined percentage, fabricated FTP/delta or private screenshot committed.
- Visually matches the Owner-supplied reference within existing RideWorks styling, verified responsively and accepted by Owner after Analyst review.
- No algorithm/database changes, no unrelated refactors, no production/deployment changes.

## 11. Stop and report

Stop for Analyst/Owner direction if task selection conflicts with RE-03/current in-progress work, if accepted data interfaces do not support the specified values without an algorithm change, if the private mockup materially conflicts with data/UX requirements, if production/private data would have to be committed, or if required review gates are reached. Repair routine UI/test defects within scope; do not silently expand scope.
