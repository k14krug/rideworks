# RACE-02 investigation and implementation handoff

## Status

The Analyst withdrew the source-pixel row-ownership requirement and authorized
deterministic overlapping tiles and explicit Owner observation reconciliation.
The subsequent cross-import identity blocker was addressed under the revised
[JIT](../../docs/tasks/RACE-02.md), section B.9, and
[issue #60](https://github.com/k14krug/rideworks/issues/60). Synthetic
implementation and verification are complete. The Owner, acting as Analyst,
approved the earlier Gate 1 in chat. Subsequent Owner testing exposed a
wrapped-title crop fragment and an unnecessarily technical review screen;
the Analyst revised the JIT. The revised implementation now stops for renewed
HARD — Analyst Gate 1 review; the task is not yet accepted. Do not merge or
deploy. No production data was accessed or changed during this implementation.

## Race-first review simplification

The default review is a compact table, with all eight fields editable on
demand, a race/match/attention summary, plain estimated cost, the original
screenshot, and collapsed technical details. Ordinary observations start as
separate races without an Owner decision. Only plausible pairs from adjacent,
overlapping sections receive a same-race/two-races question and optional crop
comparison. No observation is silently merged or removed. A single final
list acknowledgment replaces the typed physical-row count; it is not proof
that extraction found every source row.

The candidate heuristic compares normalized dates, times, title words and
finish when available. It is an aid to review, not proof of identity or a
guarantee that every bad extraction will be flagged. A wrapped-title fragment
with missing date remains a possible pair when it shares distinctive title
text. Conflicting source values must be checked and corrected against the
screenshot. Pair decisions, raw observations and the derived distinct-race
count are preserved; the final transaction recomputes the pairs, grouping,
identity conflicts and automatic matches. A count derived from a checked list
is explicitly marked in provenance and is not treated as the older explicitly
verified physical-row count when determining prior same-image identity.

Synthetic coverage includes 17 races with the 2026-09-27 Stage 3 Electric
Break overlap: one pair question, no per-row source decision, all eight fields
editable, no writes while a pair, match or acknowledgment is unresolved,
and one atomic 17-race commit after correction. The interface remains subject
to Analyst and Owner review; the mock cannot establish real-model accuracy.

## Section-specific prompt revision

Sectioned extraction uses `zrp-races-section-v4` and the exact eligibility
text in JIT section A.1, with each edge labeled from the actual original-image
crop bounds. It no longer sends the full-image partial-row instruction. The
common field/schema rules remain, and full-image mode retains its prior
`zrp-races-v3` prompt. The import and each section retain the effective
version and crop coordinates.

Raw observations are never removed or automatically grouped. The earlier
first/last-observation boundary warnings have been removed: observation order
does not establish pixel position, and a complete row can have unreadable
fields. The Owner resolves flagged overlap pairs and checks conflicting values
against the screenshot. Final-list acknowledgment, unique automatic matching
and transaction validation remain mandatory.

The synthetic 768×939 seam regression draws a wrapped “Stage 4 Loop de Loop”
across the boundary and mocks a separate “Loop” observation. It verifies
request text and edge hints, retains the bad observation and a complete row
with unreadable date, proves unresolved/missing-date batches write no
results, and confirms only two races after explicit reconciliation and
correction. Mocks test the safeguards, not model compliance or transcription
accuracy. Real-model behavior and the full-image versus section comparison
remain for a separately authorized Owner Gate 2.

## Corrected-date wrong-attachment regression

At prior branch head `3cfeb2b`, a disposable synthetic reimport with a corrected
date added a second association without detecting an earlier wrong attachment.
The old check considered only equal OCR dates; recurring events also made a
blanket wider-date duplicate rule unsafe.

The revised implementation first considers shared original-image SHA and
surviving Owner-reviewed row/group provenance. A source row is known to be the
same only when supported by a shared immutable import observation, or by
an explicitly verified physical single-row count in an earlier import of the
same image together with a single current reviewed race. A derived list count
is not treated as a verified physical-row count. All other
same-image pairs, including legacy imports, remain explicit review candidates.
For different images, candidates use an OCR-date neighborhood of ±3 calendar
days, local clock time within 10 minutes, and distinctive event words. This is
a bounded candidate search, **not** proof of identity or a guarantee of
detecting every possible historical OCR error.

The review shows both original screenshots, stored result and Activity details.
“Same race” blocks and links to the separate confirmed removal; it never
changes the old record as a batch side effect. “Different races” is bound to
the new import, source observations and values, selected automatic Activity,
old import and exact old-result revision. Decisions are recomputed and recorded
with successful import reconciliation. Stale source/result revisions, missing
or corrupt images, unresolved pairs, and over 400 possible pairs block the
batch. A result marked “different” cannot simultaneously be replaced by
another row in that batch. Existing Activity matching and the whole-batch gate
remain independent. Tests cover legacy provenance, same-hash distinct rows,
cross-date correction, recurring races, removal/restoration, stale decisions,
source corruption, multiple rows, and retained-result replacement.

## Synthetic evidence

An experimental section merger required equal extracted values and overlapping
model-reported row coordinates. Five basic synthetic tests passed, including
overlap, conflicting outputs, distinct equal rows at different reported
positions, and invalid positions. A further adversarial synthetic case used
two images: one with one physical row, the other with two physical rows and
an internal separator. Supplying the same plausible model-reported bounding
box and row values for both images yielded one merged row in both cases.
The merger did not independently verify which pixels represented a row.

A separate synthetic pixel-border probe detected a wide separator but missed
a shorter separator and treated every line of a gray background as a
candidate. These probes do not establish that an independent image-boundary
approach is impossible; they show that the attempted methods do not justify
silently collapsing these observations. The experimental code and fixtures
were not retained as implementation.

The information ambiguity is reproducible with this equivalent minimal
synthetic example. The mock observations intentionally agree even though the
second image has an additional physical separator; no model is called.

```bash
.venv/bin/python - <<'PY'
from PIL import Image, ImageDraw

for physical_rows in (1, 2):
    image = Image.new('RGB', (768, 939), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 420, 700, 479), outline='black')
    if physical_rows == 2:
        draw.line((30, 450, 700, 450), fill='black')
    left = {'top': 420, 'bottom': 480, 'event': 'Synthetic'}
    right = {'top': 420, 'bottom': 480, 'event': 'Synthetic'}
    merged_count = 1 if left == right else 2
    print(f'Physical rows: {physical_rows}; geometry/value-only merge: {merged_count}')
PY
```

OpenAI's [images and vision limitations](https://developers.openai.com/api/docs/guides/images-vision#limitations)
warn that vision models may struggle with precise spatial localization and
small text. Therefore model-supplied coordinates alone are not verified
physical-row evidence. No live OpenAI request or personal screenshot was used.

## Source-pixel separator probe

Run `.venv/bin/python reports/RACE-02/row_probe.py`. The probe looks for
contrasting horizontal runs and rejects irregularly spaced boundaries. It is
an experiment, not an implementation or a complete segmentation algorithm:

| Synthetic case | Actual rows | Inferred rows |
|---|---:|---:|
| One row | 1 | 1 |
| Two identical rows | 2 | 2 |
| 768x939, wrapped titles | 17 | 17 |
| Taller image | 33 | 33 |
| Short separator | 17 | 17 |
| Gray background | 17 | 17 |
| Identical adjacent rows | 17 | 17 |
| Clipped bottom row | 17 | 16 |
| Equally spaced heading separator | 17 | 18 |

Even regular source-pixel spacing is insufficient to identify table ownership:
a heading can resemble another row boundary, and a clipped last row lacks a
bottom border. More heuristics may reject these examples, but we have not
established how they can reliably distinguish table content without also
rejecting valid variants. These counts are historical evidence, not the current implementation or a
requirement to reject the screenshot. The revised JIT explicitly withdraws
pixel-derived row ownership.

## Implemented work in progress

- An experimental automatic matcher checks date, local time, timezone/DST,
  distinctive title words, explicit stage conflicts, candidate uniqueness and
  collisions; the review and final transaction recompute the full batch.
  Manual selection and skipping are rejected. Cross-import candidate evidence
  and explicit source-identity decisions are separate from matching.
- Removal records a tombstone without deleting source or activity evidence;
  restoration/replacement requires explicit approval. Activities displays
  separate score and race watts using a bounded query.
- The default model is `gpt-6-luna`, and a standard-tier estimate accounts for
  reported cached input and cache-write tokens as well as output tokens,
  without adding reasoning tokens twice. The snapshot is dated 2026-11-06:
  $0.10 input, $0.01 cached input, $0.125 cache write, and $0.50 output per
  million short-context tokens; long-context multipliers apply. The model
  [documentation](https://developers.openai.com/api/docs/models/gpt-6-luna),
  [pricing](https://developers.openai.com/api/docs/pricing) and
  [prompt-caching documentation](https://developers.openai.com/api/docs/guides/prompt-caching)
  were checked. This is not a bill; regional premiums or other charges can
  differ. Unknown usage or pricing is unavailable/partial.
- Dimension-based section plans retain original images, bounds and raw model
  observations; section failures block confirmation. Pair decisions, final
  list acknowledgment and matching are revalidated in the commit transaction.
  No pixel-derived row count is used. Both sectioned and
  full-image modes are available for the later Owner comparison.
- Attempt-level usage and request IDs are retained where available; unknown
  usage yields a partial/unavailable estimate. The implementation is not
  approved for real screenshot imports.
- Prior-association review no longer treats a shared image hash alone as
  evidence of a shared race. Candidates require defensible same-source
  provenance, matching retained source observations or unique source title and
  time, or nearby date/time with distinctive event wording. A candidate is not
  automatically identified as the same race merely by its image or matching
  text; ambiguous candidates still require a decision. Evidence is bounded:
  missing provenance and materially different OCR can conceal a relationship,
  while recurring similar races can still need review.
- For a same-race overlap with conflicting extracted fields, the exception card
  displays both raw values, permits editing the final list row, and requires a
  separate screenshot verification. The server binds that verification to the
  source observations, pair, grouping choices, final values and timezone and
  checks it again during the atomic commit. Raw source observations remain.

## Verification

- `.venv/bin/python -m unittest discover -s tests -q` — **629 tests passed** using
  synthetic data, including migration, rollback, FIT/analytics and race tests.
- `PYTHONPATH=tests .venv/bin/python -m unittest -q test_race_identity
  test_race_review_simplified test_race_sections test_race_results` — **61 tests
  passed**. They include 17- and 33-race same-image reimports, corrected values,
  a prior wrong Activity attachment, recurring races, and value-bound pair
  verification for conflicting score, signed change, date and watts.
- Browser verification on four disposable mock-only scenarios: **21 checks**
  for extraction/reconciliation, matching, cost, Activities columns and
  removal confirmation; **10 checks** for same/different identity decisions,
  source comparison, retained-result protection, separate removal and revalidation;
  **10 checks** for the seam fragment and missing-date block; **15 checks** for
  the 17-race list, one overlap decision, acknowledgment, matching and mobile layout.
  Start the fixtures with `.venv/bin/python tools/preview_race_results.py
  --data-dir <new-empty-directory> --port <port>` and add `--identity-case` or
  `--seam-case` or `--list-case` for the other scenarios. The corresponding Playwright workflows are
  `tools/verify_race_results_browser.js` and
  `tools/verify_race_identity_browser.js`, `tools/verify_race_seam_browser.js`
  and `tools/verify_race_list_browser.js`.
  Equivalent top-level snippets were executed in the integrated browser; no
  live extraction was used.
- A synthetic in-memory matching benchmark matched 17 rows against 10,000
  Activities in 0.047 seconds; it excludes database retrieval and is not a
  production performance guarantee.
- `.venv/bin/python reports/RACE-02/row_probe.py` — produced the counts above.
- `git diff --check` — passed.
- Pylance syntax checks passed for the revised Python source, review tests and
  preview; signature checks found 12 compatible `commit_rows` call sites and
  three compatible `review_page` call sites.
  `node --check` passed for the synthetic browser scripts.
- No live model call, real screenshot, production database or browser-based
  Owner test was used in this verification. The checks do not establish extraction accuracy,
  account/model availability, or renewed Analyst acceptance. Owner Gate 2
  remains necessary for full-image versus sectioned per-field accuracy and
  actual cost.

The matching-only benchmark command was:

```bash
.venv/bin/python - <<'PY'
from datetime import date, timedelta
from time import perf_counter
from rideworks.race_matching import batch_matches
start = date(1997, 1, 1)
activities = [{'activity_id': str(i), 'start_time': (start + timedelta(days=i)).isoformat() + 'T11:33:00+00:00', 'absolute_time': True, 'activity_type': 'Virtual Ride', 'subtype': None, 'title': 'Stage 4 Hillcrest', 'match_watts': None, 'match_watts_source': None} for i in range(10000)]
rows = [{'date': (start + timedelta(days=i)).isoformat(), 'start_time': '11:33', 'event': 'Stage 4 Hillcrest', 'race_group': '0-210', 'finish': 1, 'avg_watts': 160, 'race_score': 180, 'race_score_change': 0} for i in range(9983, 10000)]
begin = perf_counter()
matched = batch_matches(rows, 'UTC', activities)
elapsed = perf_counter() - begin
print(f'Synthetic matching: {len(rows)} rows, {len(activities)} activities, {sum(bool(item["activity_id"]) for item in matched)} matches, {elapsed:.3f} seconds')
PY
```

## Migration safety

The additive migrations retain existing active results, imports,
screenshots and revision history, and adds a removal audit record rather than
deleting source evidence. Migrations and rollback checks use disposable stores
only. Before any separately authorized production activation, stop database
writers and verify a consistent backup of the complete current data directory;
keep the matching old code and configuration. Old code rejects newer schema
versions, and restoring an older database after new writes would discard those
writes without a separate reconciliation decision.
