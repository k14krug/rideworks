# FTP-01 — Database-owned FTP history and editable performance chart

**Status:** pending — owner direction accepted 2026-10-14; **Astra pre-implementation review required; NO CODING authorized yet**.
**Purpose:** Replace the current packaged-CSV FTP runtime source with editable, date-effective SQLite FTP history, and integrate the established FTP-vs-20-minute chart into RideWorks so the Owner can add, revise or remove historical FTP values from any plotted ride.

## Requirements Used

- Owner's 2026-10-14 directions in the RideWorks project conversation: FTP history belongs in the application database; the FTP CSV files must disappear at completion, with **no archival FTP CSV retained**; select **any orange or gray** 20-minute performance point; use 95% of best-20 power as an editable starting value; allow increases, decreases, date selection and manual judgment; view changes in Training State.
- Current [AGENTS.md](../../AGENTS.md) and the task/review lifecycle; [product requirements](../PRODUCT_REQUIREMENTS.md); existing historical FTP principles and accepted [Training State implementation](../PHASE_4_ACCEPTANCE.md).
- Actual current code, especially `rideworks/training_state.py`, `rideworks/training_state_page.py`, `rideworks/planning.py`, `rideworks/store.py`, `rideworks/performance.py`, related browser routes and tests.
- The Owner/Dex 2026-10-13 report `data/reports/ftp-vs-20-minute-2026-10-13/ftp-vs-20-minute-interactive.html` on the local system: 879 comparable eligible rides, 69 above then-effective recorded FTP, 810 others; existing full-history graph with FTP step line, orange/gray points, zoom, pan, date slider and tooltips. **This local report is reference evidence, not a proposed permanent application data source.**

## Execution Control

**Allowed Invocation:** `/TASK only`.

### Gate 0 — HARD — Analyst (Astra), BEFORE ANY IMPLEMENTATION

On the first invocation, Dex must **not change production code, database schema, migration scripts, UI, tests, or FTP CSV files**. Refresh the repository and read the current sources and this JIT. Have **Astra in an independent analyst/reviewer role** critically review this plan against actual current code and local runtime/migration constraints, not simply rubber-stamp it. This is the Owner's explicit pre-coding requirement.

Astra must assess and report:
1. All active FTP consumers: Training State and its per-ride cache/daily recomputation, Planning and its classification/projections/cache, current-FTP display or analysis elsewhere, and all remaining packaged/root CSV and test dependencies. Identify any implementation traps.
2. Safe one-time **66-entry** migration from the existing two equivalent FTP CSV sources to the single production SQLite database, including run order (import **before** removing packaged sources), idempotency, rollback and new/empty database behavior. Avoid a permanent hardcoded 66-row duplicate embedded in code.
3. Edit semantics: date-effective intervals, insertion between entries, same-date collisions, editing/deleting historical entries, original import provenance and user-added entry/activity reference; handling earlier-than-known-history dates; no new automatic FTP estimator.
4. Chart integration: authoritative source of plotted eligible best-20 points, orange/gray classification against the **current edited** FTP history, responsiveness/selection, editable FTP/date defaults and consequences preview. Compare practical reuse options before imposing an extra large plotting runtime.
5. Cache invalidation and correctness: changed FTP should affect FTP-normalized power stress, resulting 42-/7-day Fitness/Fatigue and Form; HR-based stress is independent of FTP; changes should be reflected on page refresh. Audit any stale Planning caches, not only Training State.
6. Full FTP-CSV deletion from final **active repository and runtime** (both `data/athlete/strava_ftp_history.csv` and `rideworks/data/strava_ftp_history.csv`, plus obsolete loaders, documentation, packaging and test references). A version-control historical commit is not a runtime/archive file; do not manufacture a new archival copy.
7. Verification and rollout on a **copy** of the live private store, with data-preservation parity, behavior checks, failure paths and source-privacy guarantees. No production write during planning or review.
8. Whether this one task should be staged into two implementation gates (database migration, then UI integration) without changing the approved functional objective.

Record Astra's independent findings and recommended changes in a durable review artifact or GitHub issue comment, identifying reviewed branch/commit. **STOP and return review findings to the Owner/Analyst; no coding until the review is accepted and an Analyst-controlled revised brief explicitly authorizes implementation.** Dex must not substantively rewrite the JIT.

### Gate 1 — Implementation (blocked pending Gate 0 authorization)

After explicit authorization from the Owner/Analyst following Astra review, Dex may begin implementation through a fresh `/TASK FTP-01`, on a focused task branch/draft PR, with the required implementation gate(s) and verification.

### Gate 2 — HARD — Analyst; Gate 3 — HARD — Owner

After implementation and independent verification, stop for code/behavior review, then Owner review of the running FTP editor/chart and Training State consequences. No merge, destructive CSV cleanup in the live environment, or claim of completion before approval.

## Product behavior and scoped implementation target (for Astra to challenge)

- SQLite is the **only live authoritative FTP history** after migration. Preserve the exact 66 previously recorded FTP setting dates/values in the database before deleting their CSV sources. Use a small rider-specific table/model; do not build a generic athlete-state framework.
- Date-effective semantics: each entry applies from its date until the next entry. An entry may be inserted, edited or deleted; avoid silently clobbering an existing entry on the same date. Support values lower or higher than prior settings.
- Integrate a graph substantially like the Dex-created standalone one: recorded FTP step line; **all qualifying ride points** with orange above then-effective FTP, gray otherwise; toggle, informative tooltip, zoom/period navigation. A selected point may seed a proposed FTP entry with rounded 95%-of-best-20 value and ride date, both user editable. An easy ride's gray value is **not** asserted to establish actual FTP.
- Before save, preview effective-date implications and any existing-entry collision. Record provenance (original transcribed Strava history vs Owner adjustment; optionally initiating ride/activity) without requiring a second 'inferred FTP' series. No automatic FTP overwrite or Strava writeback.
- Persist changes through existing RideWorks UI patterns. Refresh charts after save; return clear errors on invalid input. Support correction or deletion of user-entered values without modifying original activity measurements.
- All runtime readers including Training State and Planning must use database FTP. Reuse/adjust Training State's current input-signature/cache behavior so FTP edits invalidate needed cached power stress and derived daily Fitness/Fatigue/Form; preserve non-FTP HR stress and measured work/kJ.
- The **final active checkout, deployed application and tests must not depend on either FTP source CSV**. Delete both tracked FTP CSVs once SQLite promotion is safely completed, and retire obsolete instructions, loaders and packaging dependencies. No leftover FTP CSV archive. Keep unrelated CSV-based research exports out of scope.

## Explicit non-goals

- No new FTP estimation algorithm, automated historical correction, scheduled backfill, bulk Strava API harvesting, or automatic Strava FTP updates.
- No redesign of Training State mathematics, no Plan feature redesign and no changes to measured power or preserved FIT/source activities.
- No unrelated file cleanup, enterprise history services or generalized athlete profile engine.

## Required implementation verification (after Gate 0 approval only)

1. Migrate all 66 records exactly once into a **copy of production SQLite**; compare date/value sequence and affected calculations before/after migration with unchanged FTP. A fresh empty store should start safely with no fabricated FTP.
2. Verify add/edit/delete/insert-betweens, same-date handling, interval edges, lower and higher FTP entries, invalid input, restart persistence and recovery from a failed migration.
3. Verify identical Training State results before/after storage-only migration, then an intentional FTP edit changes affected power-derived stress and the appropriate daily/42-/7-day curves on a new page request. Verify unchanged HR-only stress and observed work.
4. Verify Planning reads the edited history and cannot quietly use stale FTP/classification/cache values; inspect other FTP consumers found in Gate 0.
5. Browser verification of all-dot selection, editable suggested watts/date, preview, save, chart repaint/reclassification, refresh, mobile/desktop and keyboard accessibility.
6. Search the **active runtime and source tree** for legacy FTP CSV dependencies; prove neither FTP CSV remains as a file in the accepted final checkout/deployment, and no hardcoded duplicate dataset substitutes for it.
7. Verify all original rides/FITs and unrelated SQLite state are intact. Run focused and general regression tests using synthetic fixtures and private-store copies, not committed personal data.

## Stop-and-report conditions

Stop for Gate 0 review before coding. After authorization, stop if the CSV-to-DB migration ordering risks losing the 66 entries, if any FTP consumers remain unexplored, if existing user changes would be overwritten, or if maintaining a consistent runtime requires a material unapproved product decision. The Analyst must settle substantive changes to this brief; Dex must not silently broaden it.

## Acceptance

Final Owner acceptance requires (a) authoritative editable SQLite FTP history, (b) functional ride-dot-to-history UI for higher or lower manual FTP entries, (c) new Training State and Planning views reflecting those entries correctly, and (d) both FTP-source CSV files removed from the final active source and runtime, not archived or silently reused.
