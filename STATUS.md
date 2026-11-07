# STATUS.md

**Product:** RideWorks.
**Current task:** RACE-02 — screenshot import reliability. [Analyst JIT](docs/tasks/RACE-02.md) · [Issue #60](https://github.com/k14krug/rideworks/issues/60).
**State:** `ready_for_review` — renewed HARD — Analyst Gate 1 required after Owner Gate 2 rejected restoration clutter and the near-title abstention. Owner Gate 2 remains unaccepted.
**Branch:** `task/race-02-screenshot-reliability` in the primary checkout.
**PR:** [#61](https://github.com/k14krug/rideworks/pull/61) — draft.
**Authority:** [Latest Analyst instructions](https://github.com/k14krug/rideworks/pull/61#issuecomment-6713802752) plus renewed Owner `/TASK RACE-02`. The Analyst-authored JIT is unchanged.
**Changes:** Matched row labels; restoration intent in the final import button with one screenshot acknowledgment; full assignment/result/history binding and transactional validation; bounded one-character long-word title variation under independent evidence and unique matching. Active replacements remain separately approved.
**Verification:** 641 Python tests, 81 focused race tests and 84 synthetic Chromium checks passed. Desktop/mobile screenshots inspected. Private read-only development replay: 17 rows, 17 unique automatic matches, zero matching failures, 11 restorations; database hash/size/mtime unchanged. [Review package](reports/RACE-02/owner-review-revision.md).
**Development:** Real staged import remains unconfirmed. The real development service was not restarted for these new changes; browser verification used isolated synthetic stores. Do not treat an existing process as running this revision.
**Restrictions:** No production access/writes, migration, paid extraction, worktree, Astra review, merge or deployment.
**Next action:** Analyst reviews the new head and report at HARD — Analyst Gate 1. After acceptance, prepare the real dev app for Owner verification of all eight screenshot fields and final import UX. No further implementation until review.
