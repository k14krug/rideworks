# HOME-UI-05 — Compact Training Overview and 90-day Power Bests

**Status:** pending — Analyst JIT, 2026-10-30.
**Visual reference:** Owner-approved private mockup supplied to Dex at invocation; never commit screenshot or rider values.
**Purpose:** Replace the three oversized Training Overview metric columns with one compact two-column information display. Add four exact 90-day Power Bests from the existing cached Power Curve. Keep the desktop card no taller than current HOME-UI-04.

## Background and authority
HOME-UI-04 / PR #55 has merged. This is a **new follow-up**, not an instruction to reopen the accepted lower dashboard. This task supersedes HOME-UI-04's requirement for *exactly three* summary groups and its prohibition on a 20-minute value in the top summary. The lower rolling **42-day** 20-minute Performance chart remains unchanged and distinct from the new rolling **90-day** best.

## Requirements Used
- `AGENTS.md`, `TASKS.md`, `STATUS.md`, `docs/PRODUCT_REQUIREMENTS.md`, especially source/provenance and reproducible metrics.
- Merged HOME-UI-01/02/03/04 JITs and accepted Home styling.
- Current `rideworks/home.py`, `rideworks/static/style.css`, `dashboard.py`, Training State and FTP history.
- `rideworks/power_curve.py` (`duration_grid`, `signature`, `curve_history`, `envelope`, `METHOD`, `POLICY`), `rideworks/store.py` and `rideworks/history.py`.

## Execution Control
**Allowed Invocation: `/TASK or /AUTOTASK`.** One bounded implementation. Fetch origin and synchronize with `main` before branching. Confirm no other task in progress; read current code, tests and JITs. Stop at **HARD — Analyst** technical/performance review, followed by **HARD — Owner** actual running Home visual approval. Draft PR only until authorized. No merge or deployment.

## UI specification
Retain the outer **Training Overview** white card, blue left rule, navy heading, rounded corners and its placement beside the unchanged compact Next Recommended Ride.

**Completely replace** the existing three-column/three-tile markup. No large per-metric icons, no isolated stat blocks, no decorative giant figures, no nested cards, no graph.

Use a compact **two-column table-like** layout matching the Owner's private approved mockup:
- Left heading **CURRENT STATUS**, with three aligned label / bold value / short comparison-context rows:
  - Fitness (42-day): existing model value and signed seven-day change in **points**; working Training State link.
  - FTP: effective dated **recorded** watts and FTP History link; no inferred FTP or invented trend.
  - Last 7 days: existing accepted mileage and signed mile difference vs previous 7 days.
- Right heading **90-DAY POWER BESTS**, with four aligned duration / bold integer-watts rows: **5 seconds, 1 minute, 5 minutes, 20 minutes**. Use a concise source note or accessible title that identifies these as **qualifying observed Virtual Ride power**.
- Ordinary readable font sizes, tight row padding, restrained hairline separators; small links rather than promotional-looking calls to action.
- **Do not increase the desktop Training Overview height compared with the currently merged HOME-UI-04 for the same viewport/data.** Do not enlarge the neighbor to mask an increase; don't clip meaningful text. On small screens the sections may stack naturally, with no overflow at 390/320 px.

Preserve Next Recommended Ride, including dynamic date/target/reason/provisional warning and View Plan. **Do not add Home Completed Today**; it remains on Plan. Preserve Recent Activities, Training State chart, 20-minute Performance chart, Mileage Progress and Mileage by Year.

## Power data specification
1. Reuse accepted **Power Curve** cached per-ride profiles. Required exact anchors: **5, 60, 300, 1200 seconds**; all already supported. Use original `rounded_watts`, compare candidates by `sum_watts` with existing `envelope` tie behavior. The four maxima may come from four different rides.
2. Define rolling period **[as_of - timedelta(days=90), as_of)**, timezone-aware UTC instant; lower inclusive, upper exclusive. Use the same Home as-of instant; exclude undated/offset-unknown and future activities. Do not substitute calendar-month boundaries or activity import time.
3. Preserve existing Virtual Ride cohort and accepted Power Curve source policies: qualified actual watts/timing, native file precedence, high-resolution full-length API stream fallback, no estimated/summary watts, timer/source ambiguities remain unavailable. Outdoor power is **not** included by this task.
4. Never use stale profiles. Validate cache method and signature against **current selected source evidence**; distinguish valid zero from missing; if relevant profiles are pending/stale, disclose possible incompleteness or show unavailable/update-needed. No manufactured bests.
5. **Home must not** run `mmp`, parse FIT, rebuild/converge curves, retrieve API streams or mutate power caches. Existing sync/manual Power Curve update owns computation.
6. Avoid calling current full `curve_history(store)` on each Home request: it hydrates all activity history and validates all signatures before `envelope` filters. Implement the **simplest bounded read-only 90-day summary path** that first selects plausible in-window candidates and then hydrates/validates only those. If optional generic date filtering is added to an existing service, it must genuinely filter before expensive work and preserve all current callers. Don't create new tables, migrations, background jobs or generic analytics infrastructure. Correctly honor the selected file > API > CSV date semantics and current activity identity; don't filter by `activities.created_at`.

## Implementation and verification
- Locate the minimal reliable candidate selection using stored metadata/Power Curve rows; document how it handles file and API date precedence without overlooking competing sources. If bounded selection can't be made correct within this scope, stop for Analyst review.
- Add small read-only 90-day bests function; integrate with Home as-of and compact HTML/CSS; keep the existing Power Curve and lower Performance behavior intact.
- Synthetic tests: exact four durations and best-per-duration winner/ties; 90-day lower/upper edges, timezone and DST; same as-of instant; eligible Virtual Ride vs outdoor; missing/ambiguous/offset-unknown start; source change/stale/missing profile and partial coverage; read-only/no recalculation behavior; unchanged FTP, Fitness and mileage.
- Run focused and full Python regressions. Browser verify 1440/1024/768/390/320 px: approved mockup, actual desktop height **no larger** than HOME-UI-04 baseline, no internal mini-tiles or icons, readable rows/links, honest missingness, no overflow, Next Recommended Ride unchanged, lower cards unchanged.
- **Measure Home response performance before/after** on the same synthetic/disposable Store and fixed clock; repeated warm requests, median and p95, plus scanned/validated candidate counts. Include a many-old-activities/few-recent case proving the new path does not validate every historical source on each Home render. Investigate material regression. Never publish private rider metrics.
- Commit `reports/HOME-UI-05/implementation.md` with implementation details, evidence provenance, exact test commands/results, timing method and limitations. Use only synthetic browser screenshots and fixtures in the public repo; the Owner's mockup is private.
- Update TASKS/STATUS, focused commits, push a task branch, open **draft PR**, and stop at review gates.

## Non-goals and stops
No new model/algorithm, schema, power eligibility, outdoor power support, cache infrastructure, API calls, sync changes, Plan changes, production Store access or deployment. No hardcoded mockup values.

Stop rather than invent semantics if current source-date precedence cannot be preserved efficiently, existing cache cannot provide reliable 90-day values, substantial Home slowdown remains, or a HARD review gate is reached.
