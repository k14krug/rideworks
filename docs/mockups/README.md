# Approved RideWorks UI Mockups

These images are approved product-direction references for **RideWorks**.

- `activity-review.png` — original approved Activity Review visual reference; **historical design background, superseded for Activity Review layout by the approved HTML concept below**.
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


## Owner-approved Activity Review concept (implementation pending)

- [`activity-review-ui-concept.html`](activity-review-ui-concept.html) — **Owner-approved visual direction** for the existing Activity Review / Ride Details page, 2026-10-11. The Owner reviewed it and said **“I like it, please make it so.”** This supersedes the older `activity-review.png` for Ride Details layout. Download/open as a standalone HTML file in Chromium to inspect the actual presentation (GitHub's source view does not execute the mockup). It includes **synthetic** graphs and ride values, functioning demonstration controls, a reorganized hierarchy, and CSS design tokens intended to inform later page-by-page improvements.

**Review boundary:** This concept is approved as the controlling **Ride Details visual reference**, and its implementation is scoped in [AR-UI-01 design](../design/AR-UI-01-activity-review-redesign.md), [Dex JIT](../tasks/AR-UI-01.md), and [issue #29](https://github.com/k14krug/rideworks/issues/29). It is **not a production code drop, numerical model, final running-app acceptance, or permission for a site-wide restyle**. Dex must use the real RideWorks source/Power Curve, best-20, activity classification, Plan and stream components; all mock graphs and numbers are synthetic. Reusable tokens (hero/stat strip, section anchors, card spacing, responsive charts, evidence disclosures) are candidates for later per-page adoption, not a requirement to immediately change Home/Plan/Performance. Owner's running-app review remains required before final task acceptance.
