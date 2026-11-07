# STATUS.md

**Product:** RideWorks.
**Current task:** RACE-02 — screenshot extraction, automatic whole-batch matching, correction/unlink and Activities race fields. [Analyst JIT](docs/tasks/RACE-02.md) · [Issue #60](https://github.com/k14krug/rideworks/issues/60).
**State:** `ready_for_review` — full-image default, explicit status categories, scoped bulk restoration consent and matching safeguards implemented; renewed HARD — Analyst Gate 1 required.
**Branch:** `task/race-02-screenshot-reliability` in the primary checkout.
**PR:** [#61](https://github.com/k14krug/rideworks/pull/61) — draft; renewed HARD — Analyst Gate 1 required after implementation and verification.
**Authority:** Owner implementation instructions supersede the JIT's section-first default and generic attention summary; all-or-nothing automatic matching, restoration/replacement consent and history remain required. The Analyst-authored JIT is unchanged.
**Verification:** 637 Python tests and 81 synthetic browser checks passed. [Review package](reports/RACE-02/full-image-review.md). A read-only dev replay flagged one OCR title spelling difference under the stricter matcher (16/17); it requires source verification/correction, not a wider matching rule. Synthetic verified transcription matches 17/17.
**Production:** No production data access, migration, merge or deployment authorized. No agent-initiated paid extraction.
**Next action:** Analyst reviews the pushed draft PR at renewed Gate 1, including the stricter title rule and scoped restoration approval. Owner Gate 2 and field-by-field acceptance remain outstanding. The real dev service has not been restarted for this revision. No further Astra review.
