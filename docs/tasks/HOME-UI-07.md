# HOME-UI-07 — Solid prior-year mileage lines

**Status:** Pending after PC-04 closeout and integration. Owner requested this as the next task.

## Requirements Used

[Product requirements](../PRODUCT_REQUIREMENTS.md), the accepted Home Mileage by Year card, and the Owner's Dev screenshot and feedback: the two prior-year dotted/dashed lines are hard to read; use solid lines.

## Scope and checks

On Home → Mileage by Year only, render both prior-year series as solid strokes. Keep the existing colors and line widths, the current-year emphasis, the stepped paths, legend, labels, annual totals and goal information. Keep interactions, layout, other mileage charts and all calculations unchanged. Use the existing annual-line styles; no new settings, data work or chart refactor.

Check desktop and a narrow viewport in Dev. Confirm both prior-year paths are solid and distinguishable from the current-year line, year labels still match their series, and the data, labels and unrelated mileage chart styling are unchanged. Keep verification proportional: record computed stroke styles and a visual check; no archive rebuild or full-suite rerun for a CSS-only change unless scope expands.

**Allowed Invocation: `/TASK only`.** Start with `/TASK HOME-UI-07` after PC-04 is accepted and integrated on refreshed main and no other task is active. Use a separate draft PR. Stop at HARD Analyst review, then HARD Owner running-Dev review. No merge or deployment authorized.
