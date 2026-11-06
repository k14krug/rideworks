# RACE-02 investigation: overlap reconciliation

## Status

Stopped before implementation Gate 1 under the JIT's condition for overlap
that cannot be distinguished safely. No Race Results implementation changes
or production-data changes have been made. The Owner-authorized VS Code
settings were committed separately on the task branch.

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

## Verification

Before the experiments, `.venv/bin/python -m unittest discover -s tests -p
test_race_results.py` passed all 20 existing tests. The experimental probes
were disposable synthetic Pillow images and mocked row observations; they do
not measure real model accuracy or establish general image behavior.

## Review needed

The Analyst should determine how to establish physical row identity and
coverage independently enough to merge repeated observations safely, and what
diagnostic to show when that evidence is unavailable, consistent with the
Owner's automatic whole-batch rule. A reliable boundary detector with
fail-closed handling is one possible direction but has not been validated.
Do not silently merge by text, model position, or guessed confidence.
