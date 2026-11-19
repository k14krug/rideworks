(() => {
  const form = document.getElementById('history-import-form');
  if (!form) return;

  const paste = document.getElementById('history-paste');
  const status = document.getElementById('history-progress');
  const preview = document.getElementById('history-preview');
  const date = /^(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|[A-Z][a-z]{2} [0-9]{1,2}, [0-9]{4})$/;
  const duration = /^(?:[0-9]{1,3}:)?[0-9]{1,3}:[0-9]{2}$/;
  const activity = /^https:\/\/(?:www\.)?strava\.com\/activities\/([1-9][0-9]{0,18})\/?$/;
  const effortMetric = /^(?:[0-9]+(?:\.[0-9]+)?)\s*(?:W(?:svg)?|bpm)$/;
  const cellText = cell => cell.textContent.replace(/\s+/g, ' ').trim();

  function clipboardRows(html) {
    if (!html || html.length > 256000) return [];
    // Template contents stay inert. Only extracted strings enter the textarea.
    const template = document.createElement('template');
    template.innerHTML = html;
    const rows = [];
    let columns = null;
    for (const row of template.content.querySelectorAll('tr')) {
      const cells = Array.from(row.cells);
      const values = cells.map(cellText);
      if (!values.some(Boolean)) continue;
      if (values.includes('Date') && values.at(-1) === 'Time') {
        columns = [values.indexOf('HR'), values.indexOf('Power')].filter(index => index >= 0);
        continue;
      }

      const dates = cells.filter(cell => date.test(cellText(cell)));
      const time = values.at(-1);
      if (dates.length !== 1 || !duration.test(time)) {
        // Keep the original plain-text paste if any row could not be extracted.
        return [];
      }

      const ids = new Set();
      for (const link of dates[0].querySelectorAll('a[href]')) {
        const match = activity.exec(link.getAttribute('href'));
        if (match && BigInt(match[1]) <= 9223372036854775807n) ids.add(match[1]);
      }
      const canonicalLink = ids.size === 1 ? 'https://www.strava.com/activities/' + [...ids][0] : '';
      const metricCells = columns ? columns.map(index => values[index]) : values.slice(cells.indexOf(dates[0]) + 1, -1);
      const metrics = metricCells.filter(value => effortMetric.test(value));
      rows.push([cellText(dates[0]), canonicalLink, ...metrics, time].filter(Boolean).join('\t'));
    }
    return rows;
  }

  paste.addEventListener('paste', event => {
    const rows = clipboardRows(event.clipboardData?.getData('text/html'));
    if (!rows.length) return;
    const value = rows.join('\n');
    const {selectionStart: start, selectionEnd: end} = paste;
    const before = start > 0 && paste.value[start - 1] !== '\n' ? '\n' : '';
    const after = end < paste.value.length && paste.value[end] !== '\n' ? '\n' : '';
    if (paste.value.length - (end - start) + before.length + value.length + after.length > paste.maxLength) return;
    event.preventDefault();
    paste.setRangeText(before + value + after, start, end, 'end');
  });

  const previousStatus = status.textContent;
  form.addEventListener('submit', event => {
    if (form.getAttribute('aria-busy') === 'true') {
      event.preventDefault();
      return;
    }
    form.setAttribute('aria-busy', 'true');
    status.textContent = event.submitter?.value === 'api' ? 'Checking Strava for saved efforts…' : 'Reading pasted results…';
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) {
      form.removeAttribute('aria-busy');
      status.textContent = previousStatus;
    }
  });

  if (preview) preview.focus();
  else if (previousStatus) status.scrollIntoView({block: 'nearest'});
})();
