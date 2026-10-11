# AR-UI-01 — Activity Review visual redesign

**Status:** **Owner-approved visual direction, 2026-10-11.** Implementation pending.
**Scope:** Existing **Activity Review / Ride Details** (`/activities/<id>`), not the Activities list/table and not an app-wide redesign.
**Owner instruction:** After reviewing the [interactive HTML concept](../mockups/activity-review-ui-concept.html), the Owner said **"I like it, please make it so."**
**Reference precedence:** This HTML now controls the **Activity Review layout and visual hierarchy** over the older `docs/mockups/activity-review.png`; that earlier image remains historical background, not an active conflicting visual requirement. Mock data, generated traces, links and the fake sidebar in HTML remain illustration only. Accepted Phase 1–5/PC-01 behavior and provenance still control function.

## 1. What we are improving

The current ride-details page is rich in information but visually flat and fragmented: title, metrics, workout context, current next ride, timeseries, power-duration comparison, best-20 and source provenance are separate boxes with little hierarchy. The image also shows an oversized vertically stretched experience and undersized ride charts.

**Desired reading order:** (1) **Ride identity and four leading metrics**, (2) **large ride Power/HR analysis with concise supplemental ride summary, workout context and current next ride**, (3) **full-width power-duration curve and inspectable prior-period comparisons**, (4) **compact best efforts / 20-min baseline**, (5) **collapsed detailed data-source and calculation evidence**. One useful page scroll with quick section anchors. The Owner-approved HTML is the visual reference, not literal copy/paste production code.

## 2. Accepted screen composition

- Preserve existing RideWorks **app header, navigation routes, brand** and real Activity URL. Use the reference's generous desktop content width, softer blue/white canvas, consistent typography scale, rounded card spacing and stronger hierarchy **within Activity Review**. Do not replace global navigation, brand artwork, or restyle unrelated pages as a side effect.
- **Hero:** breadcrumb, actual activity title and source/type/date context, two unobtrusive functional jump links and four summary metrics (elapsed duration, distance, avg power, avg HR), aligned and easy to scan. Numeric data follows original source/availability semantics; absent values display **Unavailable**, not a placeholder copied from mockup. On FIT and API cases disclose summary's data source accurately.
- **Local sticky section links** to Overview, Power & HR, Power Curve, Best Efforts and Source Evidence. Work with actual fragment IDs and desktop/mobile positioning. Links should not obscure destinations under fixed app header. Do not invent a full new global nav scheme.
- **Primary analysis:** substantially larger true-source Power/HR SVG than current 260px (~350–400px desktop and legible ~300–330px small screens, subject to layout tests). Retain real native/API data, gap behavior, alignment, hover/touch/keyboard sample inspection, honest missing HR/power states and times/units. Independent checked-by-default Power and HR visibility toggles are allowed by the approved concept; if built, they must really affect line/markers and readout without changing raw stream or chart scale incorrectly. No synthetic trace in production.
- **Sidebar/companion cards:** compact Ride Summary, **Workout Context** with actual inferred/confirmed/manual classification and working correction/save, and **Current Next Ride** using the existing live planner output with correct date/type/conditional caveat. Never imply that current recommendation was historically planned for the selected older activity. On smaller screens these stack in a coherent order, without hiding real content.
- **Power Curve:** prominent full-width section, actual PC-01 SVG interaction and provenance, selected ride vs **its preceding six weeks by default**, historical period selector, chart and readable selected-duration comparison. Keep all actual PC-01 source/coverage/unavailable behaviors, calculated-anchor restrictions and contributor Activity links. The mockup may place a readout beside the chart on desktop; implement as an adaptation of the existing PC-01 live readouts/DOM, not a reimplementation of numerical/source policy. Do not invent greater sample accuracy or a new power grid.
- **Best Efforts:** compact, readable best 20-minute value, accepted current-vs-prior-six-week comparison, links and provenance. Avoid duplicating the same best-20 comparison prominently in multiple adjacent cards; preserve **the existing distinct best-20 prior period convention** even though the Power Curve's previous-six-week boundary differs (the older recent-context panel uses exclusive lower bound). Label them accurately. Additional "3 best efforts" values in the HTML are illustrative only and should not become fabricated calculated metrics. You may use just accepted best-20 + the prior comparison until further metrics exist.
- **Source Evidence:** group native FIT, Strava summaries, API streams, calculation window details, and unavailable/ambiguous source issues under a visible descriptive section heading with collapsed **semantic `details`**; all existing identities, timestamps, extraction/mapping provenance, summary-vs-stream origins, metadata and error states must remain inspectable. Do not hide all limitations behind ambiguous green badges. Avoid duplicate source tables or drop properties in the process.
- **Not every ride is rich:** preserve native FIT rich review, current Strava-API-with-stream rich review, Strava export/API metadata/thin pages, original source disagreement/error states, and Outdoor Rides. A missing or ineligible chart should show an explicit supported empty/availability state in the new visual structure; not an empty white chart pretending no effort.
- **Responsive:** evaluate widescreen (1440 desktop), laptop (1024), tablet (768), mobile 390 and **320 CSS px**. No horizontal overflow or clipped navigation, metrics, duration tick labels, buttons, source rows or chart legend. On mobile charts remain substantially legible, with deliberate readable axes; no simply scaling down 900px SVG screenshots.

## 3. Reusable RideWorks design language — start here, not everywhere

This change is the **first implementation/reference** for a possible consistent page language. Shared candidate tokens/patterns: `--rw-ink`, `--rw-blue`, `--rw-teal`, `--rw-canvas`, muted/stroke colors; **14px rounded cards**, ~18–24px inner padding, an aligned hero/stats strip, restrained use of bold/warnings, readable 19px section titles, small source captions, clear interactive legends, accessible readout panels, descriptive section anchors and collapsible evidence.

**Implementation boundary:** Keep these under a scoped wrapper/stylesheet or additive classes where possible; minimize unscoped selectors and do not globally switch chart sizing or navigation. A small deliberate set of optional shared CSS variables is fine if visual effects on existing pages are verified. This is a candidate visual system for future page-by-page acceptance, **not** an authorization to redesign Home, Activities list, Performance, Training State or Plan now. A separate later task can apply the agreed language elsewhere.

## 4. Source-derived / illustrative distinction

**Actual/source data:** all timestamps, power/HR samples, displayed watts/bpm, ride type, class correction, next ride from Plan, summary origin, 20-minute mean and source, PC-01 baseline and contributor links come solely from already accepted RideWorks models and saved rider overrides.

**Mockup-only examples:** `Evening Circuit Race`, 173 W, any screenshot's generated waveform, 196/201 W bests, a mock "confirmed" pill, a specific recommendation text and fake in-page navigation href are placeholders only. Never copy such values or strings as real ride evidence or assume a missing classification has been confirmed.

## 5. Interaction and acceptance examples

- A real recent **API virtual race** with power and HR shows source-supplied averages, full interactive stream chart, current classification correction and live next ride, actual curve vs prior 42-day evidence, accepted best-20 and collapsible API provenance. Every link and form works, including after sync.
- A native FIT-backed virtual ride has the equivalent responsive rich layout, valid native source explanation and native stream/time series. Missing HR does not hide qualifying power; null/broken record gaps are not bridged.
- An activity with only summary metadata does not get fictitious charts or a "measured power" badge. All source observations remain accessible.
- An Outdoor Ride without trusted Power Curve data retains its available summary and supported ride charts, while PC-01 displays the correct eligibility explanation.
- An older ride's Power Curve compares against **its own prior 42 days**, never today's prior window. Best-20 prior six-week comparison continues using its separately accepted convention.
- The selected user classification is shown from actual state, and the correction action continues to work with safe/no unintended source changes. The current Next Ride card stays current and is not framed as a historical instruction.
- Interactive sections/tabs/anchors behave on keyboard/mobile. No new configuration or pipeline is required.

**Implementation scope guard:** This task is presentation/interaction only; changes to power metrics, training stress, source eligibility, sync, FTP, period membership, race inference, and planning rules require an explicit separate decision. Reuse current code/components; no new source ingestion or artwork assets are needed.

## 6. Acceptance process

**HARD — Analyst Gate 1:** verify code/DOM integration and source identity, regression for all current review modes, desktop/mobile Chromium capture comparison with approved HTML, keyboard/touch, full regression and preservation of accepted outputs. Report departures from mockup. 
**HARD — Owner Gate 2:** the Owner reviews the running redesigned Activity Review, not an isolated mockup. Only after this review can the implementation task be marked done and merged.

The present Owner approval is **approval of the visual reference and direction**, **not** acceptance of Dex's future implementation. Phase 6 remains deferred.
