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

{
    const form = document.getElementById('home-strava-sync');
    if (form) {
        const badge = document.getElementById('home-strava-check');
        const outcome = document.getElementById('home-sync-outcome');
        const button = form.querySelector('button');
        const nonce = form.elements.namedItem('nonce');
        const messages = {
            new: 'New rides on Strava',
            clear: 'No new rides in the checked window.',
            incomplete: 'Strava check incomplete. More activities may be available.',
            unavailable: 'Could not check for new rides.',
            disconnected: 'Strava connection unavailable. See Settings.',
            authorization: 'Strava authorization needs attention. See Settings.',
            rate_limited: 'Strava rate limit reached. Check again later.',
            busy: 'Strava is busy. Reload Home after the operation finishes.',
            superseded: 'Strava status changed. Reload Home to check again.',
        };
        const post = (url, fields, signal) => fetch(url, {
            method: 'POST', body: new URLSearchParams(fields), signal,
        });
        const check = new AbortController();
        const deadline = setTimeout(() => check.abort(), 15000);
        (async () => {
            try {
                const response = await post('/home/strava/check', {nonce: nonce.value}, check.signal);
                const result = response.ok ? await response.json() : {};
                if (!button.disabled) {
                    badge.textContent = messages[result.status] || messages.unavailable;
                    badge.classList.toggle('new-rides', result.status === 'new');
                }
            } catch {
                if (!button.disabled) badge.textContent = messages.unavailable;
            } finally {
                clearTimeout(deadline);
            }
        })();
        form.addEventListener('submit', async event => {
            event.preventDefault();
            if (button.disabled) return;
            button.disabled = true;
            check.abort();
            outcome.textContent = 'Syncing with Strava…';
            badge.textContent = '';
            badge.classList.remove('new-rides');
            try {
                const response = await post(form.action, {nonce: nonce.value, home: '1'});
                if (response.status === 409) {
                    outcome.textContent = 'Another Strava operation is running. Reload Home when it finishes.';
                } else if (!response.ok) {
                    outcome.textContent = 'Sync could not be confirmed. Reload Home to see the latest status.';
                } else {
                    const result = await response.json();
                    if (result.status === 'complete') {
                        location.reload();
                        return;
                    }
                    outcome.textContent = result.message;
                    nonce.value = result.nonce;
                    button.disabled = !result.connected;
                }
            } catch {
                outcome.textContent = 'The sync connection was interrupted. Reload Home to see the latest status.';
            }
        });
    }
}
