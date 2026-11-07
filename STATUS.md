# STATUS.md

**Product:** RideWorks.
**Current task:** RACE-02 — screenshot extraction, automatic whole-batch matching, correction/unlink and Activities race fields. [Analyst JIT](docs/tasks/RACE-02.md) · [Issue #60](https://github.com/k14krug/rideworks/issues/60).
**State:** `in_progress` — HARD — Analyst Gate 1 accepted at `413be43b653f396e2de23524e06832371c63896b`; awaiting HARD — Owner Gate 2.
**Branch:** `task/race-02-screenshot-reliability` in the primary checkout.
**PR:** [#61](https://github.com/k14krug/rideworks/pull/61) — draft; [Gate 1 technical acceptance](https://github.com/k14krug/rideworks/pull/61#issuecomment-6709552675). Owner Gate 2 and final task acceptance remain outstanding.
**Production:** Owner reports RACE-01 is in production; no RACE-02 production action or deployment is authorized.
**Evidence:** The [investigation](reports/RACE-02/implementation.md) records identity filtering and pair-scoped overlap verification. Full synthetic suite: 630 tests passed; 56 mock-only browser checks passed.
**Development:** Real application started from implementation `413be43` in the primary checkout using the normal repository `.env` and `data/` store (schema 14; no migration needed). URL: <http://127.0.0.1:8767/race-results/import>. Transient user service: `rideworks-dev.service`; restart with `systemctl --user restart rideworks-dev`. Inherited agent `DEBUG=release` is cleared so repository configuration applies.
**Startup verification:** Import form, settings and review JavaScript returned HTTP 200; served JavaScript matches the checkout. Settings confirms the dev store. Normal `python -m rideworks serve` uses the real Responses API extraction path, with `gpt-6-luna` and a configured server-side key; no synthetic extractor injected. No screenshot upload or extraction request performed by Dex. Production untouched.
**Next action:** Owner uploads the chosen screenshot and initiates live sectioned/full-image extraction through the dev UI, then evaluates Gate 2. Keep PR draft; no merge, deployment or agent-initiated live extraction.
