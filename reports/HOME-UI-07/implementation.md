# HOME-UI-07 verification

The Home Mileage by Year chart's two prior-year paths now use solid strokes.
Their existing colors and widths and the emphasized current-year path remain
unchanged.

Chromium checks used a disposable Dev data copy at 1440 px and 390 px. Computed
styles at both widths were:

| Series | Stroke | Width | Dash array |
| --- | --- | --- | --- |
| Current | `rgb(37, 99, 235)` | `2.5px` | `none` |
| Previous | `rgb(217, 119, 6)` | `2px` | `none` |
| Two years prior | `rgb(13, 148, 136)` | `2px` | `none` |

Before the change, the previous and two-years-prior dash arrays were `6px, 3px`
and `2px, 3px` respectively. Visual inspection at both widths confirmed that
the solid lines remain distinguishable. Each year label and legend color matched
its corresponding series. Before/after comparison confirmed unchanged SVG
markup, stepped paths, legend and goal text, and the unrelated weekly mileage
chart's markup and computed dash style. Neither viewport overflowed.
Private screenshots remain outside Git. No data rebuild or full test suite was
run for this CSS-only change.

Stop at HARD Analyst review; Owner running-Dev review follows. No deployment is
authorized.
