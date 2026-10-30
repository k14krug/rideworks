/* Immediate display of server-calculated mileage values; no chart arithmetic. */
(() => {
  'use strict';
  // Fit complete recent rows in the card; retain a scrollable fallback without JS.
  const recentList = document.querySelector('.home-recent-list');
  if (recentList) {
    const rows = [...recentList.querySelectorAll('.home-recent-row')];
    const fitRows = () => {
      for (const row of rows) row.hidden = true;
      for (const [index, row] of rows.entries()) {
        row.hidden = false;
        const bottom = recentList.getBoundingClientRect().bottom;
        // An exceptionally tall first row stays available through scrolling.
        if (index > 0 && row.getBoundingClientRect().bottom > bottom + 0.5) {
          row.hidden = true;
          break;
        }
      }
    };
    new ResizeObserver(fitRows).observe(recentList);
    window.addEventListener('resize', fitRows);
    fitRows();
  }
  const setup = (chart, tooltip, attribute, field) => {
    if (!chart || !tooltip) return;
    let focusedItem = null;
    const show = (item, event) => {
      tooltip.textContent = item.dataset[field];
      tooltip.hidden = false;
      const bounds = item.getBoundingClientRect();
      const x = event?.clientX ?? bounds.x + bounds.width / 2;
      const y = event?.clientY ?? bounds.y;
      const width = document.documentElement.clientWidth;
      tooltip.style.left = Math.max(4, Math.min(x + 10, width - tooltip.offsetWidth - 4)) + 'px';
      tooltip.style.top = Math.max(4, Math.min(y - tooltip.offsetHeight - 10, innerHeight - tooltip.offsetHeight - 4)) + 'px';
    };
    const hide = () => { tooltip.hidden = true; };
    for (const item of chart.querySelectorAll(attribute)) {
      item.addEventListener('pointerenter', event => show(item, event));
      item.addEventListener('pointermove', event => show(item, event));
      item.addEventListener('pointerleave', hide);
      item.addEventListener('pointercancel', hide);
      item.addEventListener('focus', () => { focusedItem = item; show(item); });
      item.addEventListener('blur', () => { focusedItem = null; hide(); });
      item.addEventListener('keydown', event => {
        if (event.key === 'Escape') { focusedItem = null; hide(); }
      });
    }
    // Focusing an offscreen point scrolls it into view; keep its readout positioned.
    const reposition = () => { if (focusedItem) show(focusedItem); else hide(); };
    window.addEventListener('scroll', reposition, {passive:true});
    window.addEventListener('resize', reposition);
  };
  setup(document.querySelector('#home-mileage-chart'), document.querySelector('#mileage-tooltip'), '[data-mileage-value]', 'mileageValue');
  setup(document.querySelector('#home-annual-chart'), document.querySelector('#annual-tooltip'), '[data-annual-value]', 'annualValue');
})();
