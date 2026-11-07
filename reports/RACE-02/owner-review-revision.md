# RACE-02 — Final import consent and bounded title variation

Ready for renewed **HARD — Analyst Gate 1** on draft [PR #61](https://github.com/k14krug/rideworks/pull/61). Owner Gate 2 remains unaccepted. Implemented by Sol in the primary checkout on `task/race-02-screenshot-reliability`.

## Authority and scope

The [latest Analyst instructions](https://github.com/k14krug/rideworks/pull/61#issuecomment-6713802752) and renewed Owner `/TASK RACE-02` invocation authorize these narrow corrections after the real UI rejection. They supersede the previous extra restoration checkbox and exact-word-only title rule. They preserve the JIT's explicit import/restoration intent, separate active replacement approval, all-or-nothing matching and retained evidence. The Analyst-authored JIT is unchanged. No additional requirement conflict was found.

The [previous full-image implementation report](full-image-review.md) is historical evidence for the full-image default, optional section fallback, prompts and earlier verification. Its 16/17 abstention and restoration-checkbox description are superseded here.

## Changes

- Previously removed, automatically matched races show **Matched**. One neutral summary states how many will be restored; the specific list is available under collapsed details. There is no per-row restoration error or extra restoration checkbox.
- The final button explicitly says **Import 17 races (restore 11 previously removed)** for the reported case. The existing single screenshot/list acknowledgment is required. Preview, GET and background activity refresh do not import or restore results. Active-result changes still require separate replacement approval.
- The final action carries a confirmation token binding the exact import and original source hash/raw rows, all final values, grouping, timezone, every automatic Activity assignment, current results, complete result revision history and removal history. The server recomputes matching and this token inside the write transaction before writes. Missing, stale, edited, differently assigned and replayed forms fail. A subsequent removal cannot be resurrected by replaying an earlier import form. No schema change.
- Matcher version `race-automatic-v3` normalizes case, punctuation and diacritics. It permits exactly one character substitution/insertion/deletion in one long word (both words at least eight characters), with at least one other exact distinctive word and no other unmatched extracted distinctive words. This is a conservative implementation bound, not a universal OCR accuracy claim. Short-word edits, two spelling changes and one shared word remain insufficient.
- The spelling allowance only participates after the same calendar date, known timestamp offset, virtual cycling type, unchanged ten-minute window and stage-conflict checks. All qualifying candidates compete equally; exact wording does not break a tie against a plausible minor variant. Multiple candidates or duplicate batch assignments block the entire batch.
- Collapsed matched-activity details show the source title/date/time and explain the one-character variation and independent evidence. Ambiguity explicitly explains that date, time and title cannot distinguish the candidates. No screenshot fields or source Activity metadata are rewritten.

Original screenshots/raw outputs, all eight editable fields and recomputation, cross-import identity protection, source provenance, audited removal/replacement, atomic confirmation and separate race versus activity watts remain intact. No broad source-selection redesign or extraction change was added.

## Evidence and verification

A private, authorized read-only replay of the existing development full-image import produced **17 rows, 17 automatic matches, zero matching failures and 11 restorations**. Exactly one match uses the bounded spelling allowance: one unmatched long token and one exact distinctive anchor. All seventeen Activity assignments are unique. Private titles, dates, IDs, screenshots and source records are absent from these fixtures and this report.

The diagnostic opened the existing development SQLite file using `mode=ro&immutable=1`, `query_only=ON` and a read transaction after checking for journal/WAL sidecars. It bypassed Store initialization/migration. Database SHA-256, size and modification time were identical before and after. No extraction, correction, import confirmation or database write was submitted. This is deterministic matcher replay, not another live vision evaluation or proof of every screenshot field.

Automated fixtures use invented records and an invented long-word spelling variation. The 17-row fixture includes fourteen FIT/export-backed rides and three API-only rides, with eleven audited removals. It retains selected timestamp/title source evidence and leaves original extraction values unchanged after import.

Verification run:

```sh
env -u DEBUG .venv/bin/python -m unittest discover -s tests -q
# 641 tests passed, 42.036 seconds
env -u DEBUG .venv/bin/python -m unittest discover -s tests -p 'test_race*.py' -q
# 81 focused tests passed
node --check rideworks/static/race_review.js
node --check tools/verify_race_full_browser.js
node --check tools/verify_race_identity_browser.js
git diff --check
```

A follow-up run of the six full-review tests passed after adding explicit subsequent-removal replay and late replacement-failure history assertions. The inherited agent `DEBUG` variable was cleared only for subprocess tests; configuration files were unchanged.

**84 Chromium checks passed** against five isolated synthetic preview stores: 28 full-image, 21 import/Activities, 10 cross-import identity, 15 fallback list and 10 seam. Desktop 1440×1000 and mobile 390×900 checks cover matched row labels, no extra restore checkbox, explicit final button, collapsed technical/edit details, minor-title explanation, edit/recompute/acknowledgment reset, missing activity blocking and atomic 17-result import. Existing fallback conflict verification, wrong attachment removal and Activities behavior pass. Screenshots were inspected locally and remain ignored.

Browser reproduction: start `tools/preview_race_results.py` with a fresh `/tmp` data directory for each of `--full-case`, default, `--identity-case`, `--list-case`, `--seam-case`; run the corresponding `tools/verify_race_{full,results,identity,list,seam}_browser.js` function through Playwright. These servers inject synthetic extraction responses; they make no paid requests and never use the real development store.

## Limits and next gate

The matcher still uses the established Activity presentation's selected source timestamp/title; it does not search every historical source for a favorable match. Near-title recognition is intentionally bounded and can abstain on more extensive spelling differences. The Owner must still verify all eight displayed fields against the original screenshot, especially scores and changes. Synthetic checks and read-only replay do not establish model accuracy or Owner UI acceptance.

The real development service was not restarted for these unaccepted code changes, and the existing real import remains unconfirmed. No paid API calls, production access/writes, worktrees, Astra review, merge or deployment occurred. Stop for renewed Analyst Gate 1 review before another Owner test. Keep PR #61 draft and RACE-02 in progress.
