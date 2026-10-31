# NAV-01 — Power sidebar navigation for 20-Minute History and Power Curve

**Status:** pending — Analyst-authored JIT, 2026-10-31.
**Purpose:** Rename the existing sidebar **Performance** section to **Power**, exposing **20-Minute History** and **Power Curve** as two selectable child destinations. This is a presentation/navigation change; both analytical views already exist.

## 1. Background and Owner decision

On 2026-10-31, the Owner explicitly requested that the left sidebar's **Performance** entry become **Power**, with two choices:

- **20-Minute History**
- **Power Curve**

The two existing modes of the current Performance page supply the content. The Owner wants navigation to each through the left sidebar rather than treating them as one undifferentiated Performance destination.

This **new navigation decision supersedes** the older PC-01 presentation decision to offer both modes *within* a single sidebar Performance entry. It does **not** supersede PC-01's accepted calculations, source eligibility, power-curve comparisons, 20-minute history, chart interactions or Activity Review power curve.

## 2. Requirements Used

- [AGENTS.md](../../AGENTS.md), [TASKS.md](../../TASKS.md), [STATUS.md](../../STATUS.md): Analyst-authored JIT, task lifecycle, invocation, privacy, and review.
- [Controlling product requirements](../PRODUCT_REQUIREMENTS.md), especially Performance History and `PERF-001`–`PERF-005`, plus existing persistent-sidebar direction.
- [Accepted PC-01 task](PC-01.md), [Power Curve acceptance](../POWER_CURVE_ACCEPTANCE.md), and [PC-01 design](../design/PC-01-power-duration-curves.md): preserve both already accepted views and their behavior.
- Current production navigation/page logic, particularly `rideworks/web.py`, `rideworks/power_curve_page.py`, current templates/styles/scripts and navigation/browser tests. Inspect the refreshed code before choosing implementation details.
- Owner's explicit 2026-10-31 sidebar rename/split request (this JIT records that decision).

## 3. Execution Control

**Allowed Invocation: `/TASK only`.**

**Dependency / sequencing:** HOME-UI-05 is currently `in_progress` and at `ready_for_review` on draft PR #56. Do not abandon, preempt, mark done, merge, or otherwise change its lifecycle as part of NAV-01. Start NAV-01 only when the existing task is accepted/cleared under `AGENTS.md` and the Owner invokes the authorized task workflow.

One bounded implementation unit. Start from a clean, freshly fetched `main` and create a NAV-01 task branch/draft PR. After implementation and verification, stop at **HARD — Analyst** source/regression/accessibility review; then **HARD — Owner** running-UI navigation/visual approval. No automatic merge, no production deployment.

## 4. Scope and required implementation

1. Replace the **Performance** *sidebar navigation label* with **Power**. The left sidebar must have two identifiable, separately selectable entries under Power: **20-Minute History** and **Power Curve**.
2. Each child entry must directly display the respective already-existing Performance view. They must be usable as distinct navigable states, not merely show both charts stacked in one unchanged page.
3. The **Power** parent should act as a clear navigation group. Preserve the application's established sidebar appearance and responsive behavior; avoid adding unrelated global navigation or a third Power overview page.
4. Ensure correct active/expanded state and links when entering each view, including direct browser navigation and reload. Switching between the children should feel like ordinary navigation.
5. Preserve existing bookmarked/deep links and compatibility where practical: the current `/performance` history default and existing Power Curve deep-link behavior (currently exercised by `/performance?curve=1`). They may resolve to the new destinations or retain the existing underlying route/state. Use the smallest practical implementation, rather than designing a new routing framework.
6. Remove or adjust any redundant in-page mode selector only insofar as needed to avoid contradictory/confusing navigation. Do not remove useful filters, periods, comparison controls, exports, chart interactions, inspection links, or relevant explanatory content.
7. Scope the sidebar change consistently across pages (including Home, Activities, Activity Review, Plan and Settings), without changing those pages' own functionality.
8. Follow existing accessible semantics and keyboard navigation, including visible focus, current-section indication and small-screen/sidebar behavior. The two choices must remain understandable when the sidebar collapses or stacks.

## 5. Explicit non-goals

- No new charts, algorithms, derived metrics, source eligibility rules, database/schema changes, rebuilds or synchronization changes.
- No reworking 20-minute calculations, curve envelopes, date ranges, overlays, tooltips, ride links or evidence policy.
- No redesign of Activity Review's own ride-specific Power Curve.
- No broader renaming of all references to the *concept* of performance, nor restructuring Home Performance chart/cards.
- No unrelated design refresh or production deployment.

## 6. Inputs and local-data expectations

This task should be implementable using repository code, synthetic fixtures and existing tests. No private FIT archive, Strava account connection, local production store, personal activity records or Owner screenshots are required. Do not commit personal activity data, screenshots or secrets.

## 7. Outputs / artifacts

- Focused implementation in the established RideWorks navigation and page/view logic.
- Focused automated tests (plus any updated browser tests) for both sidebar choices, deep-link behavior, selected/expanded state and preserved view controls.
- A concise sanitized implementation/verification report suitable for Analyst review.
- A draft PR referencing NAV-01; leave task `in_progress` / `ready_for_review` until required review gates are cleared.

## 8. Verification procedure

1. Inspect current navigation and both Performance modes on refreshed `main`; record the actual relevant routes and existing behavior before changing them.
2. Exercise each sidebar child from multiple other pages; verify the correct history chart or power-duration comparison view is displayed and the correct sidebar choice is identified.
3. Load and reload each view using its direct URL; verify backward compatibility for existing Performance and curve links or document a clear redirect/alias.
4. Exercise the existing 20-minute controls and Power Curve comparison/interaction controls without numerical or source-policy changes. Check Activity Review's independent Power Curve still works.
5. Check desktop, narrow/mobile, keyboard/focus and accessible current-page/group semantics, using established browser-check conventions.
6. Run focused tests and the repository's normal regression suite; report results and any changes to tests.

## 9. Acceptance criteria

- Sidebar says **Power**, not **Performance**, and displays the two requested choices.
- **20-Minute History** opens the existing 20-minute Performance history view.
- **Power Curve** opens the existing multi-duration Performance Power Curve view.
- These are independently navigable, reloadable views, with sensible active group/child indication on desktop and mobile.
- The previous page's filters/charts, period selections, source explanations, link targets and analytical results remain intact.
- Existing direct links are not needlessly broken; Home Performance card and Activity Review remain unaffected.
- Focused/full tests and browser/accessibility evidence are provided for Analyst review, followed by Owner visual acceptance.

## 10. Stop-and-report conditions

Stop and ask the Analyst/Owner rather than inventing policy if:

- the current sidebar architecture cannot support two children without material routing/layout redesign;
- implementing this would break accepted PC-01 analytical behavior or require a change to accepted history/power-curve source policy;
- existing route/link compatibility cannot reasonably be preserved;
- another task's in-progress or review state would need changing;
- a material product/visual decision not captured in this JIT becomes necessary;
- required verification indicates an unresolved regression.

Do not start the next task automatically after this one.
