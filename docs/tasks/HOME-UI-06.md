# HOME-UI-06 — Add Race Avg W to Home Recent Activities

**Status:** Pending implementation, Analyst-authored 2026-11-08.  
**Issue:** [#62](https://github.com/k14krug/rideworks/issues/62).  
**Scope:** One narrowly scoped Home dashboard table improvement. No race importer changes or data migrations.

## 1. Purpose and Owner decision

The Owner reviewed production screenshots of **Home → Recent Activities** alongside the **Activities** table and approved displaying **Race Avg W** immediately to the right of the existing **Avg Pwr** column. The Owner's visual assessment is that the desktop Recent Activities table has space in its last three columns (Distance, Duration, Avg Pwr) that can be reclaimed for one additional narrow numeric column.

**Owner decision:** Keep the Recent Activities card's overall width, height, layout position, currently visible row density, and usual row count; tighten those existing columns rather than expand the card. Race Avg W should show race-specific, Zwift-reported watts, not file-backed/Activity average power. On smaller screens, maintain sensible responsive access to the values.

The shared production screenshots are *private visual references* supplied in conversation, not repository artifacts. Never commit screenshots, personal ride names or real activity records.

## 2. Requirements and actual source boundaries

- [Product requirements](../PRODUCT_REQUIREMENTS.md): PR-001 (single rider), PR-002 (product usefulness), PR-004/005/006 (source/provenance), PR-009 (independent competing evidence), PR-012 (missing means missing).
- [AGENTS.md](../../AGENTS.md): AI Analyst JIT, explicit invocation, task/PR lifecycle, HARD review gates, and safe repository work.
- Accepted [RACE-02](RACE-02.md), [PR #61](https://github.com/k14krug/rideworks/pull/61): `race_results` stores only **confirmed current** race-result attachments, including `values_json.avg_watts`; removed results have a retained audit history but no active row.
- Accepted Home and its activity avg-power definition ([P3-01](P3-01.md), [HOME-UI-02](HOME-UI-02.md), [HOME-UI-05](HOME-UI-05.md), [RE-03](RE-03.md)).
- Current implementation on merged `main`: `rideworks/home.py` builds Recent Activities from `dashboard(store, zone.key)['recent']`; `rideworks/dashboard.py` bounds that list to 24 and provides independent `average_power`; `rideworks/static/style.css` controls Home table columns and responsive view, including an existing `@media (max-width: 740px)` stacked table treatment. `tests/test_rideworks_dashboard.py` and browser scripts already verify the Home surface.
- Existing Activities table already displays Activity avg power and Race avg W separately. Reuse its *meaning* and active-link semantics, not unnecessary styling or its entire query.

## 3. Execution Control

**Allowed Invocation: `/TASK or /AUTOTASK`.**

- This JIT is written and committed by the AI Analyst *before* Dex starts.
- Dex must first safely refresh `origin` per `AGENTS.md`, verify a clean primary checkout, current `main`, pending HOME-UI-06 status, and no competing active task; then create a normal task branch and **draft PR**. Use the existing primary RideWorks checkout; do not create a separate Git worktree.
- **HARD — Analyst Gate 1:** stop after implementation, tests, source-neutral verification, and draft PR for code/data/performance/layout review.
- **HARD — Owner Gate 2:** after Analyst acceptance, Owner reviews the running real Home UI at desktop and smaller widths. No merge or production release before Owner acceptance.
- **Production deployment:** separate explicit Owner approval following acceptance; not authorized by this task or by synthetic test success. No production data changes or privileged access by Dex.

## 4. Implementation requirements

### Data and rendering

1. Add a **Race Avg W** column after **Avg Pwr** in the **Home → Recent Activities** table only. Existing activity average power remains displayed, with the same source precedence, formatting and meaning as now.
2. For each recent Activity, read `values_json.avg_watts` from its **current active** `race_results` record matched by `activity_id`. Prefer a single small SQL query for the 24-or-fewer recent Activity IDs; equivalent bounded lookup is acceptable. No N+1 query loop, full-history race scan, new API calls, new cache, schema change or duplicate race data model.
3. Display a known value as `169 W` (integer source-supplied value), including a legitimate `0 W` when present. Display `—` (or consistent neutral missing indicator) when the Activity has **no active race result** or the race result's watts are null/unavailable. No fallback to Activity avg power, Strava API watts, FIT/session summary, predicted watts or Racing Score. Do not read previously removed result history as current evidence.
4. Preserve links, Strava Relative Effort presentation, date/time, title, Distance, Duration, Avg Pwr, row order, underlying recent cohort, selected timezone, source explanation and other Home cards. The direct Home-to-Activity link must remain functional. Do not quietly reinterpret or round any power data.
5. Keep all new read logic localized to the existing Home/dashboard presentation boundary; do not alter shared Activity analysis/performance/power models. Follow existing escaping and source display conventions. User-facing data attributes/labels should distinguish `Race Avg W` from `Avg Pwr` for responsive and accessibility cases.

### Layout

1. Keep the accepted desktop **Recent Activities** card width/height and position unchanged, and maintain the currently visible row count at a comparable desktop viewport; the data list remains bounded as before.
2. Reclaim width from the Distance, Duration and Avg Pwr columns (and modestly the title if truly needed). Allocate roughly **65–75px** for a compact, right-aligned `Race Avg W` column; use tabular numerals. Treat these widths as visual starting points, not mandatory pixel-perfect guesses.
3. Avoid illegible font reduction, clipped headers, overlapping numbers, page-wide horizontal overflow, premature truncation of most ride titles, and unexpected vertical row growth. Do not enlarge Home's companion chart cards or move the overall layout to hide a size increase.
4. Preserve or deliberately adjust the **existing responsive Home table** rules, particularly `@media(max-width:740px)` and legacy `@media(max-width:620px)` column-index selectors. Ensure the seventh field is readable and unambiguously labeled on tablet/mobile; choose compact stacked rows or contained horizontal scrolling as appropriate based on the *running* layout, not CSS guesswork. Avoid global CSS changes.

## 5. Verification and output

- Add focused synthetic regression coverage: a linked race result showing `169 W` beside a differing Activity average; no active link showing `—`; an explicitly removed/unlinked race showing `—`; null race watts showing `—`; legitimate `0 W` showing `0 W`. Check fields by Activity ID rather than guessed row position.
- Confirm the Home source lookup is bounded (one query for recent IDs or equivalent), with no history-wide or per-row queries. Check no changes to Activities's existing race fields and no unintended power-metric changes. Confirm existing empty/undated/recent sorting and output escaping.
- Run the full relevant Python suite and focused Home/browser checks. Visually inspect at representative widths, including **1440, 1280, 1100, 768, 740, 620, 390 and 320px** (adjust breakpoint coverage as needed), checking both race and nonrace rows and the existing card height/row density. Use synthetic data only.
- Provide before/after layout evidence (dimensions/row count) at a consistent desktop viewport, source and query notes, exact tests/results and limitations in `reports/HOME-UI-06/implementation.md`. Synthetic preview screenshots may remain ignored locally; do not commit private production images.
- Open a draft PR and STOP for **HARD — Analyst Gate 1**, explicitly noting any visual concerns that require Owner judgment.

## 6. Explicit non-goals

No adjustments to Race Results importer, race matching, source association or removal behavior; no new Racing Score column on Home; no chart/layout redesign; no new data migrations; no automatic sync, upload or paid API calls; no training-state or power calculation changes; no production deployments or production database access.

## 7. Stop-and-report conditions

Stop for Analyst decision if a narrow active-result lookup is unsafe, the approved table cannot fit without harming readability or current visible row count, mobile handling requires a bigger Home redesign, an unrelated schema/data problem arises, or implementing this would conflict with accepted source and history semantics. Do not silently trade off the card size, source distinction or Owner-accepted UI to make a test pass.
