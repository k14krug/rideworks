# Approved RideWorks UI Mockups

These images are approved product-direction references for **RideWorks**.

- `activity-review.png` — preferred visual/layout reference for the Activity Review screen.
- `dashboard.png` — preferred visual/layout reference for the Dashboard screen.

The controlling repository paths are:

- `docs/mockups/activity-review.png`
- `docs/mockups/dashboard.png`

The mockups guide overall page structure, information hierarchy, density, panel/card organization, and visual character. They do not freeze every pixel, color, spacing value, label, or component detail. Capabilities that do not yet exist should be omitted rather than represented by fake placeholders.

**Mockup content is illustrative.** Sample metric values, comparisons, trends, workout classifications, insight text, colors/arrows implying improvement, and other analytical statements shown in the images are not formulas, test fixtures, accepted training policy, or evidence that RideWorks must calculate those results. Controlling requirements and phase-specific analysis rules determine actual behavior.

The screenshots were created before the product name **RideWorks** was selected. Any older application title or wordmark visible inside the images is superseded. New RideWorks UI must use the RideWorks name consistently.

RideWorks also requires branded application iconography. The exact icon/mark artwork is not established by these mockups and must receive Owner visual approval before final Phase 1 UI acceptance.

Original image dimensions: 1448 × 1086 pixels.

SHA-256:
- `activity-review.png`: `373ff4c9ea1d197df9e60d40d40eb0b2087219fff8dcf73dcaf545da4296bd58`
- `dashboard.png`: `229f4ab5b2e45361cbe0e293eca66618daef950692093138826fe64732aec2b4`


## Exploratory UI concepts (not yet Owner-approved)

- [`activity-review-ui-concept.html`](activity-review-ui-concept.html) — **proposed** responsive Activity Review / Ride Details redesign, 2026-10-11. Download/open as a standalone HTML file in Chromium to inspect the actual presentation (GitHub's source view does not execute the mockup). It includes **synthetic** graphs and ride values, functioning demonstration controls, a reorganized hierarchy, and CSS design tokens intended to inform later page-by-page improvements.

**Review boundary:** This is a visual exploration, not an implementation task, accepted design override, data-model proposal or permission to restyle Home/Plan/Performance. The previously approved `activity-review.png` remains the controlling historical reference until the Owner specifically accepts a replacement. Dex should use this HTML for comparison **after Owner feedback**, preserving accepted source/Power Curve, best-20, activity classification, Plan and stream behavior. The built-in footer documents reusable layout patterns (hero/stat strip, section anchors, card spacing, responsive charts, evidence disclosures), which can be evaluated for other pages *separately*, without imposing an app-wide restyle now.
