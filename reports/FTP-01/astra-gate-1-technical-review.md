# FTP-01 Gate 1 technical review

Reviewer: **GPT-6 Astra (orchestrator-selected `gpt-6-astra`; fresh context)**. This is a distinct technical review, not external Analyst acceptance.

Reviewed branch: `task/ftp-01-implementation`. Exact reviewed commit: `662e95400b3ff6d840398befe68dc7cf3d931225`; diff base: `92667ad`. PR: #41. Review date: 2026-10-15. Scope: Gate 1 only; no Gate 2 implementation or production promotion reviewed or authorized.

## Disposition

**PASS — affirmative Gate 1 technical review.** No unresolved material implementation findings and no required fixes. The reviewed storage, bootstrap, insertion and reader changes satisfy the Gate 1 contract when considered together with the recorded private-copy evidence. Gate 2 may proceed under the controlling JIT after the implementation agent completes its gate bookkeeping. Gate 3/4 Owner authorization requirements remain unchanged.

## Examination and findings

Reviewed AGENTS.md, the current FTP-01 JIT, relevant product/Phase 4 requirements, the actual implementation/test diff, source call sites, verification utilities, Gate 1 implementation report and all three aggregate evidence files.

- **Schema/bootstrap: pass.** The pre-upgrade new/existing distinction is durably saved before the legacy migration chain. Schema migration commits history/state/version atomically. A new Store has valid empty history; an existing uninitialized Store raises a migration-needed error instead of silently calculating without FTP. Source identity and structure are checked before target construction. Bootstrap row insertion, completion marker, revision and parity verification share one transaction. Replay follows the completion marker, preserving intermediate additions. Nonempty unmarked targets are refused.
- **Timeline: pass.** A single source-neutral table supports lower, higher and equal-watt intermediate entries without changing old rows. Canonical dates, positive integer values, duplicate dates, stale revisions and the currently authorized intermediate range are validated. Inclusive/exclusive lookup and the established athlete-calendar/unknown-timezone behavior remain intact. No import-origin restrictions or extra original-history timeline were introduced.
- **Consumers/cache coherence: pass.** Active runtime FTP loading now requires the Store. Training State reads history and digest inside its calculation transaction; the digest participates in stress-cache keys. Planning completed history, current context and classifier reads share transactions; classifier signatures include effective FTP and power context. Home and page-level transaction boundaries prevent mixtures across page components. Activity Review uses the same history; saved intents and rider corrections are not rewritten. No measured-power algorithm or Planning target-watt policy changed.
- **Recovery/privacy: pass for this gate.** Aggregate evidence records fixed-clock model parity, preservation of 24 non-cache tables and 1,422 artifacts, inverse-square response, independent daily convolution, restart/replay agreement and restoration using matching old code/database. I inspected the verification implementation and aggregate reports; I did not independently rerun personal-data experiments. No personal archive/database or raw activity evidence was added by the reviewed diff. FTP CSVs appropriately remain available at Gate 1.

Severity findings: **none requiring correction**. No code fixes were made during this review.

## Independent verification actually run

Working directory: `/home/kkrug/projects/rideworks-ftp01`.

```bash
DEBUG=0 PYTHONPATH=tests /home/kkrug/projects/rideworks/.venv/bin/python -m unittest test_rideworks_ftp_history test_rideworks_planning test_rideworks_training_state
```

Result: **70 tests passed**, 3.235 seconds. Includes import parity/replay after insertion, source rejection before target creation, injected bootstrap rollback, migration interruption, stale/duplicate/date checks, concurrent snapshot consistency, lock rejection, cache invalidation and Planning regressions.

An additional `DEBUG=0 PYTHONPATH=tests /home/kkrug/projects/rideworks/.venv/bin/python -` synthetic verification used `TemporaryDirectory` and explicitly targeted Stores. It injected failure in the earliest schema script (before the normal schema existed), reopened the Store and verified retained new-store identity, empty-history Training State and Plan usability; it then injected an aborting revision trigger and verified row/revision rollback plus restart equality. Result: **PASS**. No default/live Store was constructed.

```bash
DEBUG=0 /home/kkrug/projects/rideworks/.venv/bin/python -m unittest discover -s tests
```

Result: **483 tests passed**, 33.909 seconds.

## Limits and next gate

The private-copy evidence was supplied by the implementation pass and reviewed, not independently regenerated here. Gate 2 must still exercise actual editor submissions and cross-page behavior, including stale tabs, date handling, accessibility and final installed-package retirement checks. Existing research/verification references to FTP CSVs are retirement work explicitly assigned to Gate 2, not a Gate 1 defect. This report does not approve deployment, live writes, CSV deletion from the released checkout, or final task acceptance.
