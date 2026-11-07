# RACE-02 — Full-image import and explicit review approvals

> Historical report for `89be95e`. The current review package is
> [Final import consent and bounded title variation](owner-review-revision.md).
> The extra restoration checkbox and 16/17 matcher limitation below are superseded.

## Review state and authority

Ready for renewed HARD — Analyst Gate 1 on draft PR #61. Owner Gate 2 and
final acceptance remain outstanding. Implementation uses GPT-6.1 Sol in the
existing primary checkout and task branch; no additional Astra review.

The Owner's 2026-11-07 `/TASK RACE-02` implementation instruction supersedes
the JIT's section-first default, generic attention summary, and cumbersome
per-row restoration UI. It explicitly authorizes this bounded implementation.
The Analyst-authored JIT is unchanged. Automatic all-or-nothing matching,
explicit consent, source retention and transactional validation still apply.
Durable context:

- [Analyst synthesis](https://github.com/k14krug/rideworks/pull/61#issuecomment-6710138876).
- [Owner full-image comparison](https://github.com/k14krug/rideworks/pull/61#issuecomment-6710666360).
- Existing Astra audit and Sol read-only diagnostic supplied in the task chat.

No unresolved requirement conflict requires a new product policy for this
change. Durable draft storage, non-race exclusions, partial imports, new source
precedence, and broader time windows are outside this implementation.

## Evidence and resulting behavior

The Owner reported the same 1525×1864 screenshot yielding 25 sectioned
observations, eight overlap questions and nine displayed matches, versus 17
full-image rows, 17 matches and zero overlap questions after refreshing dev
activities. Estimated costs were $0.00339425 and $0.00140230 respectively.
These are Owner-operated measurements, not new agent API calls or invoices.
The comparison does not establish every field's transcription accuracy.

- Full image is selected in the upload form and is the `stage_import` default.
  Optional sectioning remains explicitly labeled fallback/diagnostic. The crop
  planner advances normally instead of pulling its final crop backwards;
  adjacent overlap is 180 pixels, avoiding the diagnosed 596-pixel repetition.
- Full-image review has one compact editable row per extracted race, with no
  overlap questions. The original and technical evidence remain collapsed.
  Matching errors, OCR corrections, restorations, replacements and source
  conflicts have separate labels/counts. Unresolved fallback observations are
  labeled observations, and their collisions are not counted as activity errors.
- One unchecked consent approves the specific displayed restorations. Its
  deterministic token binds the import/source, complete reviewed values,
  timezone, grouping, Activity IDs and current removal revisions. The commit
  recomputes it under the write transaction. Edits clear client consent; stale
  values, a changed removal set/revision, another import and replay after
  restoration are rejected. Bulk restoration never approves replacement.
  Per-row replacement consent remains separate.
- Candidate classification requires cycling evidence. Title eligibility requires
  the complete distinctive event wording to occur in the activity title, rather
  than one shared word. A one-word distinctive event requires the same distinctive
  title; a visibly ellipsized final word may be a prefix in a multiword title.
  No fuzzy spelling correction or similarity threshold was added. Stage veto,
  exact-date/timezone handling, uniqueness and the ten-minute limit remain.
- Failures distinguish invalid OCR, timezone, absent date coverage, sport, time,
  title, stage, ambiguity and collisions. Up to five nearby candidates are sorted
  by date/time proximity and show source context and rejection reasons. Dates
  are never changed to make a candidate qualify.
- New reconciliation provenance records `race-automatic-v2` and the selected
  candidate's timestamp/title evidence, including source identities. Original
  observations, result/removal history and race/activity power separation remain.
- Prompt text now specifies `HH:MM`, consistent with the schema. New prompt
  versions are `zrp-races-v4` and `zrp-races-section-v5`; prior compatible imports
  remain readable. No schema migration is required.

## Meaningful limitation from read-only dev replay

A read-only replay of the existing full-image dev observations under the
stricter title rule produced **16/17** matches. One extracted title differs in
spelling from its activity source; the prior matcher accepted its single shared
word. This is a correction/review case, not a missing activity. No saved values
were changed and no automatic spelling substitution was introduced. The Owner
must check the original and explicitly correct the field if appropriate.

The synthetic verified-transcription fixture matches 17/17. Do not claim that
the existing uncorrected real extraction automatically matches 17/17 under the
new rule. Other legitimate title variations can conservatively remain blocked;
reviewing those cases is preferable to silently weakening identity checks.

Dev replay used the already authorized primary development database with
SQLite `mode=ro&immutable=1` and `query_only`, without constructing `Store` or
opening a source journal. Main-file metadata remained unchanged and no SQLite
sidecars were created. No production store was accessed. No private titles,
screenshots, raw records, identifiers or credentials are included here.

## Verification

Final commands from the primary checkout:

```sh
env -u DEBUG .venv/bin/python -m unittest discover -s tests -q
node --check rideworks/static/race_review.js
node --check tools/verify_race_full_browser.js
git diff --check
```

**637 Python tests passed.** Clearing the inherited agent `DEBUG=release`
allows CLI subprocess tests to use valid repository settings; configuration was
not edited. An initial run without that cleanup had three CLI configuration
errors; subsequent complete runs passed. Focused race suite: **77 tests passed**.

`tests/race_full_fixture.py` uses invented races and real read/matching boundaries:
14 FIT/export activities, three API-only activities, nonzero source clock offsets,
17 extracted rows and 11 audited removals. It does not copy the Owner's records
or patch away activity-history/source selection. Integration checks cover missing
activity zero-write failure, stale consent after edits/timezone/removal changes,
cross-import/replay rejection, separate replacement consent, retained original
rows, Activity source preservation, history and atomic batch writes.

**81 synthetic browser checks passed** across these fresh disposable previews:

| Preview flag | Port | Browser workflow | Checks |
|---|---:|---|---:|
| `--full-case` | 18921 | `tools/verify_race_full_browser.js` | 25 |
| default | 18922 | `tools/verify_race_results_browser.js` | 21 |
| `--identity-case` | 18923 | `tools/verify_race_identity_browser.js` | 10 |
| `--list-case` | 18924 | `tools/verify_race_list_browser.js` | 15 |
| `--seam-case` | 18925 | `tools/verify_race_seam_browser.js` | 10 |

Each server command used this pattern (substituting the table's flag/name/port):

```sh
.venv/bin/python tools/preview_race_results.py --full-case \
  --data-dir /tmp/rideworks-race02-sol-review-full --port 18921
```

The preview refuses an existing database. All extraction responses and credentials
are synthetic. Browser workflows explicitly select sectioning only for fallback
tests; the new full-image workflow verifies the selected default without changing
it. Each workflow is a Playwright `async page => ...` function, runnable with:

```sh
playwright-cli --session race02-sol goto http://127.0.0.1:18921/race-results/import
playwright-cli --session race02-sol run-code --filename tools/verify_race_full_browser.js
```

The isolated browser was opened with a temporary config pointing at the installed
Chromium executable. The installed CLI was used directly for `run-code`, because
the skill wrapper injects a config flag that this CLI accepts only on browser
startup. Desktop (1440px) and mobile (390px) screenshots were inspected; the
table scrolls within its container on mobile, all fields remain editable and the
single restoration consent remains accessible. Synthetic screenshots are ignored
under `output/playwright/` and are not committed.

## Handoff

Keep PR #61 draft and stop for renewed Analyst Gate 1. The actual development
service was not restarted during implementation. No paid extraction, production
data access/write, deployment, merge, new worktree or new infrastructure occurred.
Owner field verification and running-UI acceptance remain required after review.
