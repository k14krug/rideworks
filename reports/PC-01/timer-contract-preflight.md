# PC-01 source/timer-contract preflight

PC-01 was invoked with `/AUTOTASK PC-01` on 2026-10-11 after a clean-worktree
remote refresh and fast-forward to main `f09d68b`. The Analyst-authored JIT
permits this invocation. Issue #27 has no additional feedback; prior P5-01
is accepted and merged. The two-screen mockup was opened in Chromium and
visually inspected. Feature implementation stopped during source-policy
verification, before changing product code, schema, sources or the JIT.

## Why execution stopped

JIT §6 requires strict observed one-second windows, including native timer
boundaries/contradictory or stopped intervals where timer evidence matters.
It also requires exact raw-value, display and earliest-window parity with
accepted best-20 for shared qualifying sources. The accepted
`best-average-power-v1` implementation uses timestamps and watts without
consulting timer events.

Two retained cases make the missing boundary/contradiction rule material:

1. A fully verified FIT active interval has a nonzero observation exactly at
   the terminal stop. A diagnostic that requires each forward one-second bin
   `[sample timestamp, timestamp + 1 second)` to lie within the half-open
   timer interval changes its best-20 value. Treating the stop observation as
   a supported endpoint preserves the accepted value. **This is an endpoint
   interpretation question, not proof that the accepted sample is invalid.**
2. A different accepted FIT best-20 window contains **127 consecutive samples
   strictly after the last paired timer stop**. The same-source timer/session
   durations disagree, so its timer scope is **not verified** by the existing
   Training State helper. Restricting the curve to the paired active interval
   changes its best-20 under either endpoint interpretation. Conversely,
   blindly trusting its timer scope is unsupported. PC-01 does not explicitly
   say how to classify this conflicting evidence while preserving history.

The second case is not merely an off-by-one endpoint. No diagnosis of all
timer-unverified rides is implied: failure of the existing helper's strict
whole-session verification can have multiple causes, and paired events are
distinct from a fully corroborated session. The source contract must define
when such evidence is usable, unavailable or contradictory.

## Reproducible evidence

`tools/check_pc01_timer_contract.py` opens a supplied database using SQLite
`mode=ro`, holds one read transaction and does not construct a `Store`, run
migrations, reextract or alter original files. It selects only current
`virtual-power-evidence-v2` / `best-average-power-v1` / 1,200-second rows;
retained superseded v1 rows are not counted twice.

For each eligible native result, it checks the cached raw value, display,
earliest record indices and eligible-window count against the accepted native
function and an independent integer prefix-sum window oracle. It then compares
two **diagnostic interpretations**, neither adopted as production policy:

- Half-open active scope containing each forward one-second sample bin.
- Samples at both timer endpoints permitted, with distinct active intervals
  still separated. This isolates after-stop contradictions from endpoint policy.

The existing `timer_scope()` is reused unchanged to distinguish paired events
from session-verified intervals. No gap filling or pause stitching occurs.
Detailed IDs, timestamps, summaries and event evidence stay in ignored local
output. The committed [aggregate](timer-contract-preflight.json) contains only
source-neutral counts and integrity results.

| Check | Result |
| --- | ---: |
| Eligible native results, current policy only | 1,022 |
| Cached/native/independent best-20 parity | 1,022 |
| Paired timer scopes | 1,020 |
| Fully session-verified timer scopes | 39 |
| Paired scopes without whole-session verification | 981 |
| Multiple active intervals | 28 |
| Unpaired timer event source | 1 |
| Source without timer events | 1 |
| Half-open value changes, verified scope | 1 |
| Half-open value changes, summary-unverified scope | 1 |
| Endpoint-inclusive value changes, summary-unverified scope | 1 |
| Samples strictly after last stop in conflicting accepted window | 127 |
| Retained original artifacts verified by SHA-256 and byte size | 1,422 |
| SQLite integrity / foreign-key violations | ok / 0 |

Artifact verification independently read `sources` and `export_snapshots`
and checked their retained bytes against recorded hashes and sizes. No
existing product modules, FTP records, Elevate benchmark or private files
are changed or included in this branch.

Commands used from the repository root (local paths are example inputs, not
hard-coded requirements):

```bash
.venv/bin/python tools/check_pc01_timer_contract.py \
  --data-dir local_data/p5-01-v2/store \
  --private-output local_data/pc-01/timer-contract-private.json \
  --aggregate-output reports/PC-01/timer-contract-preflight.json
.venv/bin/python -m unittest discover -s tests -p 'test_pc01_timer_contract.py' -v
.venv/bin/python -m unittest discover -s tests -q
```

The four synthetic diagnostic tests pass. They reproduce terminal-stop
interpretation, strictly after-stop samples, active-interval separation,
null/zero/gap/tie and invalid-power behavior without personal fixtures.
The full existing Python suite plus those four tests passes: **416 tests in
22.899 seconds**. This validates existing behavior and the diagnostic; it
does not establish PC-01 feature acceptance.

## Required Analyst clarification

Define in the controlling JIT/design:

1. Whether a native observation at a terminal stop is supported for MMP and
   how sample endpoints relate to timer boundaries, consistent with the
   accepted observed-window semantics.
2. How PC-01 handles accepted sources with paired timer events contradicted
   by session duration or continued observations. In particular, clarify
   whether their curves are unavailable pending resolution, or which existing
   evidence establishes qualifying windows, and how the parity requirement
   applies to those sources. Do not infer that all 981 unverified scopes
   should be excluded.

A narrow possible resolution is an explicit endpoint rule plus explicit
curve-unavailable treatment for materially contradictory sources, preserving
accepted best-20 history. This is a proposal for Analyst/Owner review, not
an implemented eligibility change or a rewritten JIT.

The mandatory stop follows `AGENTS.md` Execution Control conditions 1, 4 and
5 and PC-01 §12's source/timing ambiguity and parity boundaries. It precedes
HARD — Analyst Gate 1: no feature, archive-profile runtime, API-curve parity or
production-curve browser acceptance is claimed. The task remains blocked;
Phase 6 remains deferred.
