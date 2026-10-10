# AGENTS.md

## my_strava — RideWorks

This repository is the development repository for **RideWorks**, the personal cycling training application.

It began as a retired Strava application and was reused as the research and development workbench for the project's Strava-export discovery and design work. The same repository will now evolve into the new application; do not assume that the production application will move to a separate repository.

The old Strava application is not a compatibility target. Its architecture, schema, behavior, UI, package structure, dependencies, and runtime choices impose **no constraints** on RideWorks. None of the legacy application code is required to remain. It may be reused selectively, changed, isolated, or deleted wholesale when that is the simplest path for an authorized RideWorks task.

The repository is being retained because it already contains the controlling RideWorks documents, research evidence, reports, mockups, reviews, and useful diagnostic tooling—not because the legacy application code has value or authority. Creating a separate repository is unnecessary unless a later concrete workflow or tooling reason makes it simpler.

Research utilities, reports, and experiments may remain in this repository when useful. Research code is evidence and tooling, not automatically production architecture for the new application.

Implementation work for the new application begins in this repository under the controlling product requirements, accepted design decisions, phase acceptance contracts, and Analyst-authored JIT briefs.

**RideWorks is the product name.** Current product requirements, new task briefs, implementation, and user-facing UI should use `RideWorks` consistently. Historical research/task artifacts may retain earlier working names and do not need cosmetic rewriting.

---

## Roles

### Ken — Owner

Ken makes product, training-analysis, privacy, priority, and final design decisions.

Ken also controls local source data that should not be committed, including bulk Strava exports and personal activity archives, and runs local-data commands when required.

### AI Analyst — ChatGPT

The AI Analyst:

* helps define requirements, experiments, and tasks
* distinguishes ideas, working assumptions, agreed principles, and actual design decisions
* authors and commits the detailed JIT task brief before Dex begins implementation
* creates or updates GitHub issues when useful
* reviews pull requests, experiment outputs, and implementation behavior
* leaves implementation feedback on GitHub
* interprets experimental results with Ken and proposes next work
* does not directly control Dex's local environment

### Dex — Codex Agent

Dex:

* implements assigned work locally from the Analyst-authored JIT brief
* does not author or substantively redesign JIT task briefs
* runs local verification and requested experiments
* asks Ken to run commands only when access to Ken's local-only data or environment is required
* commits and pushes changes
* opens or updates pull requests
* reads and addresses Analyst feedback
* keeps repository status current

### Communication Between Agents

The AI Analyst and Dex do not communicate through a private side channel.

**GitHub is their shared durable communication channel.**

The Analyst may place instructions or review feedback in:

* committed JIT task briefs
* GitHub issues
* pull-request descriptions
* pull-request comments
* review comments

Dex must read the relevant repository documents, issue, PR, and unresolved review comments before beginning or completing work.

Do not rely on Ken to manually relay technical details when the information is already available through GitHub.

---

## Repository Working Files

### `AGENTS.md`

Permanent development, research, data-handling, and workflow rules.

Do not use this file for current task status or transient experiment results.

### `TASKS.md`

The durable task list.

Each task should have:

* task ID
* short description
* status
* scope
* acceptance criteria where useful

Use these statuses unless the repository establishes another convention:

```text
pending
in_progress
blocked
done
```

Only one implementation/research task should normally be `in_progress`.

### `STATUS.md`

Short current handoff state for humans and agents.

Keep it concise and current. Include as applicable:

* current task
* branch
* PR
* implementation/research state
* verification or experiment performed
* blockers
* next action

Do not turn `STATUS.md` into a historical journal. Git and GitHub already provide history.

### `docs/tasks/<TASK-ID>.md`

Detailed just-in-time task brief for the current task.

The AI Analyst authors and commits this brief before Dex starts implementation.

Every newly authored or substantively revised JIT must contain an `Execution Control` section with an `Allowed Invocation` declaration. Valid declarations are:

- `/TASK only`
- `/AUTOTASK only`
- `/TASK or /AUTOTASK`

If a legacy JIT has no `Allowed Invocation` declaration, treat it as `/TASK only`. Never infer autonomous authorization from task simplicity, model capability, prior behavior, or conversation context.

If the selected task has no Analyst-authored JIT brief after repository refresh, Dex must stop and report the missing brief. Dex must not create, reconstruct, expand, or substantively redesign the JIT itself.

---

## Task Lifecycle

### Pending

Before work begins:

* `TASKS.md`: `pending`
* `STATUS.md`: `pending` when the task is the current handoff but has not begun

### Implementation / experiment

Once Dex starts:

* `TASKS.md`: `in_progress`
* `STATUS.md`: `in_progress`

### Ready for Analyst review

When implementation and required local verification/experiments are complete:

* `TASKS.md`: remain `in_progress`
* `STATUS.md`: `ready_for_review`

Do not mark the task `done` merely because code ran or tests passed.

### Analyst requests changes

While addressing feedback:

* `TASKS.md`: remain `in_progress`
* `STATUS.md`: `in_progress`

After changes are implemented, verified, and pushed:

* `TASKS.md`: remain `in_progress`
* `STATUS.md`: `ready_for_review`

### Analyst accepts task

Once the AI Analyst explicitly accepts the work and no implementation/review work remains:

* `TASKS.md`: `done`
* `STATUS.md`: `done`

The PR may still await mechanical merge. Do not make an already-accepted PR merge the persisted Next Action.

Do not automatically begin the next task.

---

## Requirements and Design Sources

`docs/PRODUCT_REQUIREMENTS.md` is the controlling product requirements document. Product phases, design work, and JIT task briefs must trace to it unless Ken explicitly supersedes a requirement.

The RideWorks project documents are the primary source for product principles and settled design context.

When relevant project documents are available in this repository, the JIT brief must identify them under `Requirements Used`. When they are not checked into this repository, the Analyst must carry the relevant requirements into the JIT explicitly rather than asking Dex to infer them.

Current strong principles include:

* build a durable useful personal training history from the best available sources
* preserve original source data whenever practical
* retain provenance where it matters
* distinguish measured, known, calculated, estimated, inferred, and missing data
* treat FTP, weight, zones, bike configuration, and similar athlete state historically
* make important calculations reproducible and replaceable
* do not manufacture precision
* keep activity analysis, longitudinal analysis, training-state assessment, and training planning conceptually distinct
* prefer transparent, explainable analysis
* use Strava as a useful source without making it the product specification or a single point of failure
* do not build mechanisms to evade Strava controls, rate limits, or policies
* treat Sauce and other existing implementations as research references, not authorities

A JIT task may add task-specific requirements but must not silently convert an exploratory idea into a settled product decision.

If a new proposal conflicts with an older source, surface the conflict. Prefer Ken's most recent explicit decision.

---

## Research vs Product Design

This repository is allowed to contain deliberately temporary research code.

Examples include:

* bulk-export inventory scripts
* FIT/TCX/GPX inspection utilities
* data-quality probes
* one-off comparison reports
* algorithm prototypes
* calibration experiments
* validation scripts

A successful experiment does **not** automatically establish:

* the future database schema
* the future application framework
* production package structure
* final algorithms
* final UI
* permanent data representation

Record what an experiment demonstrates and what remains uncertain.

Do not refactor experimental code into a proposed production architecture unless the JIT explicitly asks for that decision.

---

## Local Data and Privacy

Raw personal source data is local-only by default.

Do **not** commit:

* Strava bulk-export ZIP files or extracted bulk archives
* collections of FIT, TCX, or GPX activity files
* access tokens, refresh tokens, client secrets, passwords, or credentials
* local databases containing personal activity history
* environment files containing secrets
* generated artifacts that expose unnecessary personal/location data

Small deliberately selected test fixtures may be committed only when the JIT explicitly permits them or Ken explicitly approves them.

**Explicit FTP-data exception (2026-10-09):** The Owner authorized
committing their 66-entry historical Strava FTP date/value record as a
version-controlled RideWorks source dataset, with documented provenance and
approved date-effective intervals. The source screenshot remains local-only.
This limited approval does not cover other personal activity records,
databases, export archives, or secrets.

**Explicit Elevate-reference exception (2026-10-09):** The Owner authorized
committing the unchanged single file
`data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv`
(496,966 bytes; SHA-256
`407cc7ac2105d5d0c5c8ce4c90775adcb7733957157c2dad6aaa0af05f1ebfb1`)
as a permanent external benchmark, with an origin/limitations README. Its final
14 days are Elevate projections. This exact-file exception supersedes the prior
P4-02 prohibition for this CSV only. It is not production training data, athlete
state authority, a model seed, or permission to commit other exports, screenshots,
activity files, local databases, credentials, or detailed QA artifacts. RideWorks
continues to use the approved dated FTP source. All JIT execution gates remain.


Prefer committing compact derived inventories, summaries, test fixtures, and reports that contain only the information needed for the research task.

Analysis tools should accept local paths as inputs rather than assuming Ken's directory layout.

Never modify original source activity files in place.

---

## Data and Analysis Discipline

Preserve evidence separately from interpretation.

Where practical, analysis outputs should make clear:

* source
* whether a value was measured, supplied, calculated, estimated, or inferred
* assumptions
* algorithm/version when material
* missing inputs
* uncertainty or confidence when material

Do not silently substitute generic cycling assumptions for known rider data.

Do not use today's FTP, weight, zones, or bike configuration for historical activities unless the task explicitly establishes that as an acceptable approximation.

For externally changing facts such as Strava API behavior/policy, FIT specifications, library capabilities, or current third-party software behavior, verify against current authoritative sources when the task depends on them.

---

## JIT Task Brief Requirements

Every `docs/tasks/<TASK-ID>.md` brief must contain, as applicable:

1. Purpose
2. Background / question being answered
3. Requirements Used
4. Execution Control
5. Scope
6. Explicit non-goals
7. Inputs and local-data expectations
8. Required implementation or experiment
9. Required outputs/artifacts
10. Verification / test procedure
11. Acceptance criteria
12. Stop-and-report conditions

Every newly authored or substantively revised JIT must declare `Allowed Invocation` in its `Execution Control` section. A missing declaration means `/TASK only`.

Dex must not change a JIT's `Allowed Invocation`, gate classification, acceptance criteria, or stop conditions. If implementation reveals that those controls need revision, stop for Analyst review.

The JIT expands a `TASKS.md` entry but must not silently redefine its purpose.

If implementation reveals a material conflict, ambiguity, missing requirement, unexpected data condition, or evidence that invalidates the planned experiment, Dex should stop and report it rather than inventing policy.

---

## Execution Control

The project supports two explicit task-invocation paths. The JIT controls which path is authorized.

### Gate classifications

A JIT may divide work into gates when staged implementation or review is useful. Each gate that participates in autonomous execution must be classified as one of:

- `SOFT` — Dex may cross this gate automatically under `/AUTOTASK` only after the gate's required implementation, verification, evidence, and repository updates are complete.
- `HARD — Analyst` — stop for AI Analyst review and authorization.
- `HARD — Owner` — stop for Ken's product, training-analysis, privacy, priority, visual, or final design decision.

A JIT does not need artificial gates when the task is naturally one implementation unit. Do not create ceremony merely to label steps.

### Mandatory stop conditions

Under either invocation path, Dex must stop and report rather than guess when any of these occurs:

1. controlling requirements conflict or are materially ambiguous;
2. a new or changed product, training-analysis, privacy, priority, or final design decision is required;
3. implementation would materially expand task scope;
4. the JIT appears incorrect, incomplete, or inconsistent with higher-authority repository sources;
5. source data, experiment results, or analysis reveal materially unexpected evidence that invalidates the planned approach or acceptance assumptions;
6. required verification fails in a way that may indicate a requirement, design, data, or analytical problem rather than a straightforward implementation defect;
7. a required source, dependency, or authoritative external rule cannot be established;
8. a `HARD — Analyst` or `HARD — Owner` gate is reached.

Straightforward implementation defects discovered while executing an otherwise unambiguous authorized gate may be corrected and re-verified within that same gate.

### Invocation authorization

The slash command must be permitted by the current JIT's `Allowed Invocation`.

- If Ken invokes `/AUTOTASK` for a `/TASK only` JIT, do not implement. Report that the JIT authorizes `/TASK` only.
- If Ken invokes `/TASK` for an `/AUTOTASK only` JIT, do not implement. Report that the JIT authorizes `/AUTOTASK` only.
- If the JIT allows both, the command used for the current invocation selects the execution behavior.
- Do not persist a global execution-mode setting. Authorization is task-specific and invocation-specific.

---

## Repository Sync

Never begin work from a stale checkout.

### Initial remote refresh is unconditional

At the start of `/TASK` or `/AUTOTASK`, Dex must:

1. Confirm there are no unexpected local changes that would make switching branches unsafe.
2. Run `git fetch origin --prune`.
3. Only after fetching, evaluate task, branch, PR, JIT, and repository state.

### Starting a new task

1. Confirm the worktree is clean.
2. Fetch `origin`.
3. Checkout `main`.
4. Pull with fast-forward only: `git pull --ff-only origin main`.
5. Verify the selected pending task has an Analyst-authored `docs/tasks/<TASK-ID>.md` on refreshed `main`.
6. If missing, stop and report it.
7. Create or switch to the task branch.

### Continuing an existing task or review

1. Confirm there are no unexpected local changes.
2. Fetch `origin`.
3. Checkout the existing task branch.
4. Pull that branch with fast-forward only.
5. Read the relevant issue, PR, and latest unresolved/recent Analyst feedback.

Do not require switching to `main` in the middle of existing task work.

---

## Start-of-Work Procedure

Before changing code:

1. Read `AGENTS.md`.
2. Read `TASKS.md`.
3. Read `STATUS.md`.
4. Read the Analyst-authored `docs/tasks/<TASK-ID>.md`.
5. Read source documents named in the JIT.
6. Inspect relevant existing code and tests.
7. Read the relevant issue/PR if one exists.
8. Read unresolved PR review comments.
9. Continue existing `in_progress` work before starting another task.

If repository state, task files, GitHub state, source data, or instructions conflict, report the conflict rather than guessing.

---

## `/TASK`

`/TASK` is the controlled execution path. It preserves the conservative workflow and never uses autonomous gate-crossing authority.

Before implementation, verify that the current JIT permits `/TASK`. If it does not, stop without changing implementation state.

When Ken invokes `/TASK`, Dex should:

1. Perform the unconditional remote refresh and appropriate repository sync.
2. Read `AGENTS.md`, `TASKS.md`, and `STATUS.md`.
3. Continue the current `in_progress` task if one exists.
4. Otherwise select the next appropriate `pending` task.
5. Verify the Analyst-authored JIT exists; stop if it does not.
6. Read the JIT and its `Requirements Used` sources.
7. Mark the task `in_progress` in `TASKS.md` and `STATUS.md`.
8. Implement only that task.
9. Add/update tests where appropriate.
10. Run required verification or experiments.
11. Update status according to the Task Lifecycle.
12. Make focused commits.
13. Push/update the PR when appropriate.
14. Report what changed, verification/results, and blockers or unresolved findings.

If the JIT defines staged gates, `/TASK` must stop at each explicit review boundary rather than using `SOFT` classification as permission to continue. A later `/TASK` invocation may resume from the next authorized point after the required review or instruction is present.

Do not automatically begin another task.

---

## `/AUTOTASK`

`/AUTOTASK` is the bounded autonomous execution path. It allows Dex to continue through Analyst-preauthorized `SOFT` gates without requiring Ken to relay a continue command after each one.

Before implementation, verify that the current JIT permits `/AUTOTASK`. If it does not, stop without changing implementation state.

When Ken invokes `/AUTOTASK`:

1. Perform the same unconditional remote refresh and repository sync required by `/TASK`.
2. Read the same repository, JIT, source, code/test, GitHub issue/PR, and unresolved-review context required by the Start-of-Work Procedure.
3. Continue the current `in_progress` task if one exists; otherwise select the next appropriate `pending` task.
4. Verify that the Analyst-authored JIT exists and explicitly permits `/AUTOTASK`.
5. Mark lifecycle state exactly as required for normal implementation.
6. Implement only the current task and only within the JIT's authorized scope.
7. For each `SOFT` gate:
   - complete the gate's implementation;
   - run the gate's required verification;
   - record any required durable verification evidence;
   - inspect the resulting diff and relevant data/analysis invariants;
   - update repository/GitHub state as required;
   - continue automatically only when the gate is clean and no mandatory stop condition applies.
8. Stop immediately at a `HARD — Analyst` or `HARD — Owner` gate and provide a concise review package containing:
   - gates completed;
   - material files/behavior changed;
   - verification performed and results;
   - the exact decision or review needed;
   - branch/PR and current head.
9. If a mandatory stop condition occurs before a hard gate, stop at that point and report the conflict, failure, or uncertainty without inventing policy or broadening scope.
10. When all authorized implementation gates are complete, set `STATUS.md` to `ready_for_review` and leave `TASKS.md` `in_progress` unless the JIT explicitly defines an Analyst-authorized mechanical closeout that is consistent with the Task Lifecycle.
11. Final task acceptance remains with the AI Analyst unless the controlling JIT and repository governance explicitly say otherwise. `/AUTOTASK` does not by itself authorize Dex to declare substantive implementation accepted.
12. Do not automatically start the next task.

`/AUTOTASK` changes execution cadence, not requirements ownership. Dex still must not author or redesign the JIT, invent product/design policy, silently resolve conflicts, or weaken acceptance criteria.

---

## Testing and Verification

Testing requirements depend on the task.

For software behavior:

* add tests for meaningful reusable behavior
* run the relevant test suite
* never claim a test passed without running it
* do not weaken or delete a test merely to make code pass

For research/analysis tasks:

* make the experiment reproducible
* record the exact command(s) used
* separate code correctness from conclusions drawn from Ken's data
* report unexpected input/data conditions
* prefer machine-readable outputs plus a concise human-readable summary when useful

Do not add CI, GitHub Actions, containers, databases, or other infrastructure unless the JIT calls for them.

---

## Scope Discipline

While working a task:

* stay within JIT scope
* do not modify unrelated legacy code
* do not add speculative product features
* do not perform opportunistic refactors unless required
* do not silently make product/design decisions
* do not turn a research script into production architecture without instruction
* keep implementation understandable
* preserve provenance and reproducibility

Record newly discovered work as follow-up rather than automatically expanding scope.

---

## Git and Pull Requests

Use focused commits.

A PR should make it easy for the Analyst to determine:

* what question/problem was addressed
* what changed
* what command/tests/experiment were run
* what outputs were produced
* what the evidence supports
* what remains unresolved

If the Analyst leaves actionable review feedback, address it before declaring the task ready for acceptance.

A pushed branch or passing local test run is not final acceptance.

---

## Completion Standard

A task is complete when:

1. JIT-requested behavior or experiment is complete.
2. Required verification has been run.
3. Required outputs are reproducible and understandable.
4. Source data/provenance distinctions are preserved.
5. No prohibited personal source data or secrets were committed.
6. No unrelated changes are included.
7. `TASKS.md` is current.
8. `STATUS.md` is current.
9. Applicable review feedback has been addressed.
10. The AI Analyst has explicitly accepted the task.

When finished, provide a concise handoff containing:

* task completed
* material files changed
* verification/experiment performed
* important findings
* branch/PR
* blockers or follow-up work
