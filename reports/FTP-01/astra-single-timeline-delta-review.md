# FTP-01 — focused single-timeline delta review

**Reviewer:** Astra, independent analyst (GPT-6 Astra). **Date:** 2026-10-15.

**Reviewed:** `task/ftp-01-timeline-review`, base `a1a5ae9fd6719fd43ccf0dfd139b057944df8f21`; current `docs/tasks/FTP-01.md`, `STATUS.md`, and issue [#37](https://github.com/k14krug/rideworks/issues/37), including the definitive Owner clarification posted 2026-10-15 at 02:28:26 UTC.

**Disposition:** The corrected single-history/intermediate-insertion contract is technically coherent. I found **no unresolved product decision that must block Gate 1 storage/consumer work** after renewed Analyst authorization. The implementation concerns below fit the revised brief; they do not require restoring the superseded design. This review grants no implementation authority.

## What the clarification changes

One table of effective date and positive integer watts is sufficient, with a unique date constraint and optional stable identity. Derive each exclusive end from the next date; do not persist an end that requires updating neighboring rows on insertion. Equal watts on different dates remain separate entries. Use ordinary insertion, never replacement/upsert that silently overwrites a same-date entry.

The first 66 records seed this same table. There is no technical need for origin columns, protected anchors, supplemental classes, duplicate original observations or an edit ledger. My prior recommendations requiring separate retained observations/lineage are superseded. Small store-level initialization metadata and a history revision/signature serve technical correctness without classifying entries.

I independently confirmed that tracked `rideworks/`, `tests/` and `pyproject.toml` have no diff from the original reviewed implementation commit `a85ff5a`. The worktree was clean when inspected, and GitHub returned no open PRs. No conflicting Gate 1 implementation is present in this checkout; this is not a claim about unobserved work elsewhere.

## Bootstrap and initialization

`Store.__init__` (`rideworks/store.py:339`) currently upgrades schemas automatically. Keep that schema creation separate from the explicit 66-record bootstrap. Validate the specified approved inputs before opening a target through a constructor that may write. Commit timeline entries, completion marker and history revision atomically, including parity checks before commit.

After a completed bootstrap, replay must consult its durable marker and return without comparing the *current* timeline to the original 66 records. Otherwise a legitimate insertion or correction looks like corruption and can trigger accidental restoration. A conflicting marker, failed/partial state or nonempty unmarked target must stop rather than merge. Failed transactions must leave neither partial entries nor a success marker.

A concrete implementation detail matters: distinguish a genuinely new empty store from an existing store awaiting bootstrap **persistently**, not by current row count. An old empty schema and a new store can otherwise become indistinguishable after restart. Record initialization state during schema setup using the pre-upgrade state; complete the transition during explicit bootstrap. An existing-store upgrade remains migration-needed until initialized; a genuinely new store remains valid without fabricated FTP. This is a technical implementation of the brief, not a second history model.

## Lookup and caches

`training_state.py:58–99` currently rejects empty history and hardcodes the Strava-history source label. Replace the runtime loader with the store-scoped history reader, accept initialized empty history, and remove or neutralize that misleading source-specific label consistently for every entry. Preserve date-effective lookup and the established Los Angeles calendar/unknown-timezone boundary behavior.

An intermediate insertion changes the effective FTP only from its date to the next entry. Existing stored rows remain untouched even though their derived interval descriptions change. Multiple insertions follow identical rules regardless of which preceding entry was imported or added later.

`ride_results` currently reads FTP before its transaction (`training_state.py:685`); move the DB history/revision read inside the coherent calculation snapshot. A canonical sorted date/value signature plus a monotonically changing revision is sufficient for calculations and stale-submission detection; no per-origin signature is needed. Global invalidation is already compatible with the existing whole-history digest approach.

Planning's classifier already includes resolved FTP and power in its signature (`planning.py:79`). Preserve that dependency, rider overrides and saved intent snapshots. Daily models recompute from per-ride results, so an insertion can influence later Fitness/Fatigue/Form beyond its direct FTP interval. No new analytical model or rescaling of literal Planning watt targets is needed.

## Targeted tests and remaining boundaries

Gate 1 should demonstrate:

- Exact initial parity; failed-import atomicity; replay after insertion/correction without reset; new versus migration-needed state across restart.
- The illustrative insert-between example, lower/higher values, repeated intermediate inserts, equal watts on distinct dates, same-date rejection and exact preservation of every existing stored row.
- Inclusive/exclusive edges, empty history, athlete/browser calendar differences and unknown-timezone boundaries.
- Unchanged storage-only numerical results; inverse-square stress response within the inserted interval; downstream daily propagation; cache/restart agreement; unchanged HR candidates, observed work, power evidence, overrides and saved intents.

Before-first/after-last insertion and the minimal correction/removal interaction remain **later workflow choices** if needed. They need not block implementing lookup, bootstrap, signatures and the authorized intermediate-insertion operation. Do not resolve them through origin-based restrictions or silently broaden the operation. A general edit/delete UI is not required for Gate 1.

**Verification limits:** text/code/Git/GitHub inspection only. No application or Store execution, database inspection/write, CSV changes or tests. Publish these findings and stop for Analyst reauthorization; Gate 2 and live promotion remain unauthorized.
