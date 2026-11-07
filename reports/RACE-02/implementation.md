# RACE-02 investigation and implementation handoff

## Status

The Analyst withdrew the source-pixel row-ownership requirement and authorized
deterministic overlapping tiles and explicit Owner observation reconciliation.
The subsequent cross-import identity blocker was addressed under the revised
[JIT](../../docs/tasks/RACE-02.md), section B.9, and
[issue #60](https://github.com/k14krug/rideworks/issues/60). Synthetic
implementation and verification are complete. The Owner, acting as Analyst,
approved Gate 1 in chat; Owner-operated local Gate 2 testing remains, and the
task is not yet accepted. Do not merge or deploy. No production data was
accessed or changed.

## Corrected-date wrong-attachment regression

At prior branch head `3cfeb2b`, a disposable synthetic reimport with a corrected
date added a second association without detecting an earlier wrong attachment.
The old check considered only equal OCR dates; recurring events also made a
blanket wider-date duplicate rule unsafe.

The revised implementation first considers shared original-image SHA and
surviving Owner-reviewed row/group provenance. A source row is known to be the
same only when supported by a shared immutable import observation, or by
reviewed single-row evidence for both imports of the same image. All other
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
  observations; section failures block confirmation. Owner-reviewed grouping,
  correction and visible physical-row count are revalidated in the commit
  transaction. No pixel-derived row count is used. Both sectioned and
  full-image modes are available for the later Owner comparison.
- Attempt-level usage and request IDs are retained where available; unknown
  usage yields a partial/unavailable estimate. The implementation is not
  approved for real screenshot imports.

## Verification

- `.venv/bin/python -m unittest discover -s tests` — **618 tests passed** using
  synthetic data, including migration, rollback, FIT/analytics and race tests.
- Browser verification on two disposable mock-only stores: **18 checks** for
  extraction/reconciliation, confirmation, removal and desktop/mobile
  Activities; **10 checks** for same/different identity decisions, source
  comparison, retained-result protection, separate removal and revalidation.
  Start the fixtures with `.venv/bin/python tools/preview_race_results.py
  --data-dir <new-empty-directory> --port <port>` and add `--identity-case`
  for the latter. The corresponding Playwright workflows are
  `tools/verify_race_results_browser.js` and
  `tools/verify_race_identity_browser.js`. No live extraction was used.
- A synthetic in-memory matching benchmark matched 17 rows against 10,000
  Activities in 0.047 seconds; it excludes database retrieval and is not a
  production performance guarantee.
- `.venv/bin/python reports/RACE-02/row_probe.py` — produced the counts above.
- `git diff --check` — passed.
- Pylance syntax checks passed for the changed Python source and identity
  tests; `node --check` passed for the review and synthetic browser scripts.
- No live model call, real screenshot, production database or browser-based
  Owner test was used. The checks do not establish extraction accuracy,
  account/model availability, or Analyst acceptance. Owner Gate 2 remains
  necessary for full-image versus sectioned per-field accuracy and actual cost.

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
