# FTP-02 — Add manual FTP entries after the latest recorded date

**Status:** Owner explicitly requested implementation on 2026-10-27; development change only, not production promotion.
**Issue:** [#47](https://github.com/k14krug/rideworks/issues/47).
**Predecessor:** FTP-01 (Owner-accepted, merged). This JIT supersedes FTP-01's intentionally deferred *after-last insertion* restriction, and nothing else.

## 1. Purpose / Owner decision

FTP History must allow the rider to record their judged FTP on **any previously unrecorded effective calendar date**, with no prerequisite ride or 95%-best-20 result. Values may rise or fall. This specifically includes adding a **new latest** entry after the most recent one, e.g. 186 W at an earlier date and 160 W today when the rider believes fitness has declined.

The existing 95%-of-best-20 plot is comparison evidence, **not** automatic FTP detection or a gate on manual entry.

## 2. Requirements Used

- Owner's 2026-10-27 RideWorks conversation approving unrestricted date-effective **new entries**, while explicitly deferring general edit/delete of existing entries.
- [FTP-01 JIT](FTP-01.md) and accepted SQLite history/graph/consumer implementation.
- `AGENTS.md`, `docs/PRODUCT_REQUIREMENTS.md`, `TASKS.md`, `STATUS.md`.
- Current files `rideworks/ftp_history.py`, `rideworks/static/ftp.js`, `rideworks/ftp_page.py`, `rideworks/web.py` and FTP tests.

## 3. Execution Control

**Allowed Invocation: /TASK only.**

Development implementation and review are permitted by the Owner request. Make a focused task branch and draft PR. **HARD — Owner:** no merge/deployment or writes to the actual development/production personal database without explicit Owner review/acceptance. OPS-03 is still a separate pending task; do not perform its production rollout as a side effect.

Mandatory stop conditions from AGENTS.md apply, including conflicts, uncertain source data, or unexpected validation failures. Independent Analyst review is required before asserting full acceptance.

## 4. Scope and behavior

- Maintain **one** ordered SQLite FTP timeline; settings are positive whole watts and date-effective on the established `America/Los_Angeles` athlete calendar.
- Permit insertions **before first**, **strictly between**, and **strictly after last**. On a new last date, the previous FTP stops applying at the start of that date and the new FTP applies indefinitely until a subsequent entry is added.
- Preserve existing historical rows, including equal-watt entries on distinct dates and first-entry unknown-prehistory semantics.
- Continue rejecting existing dates; no implicit overwrite. Keep empty-history initialization out of scope.
- Update backend validation and frontend preview/save enablement consistently. For a new last entry, explain which previous FTP expires and that the new value continues until replaced.
- Keep manual date/watts entry independent of chart selection, preserve 95% best-20 chart and ride suggestions, and retain stale-revision/nonce/Origin protections.
- Reuse existing history revision/signature invalidation for Training State, Home, Plan, and Activity Review; do not change measured power or immutable source records.

## 5. Explicit non-goals

No automatic FTP rise/drop inference; no change to 20-minute or training analysis algorithms; no editing/deleting existing FTP rows; no history migration, schema redesign, data provenance classes, new source fields, or future-date policy beyond existing date validation; no Strava writeback; no general UI redesign; no live data write or release rollout.

## 6. Implementation and verification

1. Remove the after-last prohibition from `ftp_history.add_entry` without relaxing duplicate, revision, positive-watts, or nonempty-history checks.
2. Update `ftp.js` preview: enable Save for valid last-date insertion and describe its effective interval; avoid showing "After-last extension is unavailable". Update page help text only as needed.
3. Update synthetic tests for: a lower FTP after the last entry; a second later entry; prior timeline unchanged; date-effective lookup before/on/after the new date; same-date collision; stale submission; before-first/intermediate/empty-history behavior unchanged.
4. Verify frontend preview allows manual after-last date (and refuses collisions), existing ride suggestions still operate, and server accepts the form through the current secure POST path.
5. Where practical, check Training State and Plan get the new latest FTP and that the history signature changes. Run applicable focused tests and the full suite on a local checkout; if this environment cannot execute full integration tests, document the limitation and request the normal local CI/agent run. Do **not** claim tests passed if not executed.

## 7. Acceptance criteria and handoff

A user can enter a date later than the latest setting and any positive supported integer FTP, even with no ride. The chart and current FTP reflect the new date-effective value, including a decrease; older date lookup/ride data are unchanged. Duplicate dates and stale/invalid writes still fail. Before-first and between-entry insertion, the 95%-best-20 evidence graph, and dependent training-state/planning calculations remain correct.

Commit the implementation/tests and publish a draft PR for review with actual verification results. **Stop at Owner review**; do not deploy or modify the personal SQLite data store under this task.
