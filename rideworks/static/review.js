/* Local presentation only. Analysis values come from RideWorks unchanged. */
(() => {
  'use strict';
  const displayTimezone = document.documentElement.dataset.displayTimezone || 'America/Los_Angeles';
  document.querySelectorAll('[data-local-time]').forEach(element => {
    const date = new Date(element.dateTime);
    if (!Number.isFinite(date.getTime())) return;
    const formatted = new Intl.DateTimeFormat(undefined, {
      year: 'numeric', month: 'long', day: 'numeric', hour: 'numeric',
      minute: '2-digit', second: '2-digit', timeZoneName: 'short', timeZone: displayTimezone
    }).format(date);
    const offset = new Intl.DateTimeFormat(undefined, {timeZoneName: 'shortOffset', timeZone: displayTimezone})
      .formatToParts(date).find(part => part.type === 'timeZoneName').value;
    const parts = new Intl.DateTimeFormat('en-CA', {year:'numeric', month:'2-digit', day:'2-digit', timeZone: displayTimezone})
      .formatToParts(date);
    const part = type => parts.find(p => p.type === type).value;
    element.dataset.localDay = `${part('year')}-${part('month')}-${part('day')}`;
    element.dataset.timezone = displayTimezone;
    if (element.hasAttribute('data-compact-time')) {
      element.textContent = new Intl.DateTimeFormat(undefined, {
        year:'numeric', month:'short', day:'numeric', hour:'numeric', minute:'2-digit', timeZone: displayTimezone
      }).format(date);
    } else {
      element.textContent = `${formatted} (${offset})`;
    }
  });
  const nativePayload = document.getElementById('native-records');
  const payload = nativePayload || document.getElementById('api-stream-samples');
  const apiMode = !nativePayload;
  if (!payload) return;
  const records = JSON.parse(payload.textContent);
  const svg = document.getElementById('chart-svg');
  const container = document.getElementById('ride-chart');
  const readout = document.getElementById('sample-readout');
  const ns = 'http://www.w3.org/2000/svg';
  const controls = {power: document.getElementById('toggle-power'), heart_rate: document.getElementById('toggle-hr')};
  const visible = signal => !controls[signal] || controls[signal].checked;
  const available = signal => records.some(record => record[signal] !== null);
  for (const [signal, control] of Object.entries(controls)) {
    if (control && !available(signal)) {
      control.disabled = true;
      control.parentElement.append(' · Unavailable');
    }
  }
  const millis = apiMode ? [] : records.map(record => record.timestamp === null ? null : Date.parse(record.timestamp));
  const valid = millis.filter(t => t !== null && Number.isFinite(t));
  const sourceStart = Date.parse(container.dataset.startTime);
  const first = Number.isFinite(sourceStart) ? sourceStart : (valid[0] ?? 0);
  const elapsed = apiMode ? records.map(r=>r.time_offset) : millis.map(t => t === null || !Number.isFinite(t) ? null : (t - first) / 1000);
  const timed = elapsed.filter(t => t !== null);
  const minimum = timed.reduce((a,b)=>Math.min(a,b),0), maximum = timed.reduce((a,b)=>Math.max(a,b),0);
  const span = Math.max(1, maximum - minimum);
  const formatDuration = seconds => {
    if (seconds === null) return 'Time unavailable';
    const total = Math.round(Math.abs(seconds)), hours = Math.floor(total / 3600);
    const mins = Math.floor(total % 3600 / 60), secs = String(total % 60).padStart(2, '0');
    return (seconds < 0 ? '−' : '') + (hours ? `${hours}:${String(mins).padStart(2, '0')}:${secs}` : `${mins}:${secs}`);
  };
  const sensor = (value, unit) => value === null ? 'Unavailable' : `${value} ${unit}`;
  const make = (tag, attributes, text) => {
    const node = document.createElementNS(ns, tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    svg.appendChild(node); return node;
  };
  let selected = null, geometry, cursor, markers;
  function inspect(index) {
    if (!records.length) return;
    selected = Math.max(0, Math.min(records.length - 1, index));
    const record = records[selected], t = elapsed[selected];
    readout.textContent = `${formatDuration(t)} · Power ${visible('power') ? sensor(record.power, 'W') : 'Hidden'} · Heart rate ${visible('heart_rate') ? sensor(record.heart_rate, 'bpm') : 'Hidden'}`;
    if(apiMode){
      readout.dataset.sampleIndex = record.sample_index;
      const absolute=new Date(Date.parse(container.dataset.startTime)+t*1000);
      if(Number.isFinite(absolute.getTime())) readout.textContent += ' · '+absolute.toLocaleString();
    }else readout.dataset.recordIndex = record.record_index;
    cursor.setAttribute('visibility', t === null ? 'hidden' : 'visible');
    if (t !== null) {
      cursor.setAttribute('x1', geometry.x(t)); cursor.setAttribute('x2', geometry.x(t));
    }
    ['power', 'heart_rate'].forEach((signal, i) => {
      const marker = markers[i], value = record[signal];
      marker.setAttribute('visibility', t === null || value === null || !visible(signal) ? 'hidden' : 'visible');
      if (t !== null && value !== null) {
        marker.setAttribute('cx', geometry.x(t)); marker.setAttribute('cy', geometry.y(value, signal));
      }
    });
  }
  function draw() {
    svg.replaceChildren();
    const width = Math.max(180, container.clientWidth), height = container.clientHeight;
    const left = 43, right = width - 40, top = 26, bottom = height - 30;
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('tabindex', '0');
    const limits = {};
    ['power', 'heart_rate'].forEach(signal => {
      const step = signal === 'power' ? 50 : 20;
      limits[signal] = Math.max(step, Math.ceil(records.reduce((maximum,r)=>Math.max(maximum,r[signal] ?? 0),0) / step) * step);
    });
    geometry = {left, right, x: t => left + (t - minimum) / span * (right - left),
      y: (v, signal) => bottom - v / limits[signal] * (bottom - top)};
    if (visible('power') && available('power')) make('text', {x: left, y: 14, class: 'axis-power'}, width < 360 ? 'W' : 'Power (W)');
    if (visible('heart_rate') && available('heart_rate')) make('text', {x: right, y: 14, 'text-anchor': 'end', class: 'axis-hr'}, width < 360 ? 'bpm' : 'Heart rate (bpm)');
    for (let i = 0; i <= 4; i++) {
      const y = bottom - i / 4 * (bottom - top);
      make('line', {x1: left, x2: right, y1: y, y2: y, class: 'chart-grid'});
      if (visible('power') && available('power')) make('text', {x: left - 9, y: y + 4, 'text-anchor': 'end', class: 'axis-power'}, String(limits.power * i / 4));
      if (visible('heart_rate') && available('heart_rate')) make('text', {x: right + 9, y: y + 4, class: 'axis-hr'}, String(limits.heart_rate * i / 4));
      const t = minimum + span * i / 4;
      if (width >= 360 || i % 2 === 0) make('text', {x: geometry.x(t), y: bottom + 22, 'text-anchor': i === 0 ? 'start' : i === 4 ? 'end' : 'middle'}, formatDuration(t));
    }
    ['power', 'heart_rate'].forEach((signal, signalIndex) => {
      if (!visible(signal) || !available(signal)) return;
      let path = '', connected = false, previous = null, count = 0;
      let area = '', segment = [], lastX;
      const closeArea = () => {
        if (segment.length) area += segment.join(' ') + ` L${lastX} ${bottom} Z `;
        segment = [];
      };
      records.forEach((record, index) => {
        const t = elapsed[index], value = record[signal];
        if (t === null || value === null) { closeArea(); connected = false; previous = null; return; }
        // A new subpath leaves missing values, timestamp gaps and backward
        // jumps visible. Zero is a valid sample. Order and duplicate times stay.
        if (previous !== null && (t - previous > 1 || t < previous)) connected = false;
        const x = geometry.x(t), y = geometry.y(value, signal);
        if (!connected) { closeArea(); segment.push(`M${x} ${bottom}`); }
        segment.push(`L${x} ${y}`); lastX = x;
        path += `${connected ? 'L' : 'M'}${x} ${y} `;
        if (!connected) make('circle', {cx: geometry.x(t), cy: geometry.y(value, signal), r: 1.5,
          class: signalIndex ? 'chart-point-hr' : 'chart-point-power'});
        connected = true; previous = t; count++;
      });
      closeArea();
      // Fill each observed segment separately: no fill bridges a missing
      // sample or time break, and the line still contains only native points.
      if (!signalIndex) make('path', {d: area, class: 'chart-power-area'});
      make('path', {d: path, class: signalIndex ? 'chart-hr' : 'chart-power', [apiMode ? 'data-api-points' : 'data-native-points']: count});
    });
    cursor = make('line', {x1: left, x2: left, y1: top, y2: bottom, class: 'chart-cursor', visibility: 'hidden'});
    markers = [make('circle', {r: 4, class: 'chart-point-power', visibility: 'hidden'}),
      make('circle', {r: 4, class: 'chart-point-hr', visibility: 'hidden'})];
    if (selected !== null) inspect(selected);
    if (!timed.length) readout.textContent = apiMode ? 'No timed API samples available.' : 'No timestamped native samples available. Use arrow keys to inspect records.';
    if (!available('power') && !available('heart_rate')) {
      make('text', {x: width / 2, y: height / 2, 'text-anchor': 'middle'}, 'Power and heart rate unavailable.');
      readout.textContent = 'Power and heart rate unavailable in the retained samples.';
    } else if (!visible('power') && !visible('heart_rate')) {
      make('text', {x: width / 2, y: height / 2, 'text-anchor': 'middle'}, 'Select a signal above to display it.');
    }
  }
  function inspectPointer(event) {
    const rect = svg.getBoundingClientRect();
    const target = minimum + (event.clientX - rect.left - geometry.left) / (geometry.right - geometry.left) * span;
    let index = null, closest = Infinity;
    // Search original records: sorting would lose duplicate/native-order evidence.
    elapsed.forEach((t, i) => {
      if (t !== null && Math.abs(t - target) < closest) { index = i; closest = Math.abs(t - target); }
    });
    if (index !== null) inspect(index);
  }
  svg.addEventListener('pointermove', inspectPointer);
  svg.addEventListener('pointerdown', event => {
    svg.focus({preventScroll: true});
    inspectPointer(event);
  });
  svg.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    inspect(event.key === 'Home' ? 0 : event.key === 'End' ? records.length - 1 :
      (selected ?? 0) + (event.key === 'ArrowRight' ? 1 : -1));
  });
  Object.values(controls).forEach(control => control?.addEventListener('change', draw));
  draw();
  new ResizeObserver(draw).observe(container);
})();
