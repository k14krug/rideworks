(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('ftp-data').textContent);
  const $ = id => document.getElementById(id);
  const chart = $('ftp-chart'), nav = $('ftp-navigator'), from = $('ftp-from'), to = $('ftp-to');
  const date = $('ftp-date'), watts = $('ftp-watts'), save = $('ftp-save');
  const labels = {above: 'Above FTP', below: 'At or below FTP', unavailable: 'FTP unavailable'};
  const dayValue = day => Date.parse(`${day}T00:00:00Z`), DAY=86400000;
  const dates = [...data.rows.map(r => r.effective_from_date), ...data.points.map(p => p.date)].sort();
  const today = new Intl.DateTimeFormat('en-CA', {timeZone: 'America/Los_Angeles', year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const first = dates[0] || today, last = dates.at(-1) || today, fullStart=dayValue(first), fullEnd=dayValue(last)+DAY;
  let page = 0, shown = [], selected = null, drag = null;
  const checks = [...document.querySelectorAll('[data-category]')];
  const stateKey = 'rideworks-ftp-chart';
  let state = {};
  try { state = JSON.parse(sessionStorage.getItem(stateKey) || '{}'); } catch (_) { /* Storage is optional. */ }
  from.value = state.from || first; to.value = state.to || last;
  from.min=to.min=first;from.max=to.max=last;
  checks.forEach(c => { c.checked = state[c.dataset.category] !== false; });
  function remember() {
    try { sessionStorage.setItem(stateKey, JSON.stringify({from:from.value,to:to.value,...Object.fromEntries(checks.map(c => [c.dataset.category,c.checked]))})); } catch (_) { /* Storage is optional. */ }
  }
  const display = value => Number(value.toFixed(2)).toString();
  function describe(p) {
    const reason=p.ftp.status==='unknown_prehistory' ? 'before the earliest recorded FTP' : p.ftp.status==='date_uncertain' ? 'source timezone makes the FTP boundary uncertain' : '';
    return `${p.date} · ${p.title} · Activity ${p.activity_id} · raw best 20 min ${display(p.raw_watts)} W · 95% ${display(p.watts)} W · ${labels[p.category]}${p.ftp.value == null ? ` (${reason})` : ` (${p.ftp.value} W; difference ${display(p.watts-p.ftp.value)} W)`}${p.absolute_time ? '' : ' · source timezone unknown; effective date requires confirmation'}`;
  }
  function preview() {
    save.disabled = true;
    const rows=data.rows,d=date.value;
    if (!rows.length) { $('ftp-preview').textContent='No FTP history yet. Manual initialization is a separate workflow.';return; }
    if(!d){$('ftp-preview').textContent='Choose and confirm an effective calendar date.';return;}
    const existing=rows.find(r=>r.effective_from_date===d);
    if(existing){$('ftp-preview').textContent=`An FTP entry already exists on ${d}: ${existing.ftp_watts} W. It will not be overwritten.`;return;}
    const prev=rows.findLast(r=>r.effective_from_date<d),next=rows.find(r=>r.effective_from_date>d),w=Number(watts.value);
    if(!prev && next){$('ftp-preview').textContent=`New earliest setting: ${d} becomes the first known FTP date. FTP remains unknown before ${d}; ${next.ftp_watts} W remains unchanged and resumes on ${next.effective_from_date}.`;
      save.disabled=!Number.isSafeInteger(w)||w<1||!watts.validity.valid;return;}
    if(prev && !next){$('ftp-preview').textContent=`New latest setting: ${prev.ftp_watts} W remains effective through the day before ${d}. The new FTP applies from ${d} onward until another entry is added. Existing entries stay unchanged.`;
      save.disabled=!Number.isSafeInteger(w)||w<1||!watts.validity.valid;return;}
    if(!prev||!next){$('ftp-preview').textContent='Choose a valid effective date.';return;}
    $('ftp-preview').textContent=`Existing FTP: ${prev.ftp_watts} W. The new value applies from ${d} inclusive until ${next.effective_from_date} exclusive. Existing entries stay unchanged.`;
    save.disabled=!Number.isSafeInteger(w)||w<1||!watts.validity.valid;
  }
  function select(p) {
    selected=p;watts.value=p.proposed;
    const uncertain=p.ftp.status==='date_uncertain'; date.value=uncertain?'':p.date;
    const message=uncertain ? `${describe(p)} Choose and confirm an effective calendar date below; no ride timestamp will be inferred.` : describe(p);
    $('ftp-selection').replaceChildren(document.createTextNode(message+' '));
    const link=document.createElement('a');link.href=`/activities/${encodeURIComponent(p.activity_id)}`;link.textContent='Open Activity';$('ftp-selection').append(link);
    preview(); if(uncertain) date.focus({preventScroll:true}); else $('ftp-add').scrollIntoView({block:'nearest'});
    if(uncertain)$('ftp-add').scrollIntoView({block:'nearest'});
  }
  function svg(target,tag,attrs,text) {
    const el=document.createElementNS('http://www.w3.org/2000/svg',tag);
    Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));if(text!=null)el.textContent=text;target.append(el);return el;
  }
  function list() {
    const start=page*30,rows=shown.slice(start,start+30);$('ftp-rides').replaceChildren();
    rows.forEach(p=>{const tr=document.createElement('tr');[p.date,p.title,`${display(p.watts)} W`,labels[p.category]].forEach(text=>{const td=document.createElement('td');td.textContent=text;tr.append(td);});const td=document.createElement('td'),button=document.createElement('button');button.type='button';button.textContent='Select';button.setAttribute('aria-label',`Select ${p.date} ${p.title}`);button.onclick=()=>select(p);td.append(button);tr.append(td);$('ftp-rides').append(tr);});
    $('ftp-prev').disabled=page===0;$('ftp-next').disabled=start+30>=shown.length;$('ftp-page').textContent=`${shown.length?start+1:0}–${Math.min(start+30,shown.length)} of ${shown.length}`;
  }
  function paintRange() {
    const selection=nav.querySelector('.ftp-nav-selection');if(!selection)return;
    const px=d=>60+(d-fullStart)/(fullEnd-fullStart||DAY)*910;
    const left=px(dayValue(from.value)),right=px(dayValue(to.value)+DAY);
    selection.setAttribute('x',left);selection.setAttribute('width',Math.max(2,right-left));
    const startDay=dayValue(from.value)/DAY,endDay=dayValue(to.value)/DAY;
    const leftHandle=nav.querySelector('.ftp-nav-left'),rightHandle=nav.querySelector('.ftp-nav-right');
    leftHandle.setAttribute('x',left-5);rightHandle.setAttribute('x',right-5);
    leftHandle.setAttribute('aria-valuemin',fullStart/DAY);leftHandle.setAttribute('aria-valuemax',endDay);
    leftHandle.setAttribute('aria-valuenow',startDay);leftHandle.setAttribute('aria-valuetext',from.value);
    rightHandle.setAttribute('aria-valuemin',startDay);rightHandle.setAttribute('aria-valuemax',fullEnd/DAY-1);
    rightHandle.setAttribute('aria-valuenow',endDay);rightHandle.setAttribute('aria-valuetext',to.value);
  }
  function drawNavigator() {
    nav.replaceChildren();nav.setAttribute('viewBox','0 0 1000 88');nav.setAttribute('preserveAspectRatio','none');
    const px=d=>60+(dayValue(d)-fullStart)/(fullEnd-fullStart||DAY)*910, y=w=>68-Math.min(1,w/(Math.max(100,...data.points.map(p=>p.watts),...data.rows.map(r=>r.ftp_watts))*1.1))*52;
    svg(nav,'line',{x1:60,x2:970,y1:72,y2:72,class:'ftp-nav-base'});
    data.rows.forEach(r=>{const end=r.effective_until_date_exclusive||last;svg(nav,'line',{x1:px(r.effective_from_date),x2:px(end),y1:y(r.ftp_watts),y2:y(r.ftp_watts),class:'ftp-nav-ftp'});});
    data.points.filter(p=>checks.find(c=>c.dataset.category===p.category).checked).forEach(p=>svg(nav,'circle',{cx:px(p.date),cy:y(p.watts),r:.8,class:`ftp-nav-dot ${p.category}`}));
    svg(nav,'rect',{x:60,y:8,width:910,height:68,class:'ftp-nav-selection'});
    const l=svg(nav,'rect',{x:55,y:7,width:10,height:70,class:'ftp-nav-handle ftp-nav-left',role:'slider',tabindex:'0','aria-label':'Range start'});
    const r=svg(nav,'rect',{x:965,y:7,width:10,height:70,class:'ftp-nav-handle ftp-nav-right',role:'slider',tabindex:'0','aria-label':'Range end'});
    [l,r].forEach(el=>el.addEventListener('keydown',e=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
      e.preventDefault();let a=dayValue(from.value),b=dayValue(to.value)+DAY;
      if(el===l){if(e.key==='Home')a=fullStart;else if(e.key==='End')a=b-DAY;else a+=e.key==='ArrowRight'?DAY:-DAY;
        a=Math.max(fullStart,Math.min(a,b-DAY));from.value=new Date(a).toISOString().slice(0,10);
      }else{if(e.key==='End')b=fullEnd;else if(e.key==='Home')b=a+DAY;else b+=e.key==='ArrowRight'?DAY:-DAY;
        b=Math.max(a+DAY,Math.min(b,fullEnd));to.value=new Date(b-DAY).toISOString().slice(0,10);}
      render(false);
    }));
    paintRange();
  }
  function drawMain() {
    const min=dayValue(from.value),max=dayValue(to.value);
    if(!Number.isFinite(min)||!Number.isFinite(max)||min>max){to.setCustomValidity('Choose an end date on or after the start date.');to.reportValidity();return false;}
    to.setCustomValidity('');chart.replaceChildren();chart.setAttribute('viewBox','0 0 1000 360');
    shown=data.points.filter(p=>p.date>=from.value&&p.date<=to.value&&checks.find(c=>c.dataset.category===p.category).checked);
    const relevant=data.rows.filter(r=>r.effective_from_date<=to.value&&(!r.effective_until_date_exclusive||r.effective_until_date_exclusive>=from.value));
    const values=[...shown.map(p=>p.watts),...relevant.map(r=>r.ftp_watts)],high=Math.max(100,...values)*1.1,x=d=>60+(dayValue(d)-min)/(max-min||DAY)*910,y=w=>310-w/high*280;
    for(let i=0;i<=4;i++){const w=high*i/4;svg(chart,'line',{x1:60,x2:970,y1:y(w),y2:y(w),class:'ftp-grid'});svg(chart,'text',{x:52,y:y(w)+4,'text-anchor':'end'},Math.round(w));}
    svg(chart,'text',{x:60,y:345},from.value);svg(chart,'text',{x:970,y:345,'text-anchor':'end'},to.value);svg(chart,'text',{x:10,y:18},'W');
    relevant.forEach(r=>{const start=r.effective_from_date<from.value?from.value:r.effective_from_date,end=r.effective_until_date_exclusive&&r.effective_until_date_exclusive<to.value?r.effective_until_date_exclusive:to.value;svg(chart,'line',{x1:x(start),x2:x(end),y1:y(r.ftp_watts),y2:y(r.ftp_watts),class:'ftp-step'});const next=data.rows.find(n=>n.effective_from_date===r.effective_until_date_exclusive);if(next&&next.effective_from_date<=to.value&&next.effective_from_date>=from.value)svg(chart,'line',{x1:x(next.effective_from_date),x2:x(next.effective_from_date),y1:y(r.ftp_watts),y2:y(next.ftp_watts),class:'ftp-step'});});
    shown.forEach(p=>{const group=svg(chart,'g',{class:'ftp-point',tabindex:'0',role:'button','aria-label':describe(p)});const hit=svg(group,'circle',{cx:x(p.date),cy:y(p.watts),r:10,class:'ftp-hit'});const dot=svg(group,'circle',{cx:x(p.date),cy:y(p.watts),r:2.7,class:`ftp-dot ${p.category}`});const title=document.createElementNS(chart.namespaceURI,'title');title.textContent=describe(p);group.append(title);group.addEventListener('pointerenter',()=>{$('ftp-hover').textContent=describe(p);});group.addEventListener('click',()=>select(p));group.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(p);}});});
    data.rows.filter(r=>r.effective_from_date>=from.value&&r.effective_from_date<=to.value).forEach(r=>{const marker=svg(chart,'circle',{cx:x(r.effective_from_date),cy:y(r.ftp_watts),r:4,class:'ftp-entry'});const title=document.createElementNS(chart.namespaceURI,'title');title.textContent=`${r.effective_from_date}: FTP ${r.ftp_watts} W`;marker.append(title);});
    $('ftp-count').textContent=`${shown.length} eligible rides in range · ${data.rows.length} recorded FTP entries${!data.rows.length?' · No FTP history yet':''}`;page=0;list();paintRange();return true;
  }
  function render(rebuildNavigator=true){if(!drawMain())return;remember();if(rebuildNavigator)drawNavigator();}
  function dateAt(clientX){const rect=nav.getBoundingClientRect(),svgX=(clientX-rect.left)/rect.width*1000,ratio=Math.max(0,Math.min(1,(svgX-60)/910)),ms=fullStart+Math.round(ratio*(fullEnd-fullStart));return fullStart+Math.round((ms-fullStart)/DAY)*DAY;}
  nav.addEventListener('pointerdown',e=>{const target=e.target.closest('.ftp-nav-left,.ftp-nav-right,.ftp-nav-selection');if(!target)return;e.preventDefault();const role=target.classList.contains('ftp-nav-left')?'left':target.classList.contains('ftp-nav-right')?'right':'pan';drag={role,startX:e.clientX,from:dayValue(from.value),to:dayValue(to.value),lastX:e.clientX};nav.setPointerCapture(e.pointerId);});
  nav.addEventListener('pointermove',e=>{if(!drag)return;const step=dateAt(e.clientX)-dateAt(drag.startX);let a=drag.from,b=drag.to+DAY;if(drag.role==='left')a=Math.max(fullStart,Math.min(drag.from+step,b-DAY));else if(drag.role==='right')b=Math.min(fullEnd,Math.max(drag.to+DAY+step,a+DAY));else{const width=b-a;a=Math.max(fullStart,Math.min(drag.from+step,fullEnd-width));b=a+width;}from.value=new Date(a).toISOString().slice(0,10);to.value=new Date(b-DAY).toISOString().slice(0,10);drawMain();paintRange();remember();});
  nav.addEventListener('pointerup',()=>{if(drag){drag=null;render();}});nav.addEventListener('pointercancel',()=>{drag=null;render();});
  $('ftp-range').onsubmit=e=>{e.preventDefault();render();};from.oninput=to.oninput=()=>to.setCustomValidity('');
  $('ftp-reset').onclick=()=>{from.value=first;to.value=last;checks.forEach(c=>c.checked=true);render();};checks.forEach(c=>c.onchange=()=>render());
  $('ftp-prev').onclick=()=>{page--;list();};$('ftp-next').onclick=()=>{page++;list();};date.oninput=()=>{selected=null;$('ftp-selection').textContent='Manual date/value entry.';preview();};watts.oninput=preview;
  $('ftp-cancel').onclick=()=>{selected=null;date.value='';watts.value='';$('ftp-selection').textContent='';preview();date.focus();};$('ftp-add').onsubmit=e=>{preview();if(save.disabled)e.preventDefault();};
  date.value=data.draft.date;watts.value=data.draft.watts;render();preview();
})();
