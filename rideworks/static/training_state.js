/* Exact server-calculated daily evidence. Rendering never changes model math. */
(() => {
  'use strict';
  const payload = document.querySelector('#training-state-data');
  if (!payload) return;
  const data = JSON.parse(payload.textContent), days = data.days;
  const chart = document.querySelector('#training-chart');
  const dateInput = document.querySelector('#training-date');
  const rangeFirst = value => {
    if (value === 'all') return 0;
    if (value === '42') return Math.max(0,days.length-42);
    const end = new Date(days.at(-1).day+'T00:00:00Z'), months = value === '3months' ? 3 : 12;
    const target = new Date(Date.UTC(end.getUTCFullYear(),end.getUTCMonth()-months,1));
    const last = new Date(Date.UTC(target.getUTCFullYear(),target.getUTCMonth()+1,0)).getUTCDate();
    target.setUTCDate(Math.min(end.getUTCDate(),last));
    const cutoff=target.toISOString().slice(0,10), index=days.findIndex(d=>d.day>cutoff);
    return index < 0 ? days.length-1 : index;
  };
  let range = '3months', first = rangeFirst(range), selected = days.length - 1;
  let hoverGuide = null, hoverPoints = [], yFor = null;
  let keyboardInspection = false;
  const colors = {fitness: '#2563eb', fatigue: '#b77815', form: '#078675'};
  const classes = {calculated: 'Calculated power interval', corrected_estimate: 'Estimated FIT interval',
    hr_estimate: 'HR estimate', partial: 'Partial power', unavailable: 'Stress unavailable'};
  const stressClass = ride => ride.selected.method==='hr' && ride.hr.evidence_kind==='summary' ? 'HR summary estimate' : classes[ride.selected.status];
  const fmt = v => v == null ? 'Unavailable' : v.toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1});
  const node = (tag, text, className) => {
    const result = document.createElement(tag); if (text != null) result.textContent = text;
    if (className) result.className = className; return result;
  };
  const svg = (tag, attrs, text) => {
    const result = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key,value] of Object.entries(attrs)) result.setAttribute(key,value);
    if (text != null) result.textContent = text; chart.append(result); return result;
  };
  const enabled = () => [...document.querySelectorAll('[data-line]:checked')].map(input => input.dataset.line);
  let plotWidth = 920, left = 55;
  let geometry = {top:25,bottom:625,stripBottom:730,height:770};
  const px = i => left + plotWidth * (i-first) / Math.max(1, days.length-1-first);
  const sourceText = counts => Object.entries(counts).map(([key,count]) => `${count} ${classes[key]}`).join(' · ') || 'No scored rides';
  const tooltip = node('div',null,'training-tooltip');
  tooltip.id='training-tooltip'; tooltip.setAttribute('role','tooltip'); tooltip.hidden=true;
  document.body.append(tooltip); chart.setAttribute('aria-describedby',tooltip.id);
  function hideInspection() {
    keyboardInspection=false;
    tooltip.hidden=true;
    if(hoverGuide) hoverGuide.setAttribute('visibility','hidden');
    for(const point of hoverPoints) point.setAttribute('visibility','hidden');
  }
  function showInspection(index, position, keyboard=false) {
    keyboardInspection=keyboard;
    const d=days[index]; tooltip.replaceChildren(node('strong',d.day)); tooltip.dataset.day=d.day;
    tooltip.append(node('p',`${d.rides.length} recorded ${d.rides.length===1?'ride':'rides'} · ${fmt(d.stress)} selected model stress`),
      node('p',`Fitness ${fmt(d.fitness)} · Fatigue ${fmt(d.fatigue)} · Form ${fmt(d.form)} (start of day)`));
    if(d.no_record) tooltip.append(node('p','No recorded ride; rest is not established.'));
    for(const ride of d.rides) {
      const evidence=ride.selected.method==='hr'?ride.hr:ride.power;
      const formats=ride.selected.stress==null?[...new Set(ride.hr_candidates.map(c=>c.source?.format).filter(Boolean))].join(', '):evidence.source?.format;
      tooltip.append(node('p',ride.title,'training-tooltip-title'),
        node('p',`${stressClass(ride)}${ride.selected.stress==null?'':` · ${fmt(ride.selected.stress)} stress`}${formats?` · ${ride.selected.stress==null?'Evidence: ':''}${formats}`:''}`));
    }
    if(d.rides.some(r=>r.selected.method==='hr' && r.hr.evidence_kind==='summary')) tooltip.append(node('p','HR summary: active coverage and pause treatment unverified.'));
    if(d.unscored) tooltip.append(node('p',`${d.unscored} ${d.unscored===1?'ride':'rides'}: Stress unavailable. Zero numeric model contribution.`));
    tooltip.hidden=false;
    const box=tooltip.getBoundingClientRect();
    const x=position.x+14+box.width<=innerWidth-8?position.x+14:position.x-box.width-14;
    const y=position.y+14+box.height<=innerHeight-8?position.y+14:position.y-box.height-14;
    tooltip.style.left=Math.max(8,Math.min(x,innerWidth-box.width-8))+'px';
    tooltip.style.top=Math.max(8,Math.min(y,innerHeight-box.height-8))+'px';
    hoverGuide.setAttribute('x1',px(index));hoverGuide.setAttribute('x2',px(index));
    hoverGuide.setAttribute('visibility','visible');
    for(const point of hoverPoints) {
      point.setAttribute('cx',px(index));point.setAttribute('cy',yFor(d[point.dataset.line]));
      point.setAttribute('visibility','visible');
    }
  }
  function focusedInspection() {
    const point=chart.createSVGPoint();point.x=px(selected);point.y=(geometry.top+geometry.bottom)/2;
    const position=point.matrixTransform(chart.getScreenCTM());
    showInspection(selected,{x:position.x,y:position.y},true);
  }
  function chartPosition(event) {
    const point=chart.createSVGPoint();point.x=event.clientX;point.y=event.clientY;
    return point.matrixTransform(chart.getScreenCTM().inverse());
  }
  function nearest(point) {
    return Math.max(first,Math.min(days.length-1,first+Math.round((point.x-left)/plotWidth*(days.length-1-first))));
  }
  function render() {
    hideInspection();
    const day = days[selected], lines = enabled(), visible = days.slice(first);
    dateInput.value = day.day; dateInput.min = days[first].day; dateInput.max = days.at(-1).day;
    for (const key of ['fitness','fatigue','form']) {
      document.querySelector(`#training-${key}`).textContent = fmt(day[key]);
      const change = day.changes7[key];
      document.querySelector(`#training-${key}-change`).textContent = change == null ? '7-day change unavailable' : `${change > 0 ? '+' : ''}${fmt(change)} vs 7 days earlier`;
    }
    chart.replaceChildren();
    const widthPixels = Math.max(1,chart.clientWidth), right = widthPixels-15;
    left = 45; plotWidth = right-left;
    const height=chart.clientHeight;
    geometry={top:25,bottom:height-145,stripBottom:height-40,height};
    chart.setAttribute('viewBox', `0 0 ${widthPixels} ${height}`);
    chart.dataset.plotTop=geometry.top; chart.dataset.plotBottom=geometry.bottom;
    chart.dataset.stripBottom=geometry.stripBottom;
    const values = visible.flatMap(d => lines.map(key => d[key]));
    let low = Math.min(0,...values), high = Math.max(1,...values);
    const pad = Math.max(2,(high-low)*.08); low -= pad; high += pad;
    const py = value => geometry.bottom - (geometry.bottom-geometry.top) * (value-low)/(high-low); yFor=py;
    for (let i=0;i<=4;i++) {
      const value = low+(high-low)*i/4, y=py(value);
      svg('line',{x1:left,x2:right,y1:y,y2:y,class:'chart-grid'});
      svg('text',{x:left-8,y:y+4,'text-anchor':'end'},fmt(value));
    }
    svg('line',{x1:left,x2:right,y1:py(0),y2:py(0),class:'training-zero'});
    svg('text',{x:right,y:py(0)-4,'text-anchor':'end'},'Form zero');
    for (const key of lines) {
      // Every exact day is rendered; selection remains independent of SVG paths.
      const step = 1; let path='';
      for (let i=first;i<days.length;i+=step) path += `${path ? 'L' : 'M'}${px(i).toFixed(2)},${py(days[i][key]).toFixed(2)} `;
      if ((days.length-1-first)%step) path+=`L${px(days.length-1)},${py(days.at(-1)[key])}`;
      svg('path',{d:path,fill:'none',stroke:colors[key],'stroke-width':2,'data-series':key});
      svg('circle',{cx:px(selected),cy:py(day[key]),r:4,fill:colors[key]});
    }
    svg('line',{x1:px(selected),x2:px(selected),y1:geometry.top,y2:geometry.stripBottom+10,class:'chart-cursor'});
    hoverGuide=svg('line',{x1:0,x2:0,y1:geometry.top,y2:geometry.stripBottom+10,class:'training-hover-guide',visibility:'hidden'});
    hoverPoints=lines.map(key=>{
      const circle=svg('circle',{cx:0,cy:0,r:4,fill:colors[key],visibility:'hidden','data-line':key,class:'training-hover-point'});
      return circle;
    });
    svg('text',{x:left,y:geometry.bottom+35},'Daily selected stress');
    const maximum = Math.max(1,...visible.map(d => d.stress));
    const width = Math.max(.4,Math.min(12,plotWidth/visible.length*.75));
    for (let i=first;i<days.length;i++) {
      const d=days[i], keys=Object.keys(d.source_classes);
      const color = keys.length !== 1 || keys[0]==='partial' ? '#768292' : keys[0]==='hr_estimate' ? '#078675' : '#2563eb';
      if (d.stress > 0) svg('rect',{x:px(i)-width/2,y:geometry.stripBottom-d.stress/maximum*50,width,height:d.stress/maximum*50,fill:color});
      if (d.unscored) svg('text',{x:px(i),y:geometry.stripBottom+12,'text-anchor':'middle'},'×');
    }
    svg('line',{x1:left,x2:right,y1:geometry.stripBottom,y2:geometry.stripBottom,class:'chart-grid'});
    const tickCount = Math.max(2,Math.min(4,Math.floor(plotWidth/110)));
    for (let tick=0;tick<=tickCount;tick++) {
      const i=first+Math.round((days.length-1-first)*tick/tickCount);
      svg('text',{x:px(i),y:height-12,'text-anchor':tick===0?'start':tick===tickCount?'end':'middle'},days[i].day);
    }
    chart.setAttribute('aria-label', `${day.day}. Fitness ${fmt(day.fitness)}, Fatigue ${fmt(day.fatigue)}, Form ${fmt(day.form)}. Arrow keys change date.`);
    document.querySelector('#training-chart-readout').textContent = `${day.day} · ${fmt(day.stress)} selected stress · ${day.rides.length} recorded rides${day.early_history_provisional ? ' · early model history provisional' : ''}`;
    document.querySelector('#training-day-heading').textContent = `Selected day · ${day.day}`;
    const detail=document.querySelector('#training-day-detail'); detail.replaceChildren(node('p', `${fmt(day.stress)} selected model stress`));
    if (day.no_record) detail.append(node('p','No recorded ride. Zero recorded model load; rest is not established.'));
    for (const ride of day.rides) {
      const article=node('article',null,'training-ride');
      const link=node('a',ride.title); link.href=`/activities/${ride.activity_id}`; article.append(link);
      const description=ride.selected.method==='hr' && ride.hr.evidence_kind==='summary' ? ride.selected.scope : `${stressClass(ride)} · ${ride.selected.scope}`;
      article.append(node('p',`${fmt(ride.selected.stress)} · ${description}`));
      if (ride.selected.status==='unavailable') article.append(node('p','Zero numeric model contribution; stress evidence remains unavailable.'));
      const inspection=node('details'), summary=node('summary','Source and calculation'); inspection.append(summary);
      const evidence={selected:ride.selected,power:ride.power,power_candidates:ride.power_candidates,power_source_policy:ride.power_source_policy,hr:ride.hr,hr_candidates:ride.hr_candidates,
        ftp:ride.ftp,hr_settings:ride.hr_settings,version:ride.version,timezone_unknown:ride.timezone_unknown};
      inspection.append(node('pre',JSON.stringify(evidence,null,2))); article.append(inspection); detail.append(article);
    }
    const workload=document.querySelector('#training-workload'); workload.replaceChildren();
    for (const n of [7,42]) {
      const w=day[`window${n}`], section=node('section',null,'training-window');
      section.append(node('h3',`Trailing ${n} days`),node('p',`${fmt(w.stress)} stress points · ${w.contributors}/${w.rides} rides scored · ${w.unscored} unscored`),
        node('p',sourceText(w.source_classes)),node('p',`${w.work_contributors===0 && w.rides>0 ? 'Unavailable' : fmt(w.work_kj)} observed kJ · ${w.work_contributors} contributors · ${w.work_omissions} omissions`),
        node('p',`${w.known_missing_power_seconds} known interior missing power seconds · ${w.verified_boundary_missing_seconds} verified boundary missing seconds · ${w.excluded_short_power_seconds} observed seconds excluded from partial stress · ${w.no_record_days} no-record dates`));
      if (w.calendar_days<n) section.append(node('p',`${w.calendar_days} days available since model start`));
      workload.append(section);
    }
  }
  function select(index) { selected=Math.max(first,Math.min(days.length-1,index)); render(); }
  function pointer(event) { select(nearest(chartPosition(event))); }
  chart.addEventListener('pointerdown',event=>{
    pointer(event);chart.focus();
    showInspection(selected,{x:event.clientX,y:event.clientY});
  });
  chart.addEventListener('pointermove',event=>{
    if(event.pointerType==='touch') return;
    const point=chartPosition(event);
    if(point.x<left || point.x>left+plotWidth || point.y<geometry.top || point.y>geometry.stripBottom+15) {hideInspection();return;}
    if(event.buttons===1) pointer(event);
    showInspection(nearest(point),{x:event.clientX,y:event.clientY});
  });
  chart.addEventListener('pointerleave',hideInspection);
  chart.addEventListener('pointercancel',hideInspection);
  chart.addEventListener('focus',focusedInspection);
  chart.addEventListener('blur',hideInspection);
  window.addEventListener('scroll',()=>{
    // Focus may scroll a tall chart into view after its keyboard readout opens.
    // Keep that readout anchored; pointer inspection still dismisses on scroll.
    const bounds=chart.getBoundingClientRect();
    if(keyboardInspection && document.activeElement===chart && bounds.bottom>0 && bounds.top<innerHeight) focusedInspection();
    else hideInspection();
  },{passive:true});
  new ResizeObserver(render).observe(chart);
  chart.addEventListener('keydown',event=>{
    const movement={ArrowLeft:-1,ArrowRight:1,ArrowUp:7,ArrowDown:-7};
    if (event.key in movement) {event.preventDefault();select(selected+movement[event.key]);focusedInspection();}
    if (event.key==='Home' || event.key==='End') {event.preventDefault();select(event.key==='Home'?first:days.length-1);focusedInspection();}
    if(event.key==='Escape') hideInspection();
  });
  dateInput.addEventListener('change',()=>{const i=days.findIndex(d=>d.day===dateInput.value);if(i>=first)select(i);else render();});
  for (const input of document.querySelectorAll('[data-line]')) input.addEventListener('change',render);
  for (const button of document.querySelectorAll('[data-range]')) button.addEventListener('click',()=>{
    range=button.dataset.range; first=rangeFirst(range);
    if(selected<first)selected=days.length-1;
    for (const item of document.querySelectorAll('[data-range]')) item.setAttribute('aria-pressed',String(item===button));
    render();
  });
  render();
})();
