# RACE-01 — Zwift Racing Profile screenshot import and linked Race Results

**Status:** Pending implementation. Owner feature direction confirmed 2026-11-05.
**Scope:** A bounded RideWorks feature, not Zwift authentication/scraping or a new activity importer.
**Priority:** Next Owner-chosen task; NAV-01 merged and accepted 2026-11-05. RACE-01 may start only on an explicit permitted Owner invocation.

## 1. Purpose

Enable the rider to upload a screenshot of the Zwift Racing Profile (ZRP) race-results table to RideWorks. An image-capable OpenAI API model extracts a narrow structured set of results. The app shows an editable review/matching preview and, only after confirmation, attaches each result to an **already-recorded RideWorks activity**. A Race Results page and the corresponding Activity Review show the imported metadata. **Never create an activity from a race result.**

The owner already uses the OpenAI API in other projects; prioritize low cost, no subscription/connector work, and no mandatory manual ChatGPT/JSON workflow.

## 2. Requirements used

- Owner decisions in the 2026-11-05 Race Results discussion: direct screenshot upload; fields are date, event, finish, average watts, Racing Score including change, and visible race group; retain start time for matching; import must attach to existing rides; consistent RideWorks Home visual language; manual JSON paste is optional fallback.
- [Product requirements](../PRODUCT_REQUIREMENTS.md): PR-001/002 (personal/product-first), PR-003–006 (durable history, distinct evidence, preservation, provenance), PR-009/012 (competing source evidence, missing data), PR-013/014 (accepted UI references/branding).
- [Durable activity/source model](../design/DESIGN-001.md), [source-centered storage/import design](../design/DESIGN-002.md), current activities and Activity Review code, [approved mockups](../mockups/README.md).
- [Race Results visual reference](../mockups/race-results-ui-concept.html) is **synthetic** and directional. Use the *current running app's Home/sidebar/cards/table styles* as the primary styling baseline, not invented metric values. No race screenshot or personal activity data is committed with this task.

## 3. Execution control

**Allowed Invocation: `/TASK or /AUTOTASK`.** Owner approval of the feature is established, but **no execution begins without an explicit permitted invocation** and fresh repository sync under `AGENTS.md`. NAV-01 has been accepted and merged. Resume RACE-01 from an authorized clean worktree without modifying or deleting the reported untracked `.vscode/settings.json` in the original checkout.

- **Gate 0 — Owner product direction: resolved.** Direct screenshot extraction, confirmation, existing-ride linking and Race Results are approved scope.
- **Gate 1 — HARD — Analyst:** after implementation and **synthetic/offline** tests, stop for source/provenance, deduplication, privacy/API-boundary, error/cost handling and activity-matching review. Leave PR draft. **A call to OpenAI with the Owner's personal screenshot is not required and is not authorized for Dex's verification.**
- **Gate 2 — HARD — Owner:** the Owner operates the running local RideWorks UI and, if desired, uploads their own real screenshot and explicitly triggers extraction using their configured OpenAI API key. Check actual recognition, cost/usage, review flow, ride matching and visual fit. Dex may inspect sanitized outcome reports but must not independently upload, transmit, or commit the Owner's screenshot. No merge or deployment without required acceptance.
- Do not treat an AI model's syntactically valid JSON as fact. Confidence must come from checks and human confirmation.

## 4. Scope / user journey

1. **Race Results page** reachable from sidebar near Activities, using current shell/navigation design. Header includes **Import Screenshot**.
2. **Upload:** PNG/JPEG/WebP accepted with a reasonable configurable upload size limit and clear validation/errors. Preserve uploaded original image and import/source identity **locally**, not in Git. Do not log image bytes or sensitive prompts/keys.
3. **Extraction:** a single-purpose server-side OpenAI vision request with a versioned prompt and strict JSON schema; read API key only from existing server configuration. Model choice/configurable; start with an inexpensive current image-capable model and avoid hardcoding a pricing assumption. Record usage/cost estimate when returned. **During Dex development, use a stub/mock API response and a wholly synthetic race-table image to verify the request/response and extraction pipeline without external transmission of personal screenshots.** The UI must plainly tell the Owner that clicking Extract sends the uploaded image to OpenAI and incurs API charges. A real extraction and observed cost/accuracy check belongs to the Owner-run Gate 2 test, not pre-implementation verification.
4. **Review:** editable extracted rows with image reference/preview, validation flags, existing/changed/duplicate state, proposed activity matches, and an explicit **Confirm Import** action. Extraction alone never writes approved race records.
5. **Matching:** link to existing RideWorks activity identity using local date/time, Zwift/virtual-ride evidence, title/event similarity and watts as supporting clues. Auto-link only when unambiguous; otherwise user picks a specific ride. No match -> pending/skip, **not a fabricated activity**. Avoid asserting exact watt equivalence between FIT and Zwift display.
6. **Commit:** idempotent, transactional where existing store supports it; one accepted race result per linked activity unless the real source evidence demonstrates an exceptional case (stop-and-report). Reimports distinguish unchanged duplicate from changed result and require review/explicit approval before replacing existing values. Rejected/uncertain rows stay outside final results.
7. **Display:** newest-first table showing date, event, race group, finish, avg watts (source-reported), Racing Score and signed score change, plus link to underlying activity. Show race metadata on that activity's detail/review page and a link back to Race Results. Optional simple Racing Score chronology and count cards computed **only from saved verified results**; chart and summaries must not delay importer correctness.
8. **Optional:** manual JSON paste can reuse the exact same schema-validation, review, matching, and commit pipeline. It is not mandatory for v1 if it adds meaningful scope.

## 5. Extraction contract

The model returns JSON shaped as `{"races":[...]}`. Each row has exactly these fields (nullable where unavailable):

| Field | Type | Extraction rule |
|---|---|---|
| `date` | `YYYY-MM-DD` or null | Local calendar date as displayed, don't infer UTC |
| `start_time` | `HH:MM` or null | Displayed clock time if readable; retain screenshot display timezone context; do not silently guess an offset |
| `event` | string or null | Full event name, joining wrapped lines, **not the route subtitle** |
| `race_group` | string or null | Badge beside the event, as shown (e.g. `0-210`, `160-270`) |
| `finish` | integer or null | `FINISH` column position, not medal icon |
| `avg_watts` | integer or null | **Top watt integer under WATTS/W/kg**; ignore W/kg and 20m/5m/1m/15s |
| `race_score` | integer or null | Larger integer in SCORE/Change; dashes/absent = null |
| `race_score_change` | signed integer or null | Green up = positive; red down = negative; explicit zero = 0; dash = null |

Example (illustrative format; do not commit rider's raw screenshot):

```json
{
  "races": [{
    "date": "2026-11-01",
    "start_time": "11:10",
    "event": "Demo Series - Stage 4",
    "race_group": "0-210",
    "finish": 9,
    "avg_watts": 161,
    "race_score": 184,
    "race_score_change": 1
  }]
}
```

**Draft extraction instruction (store centrally, version it; edit if validation warrants):**

> Read the Zwift Racing Profile screenshot. Extract every fully visible race-result table row, in screen order, into the supplied JSON schema. For each row extract date and clock time, full event title (join wrapped lines, exclude the route subtitle), race-group badge, finishing position, top integer watts from WATTS/W/kg, score and signed score change. Ignore route, distance, time/gap, watts/kg, and 20m/5m/1m/15s columns. Interpret up arrow as positive, down arrow as negative, explicit zero as zero, dash as null. Missing or unreadable values are null; do not guess, duplicate, merge or manufacture rows. Do not read the promo/series cards above the table as races.

Use server-side type/date checks, reasonably bounded event length, expected group form when readable, plausible nonnegative watts/score/finish (without false precision about score range), and untrusted-text handling. A valid schema does not guarantee faithful OCR; review remains required. Tall screenshots with small fonts may need deterministic cropping into overlapping sections, extraction, and overlap de-duplication; **start with synthetic fixtures and avoid added complexity until the Owner-run live test establishes a concrete need**. Leave the full-resolution original intact.

## 6. Data/provenance and matching

- Inspect existing Activity/Source/store conventions before choosing persistence schema, files and routes. Do not create a separate activity database or new frontend stack.
- Store confirmed race result **by linked activity ID**, plus source type (`zwift_racing_profile_screenshot`), source image reference, extraction/model/prompt/schema version, import timestamp and any corrected fields when practical. The screenshot is source evidence, not a measured-power recording.
- Source `avg_watts` is Zwift race-result display data and must not overwrite recorded FIT power or RideWorks-computed averages.
- Respect local-date versus UTC conversions. Extracting a screenshot time alone does not establish its timezone; allow the rider to supply/confirm display timezone if matching is uncertain.
- Show candidate-match evidence without inventing match confidence scores. Resolve ambiguous, multiple, missing or same-day/same-title cases explicitly.
- If a screenshot contains old and new results, recognize previously attached activities and avoid duplicating them; do not overwrite changed values silently.
- No external Zwift session, account/password storage, Zwift API automation or scraping.

## 7. UI reference and review

Reuse the existing RideWorks left sidebar, Home visual palette, cards, fonts, compact tables and linked activity titles. The synthetic [HTML reference](../mockups/race-results-ui-concept.html) illustrates two states: race history and import/review. It is **not** a pixel requirement or authority for sample numbers.

Results: header and clear Import action; compact summary only when real data supports it; race table with useful sorting/paging; score chart optional.

Import/review: upload area; extraction status/errors; editable fields; source image access; activity-match link/select; states for new, already imported, changed, ambiguous and invalid; explicit skip/confirm; post-import count summary. Avoid excessive layout additions if actual current UI already has suitable components.

## 8. Explicit non-goals

No Zwift login, undocumented endpoint scraping, external ZwiftRacing/ZwiftPower import, historical API harvesting, live synchronization, new ride creation, updating FIT records or actual power measurements, automatic race classification in the training planner, race predictions, universal multi-athlete configuration, new frontend framework, chat system, recurring automated API calls, or deployment. No direct writes on model response.

## 9. Inputs and local-data expectations

**No personal screenshot is required from Dex to start or finish implementation for Analyst Gate 1.** Dex must not transmit an Owner screenshot to an external service or commit it. Use fully synthetic screenshots and mock/stub OpenAI responses for parser, prompt/schema, validation, upload, match, idempotency, and UI tests. The Owner will provide a real screenshot only through the **running RideWorks upload UI** at HARD — Owner Gate 2, where the Owner chooses to initiate the API request; that live integration test is an explicit part of the product's intended behavior. Retain real screenshot, real response and related activity data locally only; Git reports should contain sanitized outcome counts and measured API usage/cost if the Owner chooses to share them. In implementation, prefer existing API credential/config conventions; if absent, use a simple environment-backed server-only setting rather than introducing secrets infrastructure.

## 10. Implementation sequence (engineering discretion)

1. Inspect current navigation, page templates/components, database identifiers and source-archive paths, Activity Review routes, existing tests, secrets configuration.
2. Add narrow data model and local screenshot import staging/provenance mechanism.
3. Add server-side extraction with configurable model, strict schema, upload safety, errors/timeouts, usage recording.
4. Add validation/review/matching and idempotent commit, including field corrections.
5. Add Race Results and Activity Review links; optional chart/summary if inexpensive.
6. Before HARD — Analyst: run unit/integration tests with synthetic screenshot rows, mocked API replies, and browser flows; include an entirely synthetic dense/tall screenshot as practical. Verify outbound API payload construction by mocks, **not by transmitting the Owner's screenshot**. After the Analyst accepts this implementation boundary, the Owner may test the actual real screenshot at HARD — Owner Gate 2 through the local app, then report observed accuracy/usage and decide whether prompt/cropping refinements are needed.

## 11. Verification / acceptance criteria

- [ ] Upload returns an editable preview **without saving a confirmed race result**.
- [ ] **Gate 1 synthetic verification:** test all eight fields against synthetic screenshot rows and controlled mock API JSON. Verify prompt/schema handling, editable review and corrections for wrapped titles, distinct group badges, signed red/green score arrows, explicit zero, dash/null, and 20m vs avg watts confusion. Avoid claiming actual model transcription accuracy from mocks.
- [ ] **Gate 2 Owner live verification:** Owner initiates the real screenshot extraction from the running RideWorks UI using their own configured API key, reviews the returned rows against the screenshot, corrects/links records, and reports any observed misses/errors. Real accuracy and actual billed cost remain **unverified** until this step; their absence is not a Gate 1 implementation blocker.
- [ ] Invalid JSON/schema, malformed image, huge image, non-image upload, API failure/timeout and missing API key yield understandable recoverable errors without corrupting history or leaking secrets.
- [ ] Reimport of the same screenshot yields no duplicate race results or duplicate rides. Edited/corrected results require explicit review before replacement.
- [ ] Every confirmed race result references a real activity; ambiguous and unmatched results cannot be committed as linked without review. No phantom/placeholder rides.
- [ ] Same-day multiple Virtual Rides and event-timezone discrepancies are tested without false auto-linking.
- [ ] Source screenshot retained locally with provenance. FIT/source measurements are unchanged; race-reported watts remain separately labeled.
- [ ] Race Results table shows only confirmed data and links to Activity Review. Activity Review links back correctly.
- [ ] Real aggregated cards/score chart never use mock values. Missing score/change display as unknown, not zero.
- [ ] Test suite relevant to importer, store, routes and activity review passes; focused browser verification at desktop and smaller width. Provide a concise source-neutral review report under `reports/RACE-01/` with model/configuration, **synthetic** test coverage, commands/results and limitations. Label live recognition accuracy and billed costs as **pending Owner Gate 2** rather than inventing them.
- [ ] Update `TASKS.md`/`STATUS.md` per lifecycle. Work in task branch and draft PR; stop at HARD — Analyst, then HARD — Owner running-UI review. No premature merge/deploy.

## 12. Stop and report

Stop if synthetic extraction/schema requirements cannot be implemented; actual observed race/group semantics differ from the proposed fields; activity matching cannot be made safe with existing activity evidence; keeping source images requires a new privacy choice; **Owner-run Gate 2** reveals unacceptably high real error rates or costs; current API capabilities or terms prevent planned behavior; or a larger schema/UI/workflow change becomes necessary. **Dex's inability to transmit the Owner's screenshot is not a blocker for implementation or Analyst Gate 1.** Propose the smallest remedy and request review; do not silently broaden scope.
