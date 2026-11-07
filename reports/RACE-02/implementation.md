# RACE-02 investigation and implementation handoff

## Status

The Analyst withdrew the source-pixel row-ownership requirement and authorized
deterministic overlapping tiles and explicit Owner observation reconciliation;
see [issue #60](https://github.com/k14krug/rideworks/issues/60) and the revised
[JIT](../../docs/tasks/RACE-02.md). That work is implemented, but a separate
incorrect-attachment case below blocks the task. Gate 1 is **not** complete.
The branch is work-in-progress and must not be used for real imports, merged
or deployed. No production data was accessed or changed.

## Blocking case: corrected date on an existing wrong attachment

The current conflict check compares a newly matched race against saved results
only when their extracted date, start time and distinctive event words overlap.
If an earlier extraction used a wrong date and was saved on a different
Activity, correcting that date can produce a valid automatic match to the
intended Activity without finding the old attachment. On a disposable
synthetic store, the following demonstration added one result and left **two
active associations**. The intended interpretation is that the earlier
observation represented the same physical race with an OCR date error; the
records alone do not prove that identity.

```bash
.venv/bin/python - <<'PY'
import json, sys, tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
sys.path.insert(0, 'tests')
from test_race_sections import image, result
from rideworks import race_results as race
from rideworks.store import Store
with tempfile.TemporaryDirectory() as root:
    with Store(Path(root) / 'store') as store:
        row = result(date='2024-11-08')
        previous = result(date='2024-11-06')
        with patch('rideworks.race_results.configuration', return_value=('', 'gpt-6-luna', 10_000_000)):
            old_import = race.stage_import(store, image(), 'UTC', extractor=lambda *_: ([previous], None), mode='full')
            identity = race.stage_import(store, image(), 'UTC', extractor=lambda *_: ([row], None), mode='full')
        wrong, correct = str(uuid4()), str(uuid4())
        for activity in (wrong, correct):
            store.connection.execute('INSERT INTO activities VALUES (?,?)', (activity, 'synthetic'))
        store.connection.execute('INSERT INTO race_results VALUES (?,?,?,?,?)',
                                 (wrong, old_import, json.dumps(previous), 'UTC', 'synthetic'))
        candidate = {'activity_id': correct, 'start_time': row['date'] + 'T' + row['start_time'] + ':00+00:00',
                     'absolute_time': True, 'activity_type': 'Virtual Ride', 'subtype': None,
                     'title': row['event'], 'match_watts': None, 'match_watts_source': None}
        item = {'values': row, 'group': 'different', 'corrected': False, 'action': 'confirm',
                'replace': False, 'shown_activity': correct, 'shown_revision': 'new'}
        with patch('rideworks.race_results.matching_activities', return_value=[candidate]):
            outcome = race.commit_rows(store, identity, [item], visible_count=1, visible_confirmed=True)
        print('New results added:', outcome['added'])
        print('Active associations:', store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0])
PY
```

JIT section B.7 requires wrong-Activity conflicts to be surfaced and removed
before saving. Because recurring races can share event names and times,
widening the date comparison alone may also block different legitimate races.
**Analyst decision requested:** specify a safe cross-import identity and
resolution workflow for uncertain old attachments, including how to distinguish
different recurring races without silently transferring links or requiring
deletion of unrelated results. No policy or bypass is assumed here.

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
  Manual selection and skipping are rejected. The same-day/same-time
  possible-old-attachment check has the blocking limitation described above.
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

- `.venv/bin/python -m unittest discover -s tests` — 604 tests passed before
  the last test and failure-accounting edits; the final full suite was not run
  after finding the blocker.
- `.venv/bin/python -m unittest discover -s tests -p 'test_race*.py'` — 47
  tests passed after those edits, using synthetic data and mocked API calls.
- Mock-only browser checks: 12 import/reconciliation checks, six Activity
  value/layout checks, removal confirmation, and a mobile crop-comparison
  check passed on a disposable store. A prior assertion incorrectly used
  `innerText` for CSS-generated mobile labels; the values were verified with
  actual element selectors and the desktop headings separately.
- `.venv/bin/python reports/RACE-02/row_probe.py` — produced the counts above.
- `git diff --check` — passed.
- Pylance syntax checks passed for the new section/reconciliation modules,
  extraction module and section tests; `node --check` passed for both review
  and synthetic browser scripts.
- No live model call, real screenshot, production database or browser-based
  Owner test was used. The checks do not establish extraction accuracy,
  account/model availability, or Gate 1 acceptance.

## Migration safety

The additive migrations retain existing active results, imports,
screenshots and revision history, and adds a removal audit record rather than
deleting source evidence. Migrations and rollback checks use disposable stores
only. Before any separately authorized production activation, stop database
writers and verify a consistent backup of the complete current data directory;
keep the matching old code and configuration. Old code rejects newer schema
versions, and restoring an older database after new writes would discard those
writes without a separate reconciliation decision.
