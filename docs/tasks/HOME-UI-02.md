# HOME-UI-02 — Home Training State and 20-minute Performance trend cards

**Status:** pending — Analyst-authored implementation brief, 2026-10-28.
**Scope:** Focused Home presentation update following completed HOME-UI-01. Do not reopen HOME-UI-01 or OPS-03.

## 1. Purpose

Bring the Home page's Training State and 20-minute Performance cards into alignment with the Owner-approved private six-month Fitness mockup, using the existing accepted data and calculations. Make longitudinal context legible at a glance without replacing the full Training State or Performance pages.

## 2. Background

The Owner reviewed the Home mockup and explicitly selected a **six-month Fitness (42-day) trend** for the Training State card, replacing the Home card's three Fitness/Fatigue/Form numeric tiles. The same agreed mockup places a **12-month rolling 42-day best 20-minute power** card beneath it, both to the right of Recent Activities. The Owner will share the visual mockup privately with Dex. **The mockup and its personal ride details are not to be committed.**

Illustrative values shown in the mockup (Training State **25.9**, rolling best **195 W**, latest eligible ride **124 W**) are **not expected values or fixtures**. Use actual accepted RideWorks data, including honest unavailable states. The current Home and accepted HOME-UI-01 styling remain the baseline.

Dex's preliminary read-only inspection reports that `training_state()['days']` supplies Fitness history, the Performance service already distinguishes rolling best from latest eligible effort, and the existing Home SVG/CSS approach can support these changes. Verify the actual source interfaces before implementation; do not infer fields or invent new calculations.

## 3. Requirements Used

- [AGENTS.md](../../AGENTS.md): task lifecycle, privacy, evidence, Analyst review, invocation controls.
- [Product requirements](../PRODUCT_REQUIREMENTS.md): DASH-001, DASH-003, STATE-001, STATE-004, STATE-005, STATE-007; distinguish training load from performance.
- Completed [HOME-UI-01](HOME-UI-01.md): accepted Home design system, real values, responsive/accessibility and existing chart/source behavior. This task is a **new, narrow follow-up**, not a reopening of that accepted work.
- Accepted Training State and Performance services, current Home implementation and tests, including existing Fitness (42-day) and eligible 20-minute-power definitions.
- **Owner's private Home six-month Fitness mockup** supplied directly to Dex for visual comparison. This is a private visual reference, not a repository input; if unavailable, use the explicit requirements below rather than fabricate or commit the image.
- Owner's explicit current direction: six months of Fitness history, dynamically scaled Y-axis, latest-value endpoint label, no three metric tiles; preserve the 12-month rolling-best Performance distinction.

## 4. Execution Control

**Allowed Invocation: `/TASK or /AUTOTASK`.**

This is one bounded implementation unit, with no autonomous product-policy decisions. After implementation, tests and source-neutral evidence, **HARD — Analyst** review of the change and **HARD — Owner** visual acceptance of the running Home view are required before marking done. Do not automatically start another task.

## 5. Scope and required implementation

### 5.1 Training State card

1. Display a compact, readable **line chart of Fitness (42-day) over the most recent six months**, using the existing accepted Training State historical series and its date/as-of semantics. Do not calculate a different Fitness metric, synthesize missing history, or substitute Fatigue/Form.
2. **Scale the Y-axis dynamically to the actual available values**, with meaningful padding and readable ticks; do not hardcode the mockup's bounds. Handle flat, short, partial and empty series honestly.
3. Label the **rightmost actual available Fitness point** with its value near the endpoint. Match the application's existing reasonable numeric precision; **25.9 is illustrative only**. Do not label a stale point as today's value without appropriate date context.
4. Card heading **Training State**, concise subheading **Fitness (42-day) · Last 6 months** (or an accurate equivalent), and a working **View Training State** link to the full page.
5. **Remove the separate Fitness, Fatigue and Form summary tiles from this Home card only.** Keep the full Training State page, its metrics, interactions and provenance unchanged. Retain appropriate Home-level source/coverage explanations or accessible descriptions rather than implying this load-derived Fitness metric is measured physiological readiness.

### 5.2 20-minute Performance card

1. Display the **last 12 months of the existing rolling 42-day best eligible 20-minute power**, using the accepted Performance series and eligibility/source rules. Do not chart the latest eligible ride's value as if it were the rolling best.
2. Use the real rolling-best value as the latest chart endpoint label. In the mockup **195 W** is the rolling best; **124 W** is the distinct latest eligible 20-minute ride in the quick-facts area. Both are illustrative.
3. Preserve the existing current-42-day-best versus latest-eligible-ride distinction everywhere on Home. Do not change qualification, missing-power handling, historical FTP or performance calculations.
4. Card heading **20-minute Performance**, concise subheading **Best 20-minute power · Last 12 months** (or accurate equivalent), and a working **View Performance** link.

### 5.3 Layout and presentation

1. At desktop widths, put **Training State above 20-minute Performance** in the right column alongside the **Recent Activities** table; their combined height should **approximately align with the table**, subject to real content and accessibility. Do not reduce chart legibility solely to force pixel-perfect alignment.
2. Follow the supplied private mockup's card proportions, blue line treatment, endpoint labels, compact typography, spacing, borders and existing RideWorks visual language, while favoring the accepted live UI and responsive behavior when they conflict.
3. Preserve the current Home summary facts, Next Recommended Ride, Recent Activities links/data, Mileage Progress and Annual Mileage Goal, source captions, diagnostics and navigation. Limit changes to what is necessary for these cards and their layout.
4. At narrow widths, stack cards in a readable order, prevent clipping and horizontal overflow at 390px and 320px, and maintain accessible chart descriptions and links. Prefer existing SVG and scoped CSS; do not introduce a charting framework or new backend architecture for this change.

## 6. Explicit non-goals

- No new Fitness, stress, fatigue, form, power, FTP, source-eligibility or training-planning algorithms.
- No changes to full Training State or Performance page functionality.
- No database/schema changes, migrations, data import/sync, production access, deployment or private-source modifications.
- No broad Home redesign beyond the two cards and necessary column alignment; no Phase 6 adaptive planning.
- No hardcoded mockup numbers, fabricated dates, invented trend points or committing the Owner's private screenshot.

## 7. Inputs and local-data expectations

Use the current Home, Training State and Performance application code/services, existing synthetic test fixtures, and accepted UI styles. Confirm the shape and meaning of `training_state()['days']` and the Performance rolling-best series in code before wiring the cards. Existing real rider data may be viewed locally for private visual inspection but must not be copied into GitHub, public reports or screenshots. Do not require the Owner to disclose raw activity files or database contents.

## 8. Outputs

- Focused Home implementation and scoped style changes.
- Appropriate tests for correct series selection, six-/12-month date windows, endpoint values, dynamic Y-axis, missing/short/flat data, correct links and preservation of distinct Performance summary values.
- Privacy-safe `reports/HOME-UI-02/implementation.md` describing actual files changed, data contracts reused, verification results, visual/responsive checks and any known limitations. Keep real-rider screenshots private.
- Task lifecycle updates in `TASKS.md` and `STATUS.md`, and a focused implementation PR for Analyst review.

## 9. Verification

1. Run focused Python tests and relevant existing regression tests. Use deterministic dates/timezones and synthetic histories where needed to prove the six-month Fitness and 12-month rolling-best windows.
2. Verify chart endpoints equal the actual last eligible source values; test a rolling-best-versus-latest-ride disagreement and confirm the chart selects the **rolling best**.
3. Check dynamic Y-axis behavior for increasing, decreasing, flat, sparse and absent data; confirm no fabricated zero or data continuity.
4. Inspect rendered Home at desktop **1440/1024**, tablet **768**, and mobile **390/320** CSS px; compare with the privately supplied mockup and verify card alignment, legibility, endpoint labels, source messages, focus/accessibility and no horizontal overflow.
5. Confirm navigation and unchanged Home recommendations, recent rides, mileage/goal, full Training State/Performance pages and existing accepted numerical behavior. No live production or source data mutation.

## 10. Acceptance criteria

- Training State Home card presents the actual last-six-month Fitness (42-day) line with dynamic Y-axis and actual latest endpoint label, without three Home metric tiles.
- Performance Home card presents the actual last-12-month rolling 42-day best eligible 20-minute power with correctly sourced endpoint; the latest eligible ride remains a separate metric.
- Both cards match the agreed Home visual direction, stack appropriately on mobile, navigate correctly and preserve source/coverage honesty.
- No accepted calculations, eligibility rules, other Home sections or full-page features regress.
- Dex provides tested, privacy-safe evidence and a PR; Analyst technical review and Owner running-UI visual acceptance occur before task completion.

## 11. Stop and report

Stop for Analyst/Owner direction if existing service data cannot support the stated histories without a new model, if historical time/eligibility semantics conflict with the agreed chart, if implementation requires changing accepted metric calculations or exposing private rider data, or if the mockup and these explicit Owner requirements materially conflict. Routine chart/layout/test defects are fixable within this task. Never invent unavailable data or silently broaden scope.
