(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('ftp-data').textContent);
  const $ = id => document.getElementById(id);
  const chart = $('ftp-chart'), from = $('ftp-from'), to = $('ftp-to');
  const date = $('ftp-date'), watts = $('ftp-watts'), save = $('ftp-save');
  const labels = {above: 'Above FTP', below: 'At or below FTP', unavailable: 'FTP unavailable'};
  const dayValue = day => Date.parse(`${day}T00:00:00Z`);
  const dates = [...data.rows.map(r => r.effective_from_date), ...data.points.map(p => p.date)].sort();
  const today = new Intl.DateTimeFormat('en-CA', {timeZone: 'America/Los_Angeles', year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const first = dates[0] || today, last = dates.at(-1) || today;
  let page = 0, shown = [], selected = null;
  const checks = [...document.querySelectorAll('[data-category]')];
  const stateKey = 'rideworks-ftp-chart';
  let state = {};
  try { state = JSON.parse(sessionStorage.getItem(stateKey) || '{}'); } catch (_) { /* Storage is optional. */ }
  from.value = state.from || first; to.value = state.to || last;
  checks.forEach(c => { c.checked = state[c.dataset.category] !== false; });
  function remember() {
    try { sessionStorage.setItem(stateKey, JSON.stringify({from:from.value,to:to.value,...Object.fromEntries(checks.map(c => [c.dataset.category,c.checked]))})); } catch (_) { /* Storage is optional. */ }
  }
  const display = value => Number(value.toFixed(2)).toString();
  function describe(p) {
    return `${p.date} · ${p.title} · Activity ${p.activity_id} · raw best 20 min ${display(p.raw_watts)} W · 95% ${display(p.watts)} W · ${labels[p.category]}${p.ftp.value == null ? ` (${p.ftp.status.replaceAll('_',' ')})` : ` (${p.ftp.value} W; difference ${display(p.watts-p.ftp.value)} W)`}${p.absolute_time ? '' : ' · source timezone unknown'}`;
  }
  function preview() {
    save.disabled = true;
    const rows = data.rows, d = date.value;
    if (!rows.length) { $('ftp-preview').textContent = 'No FTP history yet. Intermediate insertion needs existing dated entries.'; return; }
    const existing = rows.find(r => r.effective_from_date === d);
    if (existing) { $('ftp-preview').textContent = `An FTP entry already exists on ${d}: ${existing.ftp_watts} W. It will not be overwritten.`; return; }
    const prev = rows.findLast(r => r.effective_from_date < d), next = rows.find(r => r.effective_from_date > d);
    if (!d || !prev || !next) { $('ftp-preview').textContent = `Choose a date strictly between ${rows[0].effective_from_date} and ${rows.at(-1).effective_from_date}. Rides outside this interval remain inspectable.`; return; }
    const w = Number(watts.value);
    $('ftp-preview').textContent = `Existing FTP: ${prev.ftp_watts} W. The new value applies from ${d} inclusive until ${next.effective_from_date} exclusive. Existing entries stay unchanged.`;
    save.disabled = !Number.isSafeInteger(w) || w < 1 || !watts.validity.valid;
  }
  function select(p) {
    selected = p; date.value = p.date; watts.value = p.proposed;
    $('ftp-selection').replaceChildren(document.createTextNode(describe(p) + ' '));
    const link = document.createElement('a'); link.href = `/activities/${encodeURIComponent(p.activity_id)}`; link.textContent = 'Open Activity'; $('ftp-selection').append(link);
    preview(); date.focus({preventScroll:true}); $('ftp-add').scrollIntoView({block:'nearest'});
  }
  function svg(tag, attrs, text) {
    const el = document.createElementNS('http://www.w3.org/2000/svg',tag);
    Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k,v)); if (text != null) el.textContent = text; chart.append(el); return el;
  }
  function list() {
    const start = page*30, rows = shown.slice(start,start+30); $('ftp-rides').replaceChildren();
    rows.forEach(p => {
      const tr = document.createElement('tr');
      [p.date,p.title,`${display(p.watts)} W`,labels[p.category]].forEach(text => { const td = document.createElement('td'); td.textContent=text;tr.append(td); });
      const td = document.createElement('td'), button = document.createElement('button'); button.type='button'; button.textContent='Select';button.setAttribute('aria-label',`Select ${p.date} ${p.title}`);button.onclick=() => select(p);td.append(button);tr.append(td);$('ftp-rides').append(tr);
    });
    $('ftp-prev').disabled=page===0; $('ftp-next').disabled=start+30>=shown.length;
    $('ftp-page').textContent=`${shown.length ? start+1 : 0}–${Math.min(start+30,shown.length)} of ${shown.length}`;
  }
  function render() {
    const min=dayValue(from.value), max=dayValue(to.value);
    if (!Number.isFinite(min) || !Number.isFinite(max) || min>max) { to.setCustomValidity('Choose an end date on or after the start date.');to.reportValidity();return; }
    to.setCustomValidity('');remember();chart.replaceChildren();chart.setAttribute('viewBox','0 0 1000 360');
    shown=data.points.filter(p => p.date>=from.value && p.date<=to.value && checks.find(c => c.dataset.category===p.category).checked);
    const relevant=data.rows.filter(r => r.effective_from_date<=to.value && (!r.effective_until_date_exclusive || r.effective_until_date_exclusive>=from.value));
    const values=[...shown.map(p=>p.watts),...relevant.map(r=>r.ftp_watts)];
    const high=Math.max(100,...values)*1.1, x=d=>60+(dayValue(d)-min)/(max-min || 86400000)*910, y=w=>310-w/high*280;
    for(let i=0;i<=4;i++){const w=high*i/4;svg('line',{x1:60,x2:970,y1:y(w),y2:y(w),class:'ftp-grid'});svg('text',{x:52,y:y(w)+4,'text-anchor':'end'},Math.round(w));}
    svg('text',{x:60,y:345},from.value);svg('text',{x:970,y:345,'text-anchor':'end'},to.value);svg('text',{x:10,y:18},'W');
    relevant.forEach(r => {
      const start=r.effective_from_date<from.value ? from.value:r.effective_from_date;
      const end=r.effective_until_date_exclusive && r.effective_until_date_exclusive<to.value ? r.effective_until_date_exclusive:to.value;
      svg('line',{x1:x(start),x2:x(end),y1:y(r.ftp_watts),y2:y(r.ftp_watts),class:'ftp-step'});
      const next=data.rows.find(n => n.effective_from_date===r.effective_until_date_exclusive);
      if(next && next.effective_from_date<=to.value && next.effective_from_date>=from.value)svg('line',{x1:x(next.effective_from_date),x2:x(next.effective_from_date),y1:y(r.ftp_watts),y2:y(next.ftp_watts),class:'ftp-step'});
    });
    shown.forEach(p=>{
      const dot=svg('circle',{cx:x(p.date),cy:y(p.watts),r:5,class:`ftp-dot ${p.category}`,role:'button','aria-label':describe(p)});
      const title=document.createElementNS(chart.namespaceURI,'title');title.textContent=describe(p);dot.append(title);
      dot.addEventListener('pointerenter',()=>{$('ftp-hover').textContent=describe(p);});dot.addEventListener('click',()=>select(p));
    });
    data.rows.filter(r=>r.effective_from_date>=from.value && r.effective_from_date<=to.value).forEach(r=>{
      const marker=svg('circle',{cx:x(r.effective_from_date),cy:y(r.ftp_watts),r:4,class:'ftp-entry'});const title=document.createElementNS(chart.namespaceURI,'title');title.textContent=`${r.effective_from_date}: FTP ${r.ftp_watts} W`;marker.append(title);
    });
    $('ftp-count').textContent=`${shown.length} eligible rides in range · ${data.rows.length} recorded FTP entries${!data.rows.length ? ' · No FTP history yet' : ''}`;
    page=0;list();
  }
  $('ftp-range').onsubmit=e=>{e.preventDefault();render();};
  from.oninput=to.oninput=()=>to.setCustomValidity('');
  $('ftp-reset').onclick=()=>{from.value=first;to.value=last;checks.forEach(c=>c.checked=true);render();};checks.forEach(c=>c.onchange=render);
  $('ftp-prev').onclick=()=>{page--;list();};$('ftp-next').onclick=()=>{page++;list();};
  date.oninput=()=>{selected=null;$('ftp-selection').textContent='Manual date/value entry.';preview();};watts.oninput=preview;
  $('ftp-cancel').onclick=()=>{selected=null;date.value='';watts.value='';$('ftp-selection').textContent='';preview();date.focus();};
  $('ftp-add').onsubmit=e=>{preview();if(save.disabled)e.preventDefault();};
  date.value=data.draft.date;watts.value=data.draft.watts;render();preview();
})();
