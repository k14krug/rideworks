# RACE-01 implementation and synthetic verification

## Implementation

RideWorks accepts a PNG, JPEG or WebP race screenshot and discloses that
extraction sends it to OpenAI and incurs API charges. The server validates the
image, requests strict structured output, retains the original locally, and
stages the extracted rows for correction. Extraction does not create confirmed
race results or activities.

Review supports a screenshot display timezone, same-day activity candidates
with source context, conservative automatic suggestions, explicit activity
selection, skip/confirm, duplicate detection and explicit approval of changed
results. Confirmation is transactional and stores race-reported watts
separately from FIT and other activity measurements. An additive SQLite
migration links accepted results and their revision history to existing
activities and screenshot/model/prompt/schema provenance. Race Results and
Activity Review link to one another.

The default model is `gpt-4o-mini`, with a configurable model and upload limit.
Request construction uses the OpenAI Responses API image input and strict
JSON schema documented by OpenAI:
[images and vision](https://developers.openai.com/api/docs/guides/images-vision),
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
and [model capabilities](https://developers.openai.com/api/docs/models/gpt-4o-mini).
Reported token usage and cost, when returned, are retained without assuming a
price. The original screenshot and extraction data remain in the private store.

## Verification

All verification used synthetic images, synthetic activities, and controlled
mock API responses. No personal screenshot or other personal activity data was
sent to OpenAI, and no live OpenAI request was made.

From the task worktree:

- `.venv/bin/python -m unittest discover -s tests -p test_race_results.py`:
  **14 tests passed**. Coverage includes strict request/schema construction,
  wrapped titles, group badges, signed/zero/missing score changes, watt-field
  distinctions, 100/101 row boundary, image types and failures, missing key,
  HTTP error and timeout, retained originals, HTML escaping, review correction,
  idempotence, changed-result approval, transaction rollback, preservation of
  FIT evidence, matching ambiguity/timezones, and migration rollback.
- `.venv/bin/python -m unittest discover -s tests`: **574 tests passed**.
- `.venv/bin/python -m compileall -q rideworks tools/preview_race_results.py`,
  `node --check tools/verify_race_results_browser.js`, and `git diff --check`
  passed.
- `tools/preview_race_results.py` and `tools/verify_race_results_browser.js`
  exercised **12 browser checks** with a generated 33-row synthetic image and
  three mocked extraction rows, at 1440 px and 390 px. The checks covered
  disclosure, upload, preview, editing, matching, confirmation, navigation,
  date sorting and mobile overflow. They do not measure OCR accuracy.

For a disposable browser rerun, create a new empty directory and start the
mock-only preview with
`.venv/bin/python tools/preview_race_results.py --data-dir <empty-directory> --port 18893`.
Open `http://127.0.0.1:18893/race-results` in Playwright and run
`tools/verify_race_results_browser.js` with the repository's `run-code`
workflow. Stop the preview after the check.

## Review boundary and limitations

**HARD — Analyst:** review source/provenance, matching, deduplication,
privacy/API boundary, errors and costs. The implementation PR remains draft.
Real recognition accuracy, API availability and actual billed cost are
**unverified** and belong to the Owner-operated live UI test at HARD — Owner.
No production deployment is authorized by this task.
