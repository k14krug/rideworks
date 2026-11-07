# RACE-02 investigation: source-row ownership and independent work

## Status

The Analyst reviewed the earlier overlap stop and authorized a source-row
ownership experiment and independent work on the other RACE-02 requirements;
see [issue #60](https://github.com/k14krug/rideworks/issues/60). The new
source-pixel probe below still gives unsafe row counts, so the task is blocked
again pending Analyst guidance. Gate 1 is not complete. The branch is
work-in-progress and must not be used for real imports, merged or deployed.
No production data was accessed or changed.

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
rejecting valid variants. The safe fallback is to reject the whole screenshot
with a clear row-boundary diagnostic before making an API request or changing
confirmed results, and invite the Owner to provide a clearer screenshot.
This fallback is not yet implemented and does not by itself satisfy the JIT's
sectioning acceptance criteria.

## Independent work in progress

- An experimental automatic matcher checks date, local time, timezone/DST,
  distinctive title words, explicit stage conflicts, candidate uniqueness and
  collisions; the review and final transaction recompute the full batch.
  Manual selection and skipping are rejected. The same-day/same-time
  possible-old-attachment check is conservative but does not establish a
  universal identity across OCR errors or different screenshots; that case
  needs further design and tests.
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
- Section planning, section provenance, attempt/retry accounting (including
  failed requests), fail-closed extraction, row-coverage validation, and
  complete overlapping-section reconciliation are **not implemented**. The
  current single-image path cannot prove source-row completeness. Do not use
  this work-in-progress branch for real screenshot imports.

## Verification

- `.venv/bin/python -m unittest discover -s tests` — 596 tests passed using
  synthetic data, including migration rollback and batch-matching tests.
- `.venv/bin/python reports/RACE-02/row_probe.py` — produced the counts above.
- `git diff --check` — passed.
- No live model call, real screenshot, production database or browser-based
  Owner test was used. The tests do not establish extraction accuracy,
  account/model availability, section coverage or Gate 1 acceptance.

## Analyst guidance

The Analyst directed source-row ownership before model extraction, with each
row owned by exactly one section and overlapping pixels used only as context.
Uncertain row boundaries or output coverage must block the batch. The proposed
pixel-based planner remains an experiment, not a validated detector.

## Migration safety

The planned additive migration retains existing active results, imports,
screenshots and revision history, and adds a removal audit record rather than
deleting source evidence. Migrations and rollback checks use disposable stores
only. Before any separately authorized production activation, stop database
writers and verify a consistent backup of the complete current data directory;
keep the matching old code and configuration. Old code rejects newer schema
versions, and restoring an older database after new writes would discard those
writes without a separate reconciliation decision.
