'use strict';
(() => {
  const payload = document.getElementById('power-curve-data');
  if (!payload) return;
  const data = JSON.parse(payload.textContent);
  const panel = document.getElementById('power-curve-panel');
  const svg = document.getElementById('power-curve-chart');
  const names = data.mode === 'activity'
    ? {ride:'This ride',six:'Previous 6 weeks',year:'Prior 12 months',all:'All earlier history'}
    : {six:'Last 6 weeks',previous:'Previous 6 weeks',ytd:'Year to date',last_year:'Previous calendar year',all:'All time'};
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const url = new URL(location.href);
  if (data.mode === 'performance' && url.searchParams.get('curve_tz') !== timezone) {
    url.searchParams.set('curve_tz',timezone);
    location.replace(url); return;
  }
  const $ = id => document.getElementById('curve-'+id);
  const fmt = d => d < 60 ? d+' s' : d < 3600 ? (d/60).toFixed(d%60 ? 1 : 0)+' min' : (d/3600).toFixed(d%3600 ? 2 : 0)+' h';
  const date = value => value ? new Date(value).toLocaleString(undefined,{year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}) : 'All earlier supported history';
  const namespace = 'http://www.w3.org/2000/svg';
  const node = (tag, attrs, content) => {
    const el = document.createElementNS(namespace,tag);
    for (const [key,value] of Object.entries(attrs)) el.setAttribute(key,value);
    if (content !== undefined) el.textContent = content;
    svg.append(el);return el;
  };
  let keys, maps, durations = [], selection = 1200, activeSeries = 0, scale;
  function detail(container, entries) {
    container.replaceChildren();
    for (const [name,value] of entries) {
      const row=document.createElement('div'), dt=document.createElement('dt'), dd=document.createElement('dd');
      dt.textContent=name;dd.textContent=value === null || value === undefined ? 'Unavailable' : String(value);
      row.append(dt,dd);container.append(row);
    }
  }
  function inspect(d) {
    if (!durations.length) return;
    selection=d;svg.dataset.duration=String(d);
    svg.querySelectorAll('.curve-selected').forEach(el=>el.remove());
    node('path',{d:`M${scale.x(d)} ${scale.top}V${scale.bottom}`,class:'curve-selected curve-guide'});
    const selected=maps.map(map=>map.get(d));
    selected.forEach((point,i) => {
      const key=i ? 'b' : 'a';
      $(key+'-label').textContent=names[keys[i]]+' · '+fmt(d);
      $(key+'-watts').textContent=point ? point.rounded_watts+' W' : 'Unavailable at this duration';
      const link=$(key+'-link');link.hidden=!point;
      $(key+'-ride').textContent=point ? point.activity.title+' · '+(point.activity.absolute_time ? date(point.activity.start_time) : (point.activity.date_day || 'Date unavailable')+' · absolute start unavailable') : 'No qualifying observed window.';
      const provenance=$(key+'-source');
      if (!point) {provenance.replaceChildren();return;}
      link.href='/activities/'+point.activity.activity_id;
      const source=point.source;
      detail(provenance,[['Evidence',source.origin],['Source',source.content_format],
        ['Arithmetic mean (W)',point.average_watts],['Exact mean (integer watt sum / samples)',point.sum_watts+' / '+d],
        ['Rounding','Nearest whole watt, halves up'],['Window start',point.start_timestamp],
        ['Window end (exclusive)',point.end_exclusive_timestamp],['Source ID',source.source_id],
        ['Extraction ID',source.extraction_id],['API summary Source ID',source.summary_source_id],
        ['API observation digest',source.observation_sha256],['Timer quality',source.timer_quality],
        ['Timer limitation',source.timer_problem],['Timer/source discrepancy affects this effort',source.timer_discrepancy ? 'Yes: valid recorded observations extend outside unverified timer scope. Recorded samples govern this effort.' : 'No discrepancy established'],
        ['Qualifying windows',point.eligible_window_count]]);
      node(i ? 'rect' : 'circle', i ? {x:scale.x(d)-4,y:scale.y(point.average_watts)-4,width:8,height:8,class:'curve-selected curve-marker curve-marker-b'}
        : {cx:scale.x(d),cy:scale.y(point.average_watts),r:4,class:'curve-selected curve-marker curve-marker-a'});
    });
    $('duration').textContent='Inspect: '+fmt(d)+' ('+d+' seconds)';
    $('difference').textContent=selected.every(Boolean)
      ? (selected[0].rounded_watts-selected[1].rounded_watts>0 ? '+' : '')+(selected[0].rounded_watts-selected[1].rounded_watts)+' W · '+(data.mode==='activity'?'ride − baseline':'A − B')
      : 'Comparison unavailable';
  }
  function render() {
    if (panel.hidden || svg.clientWidth === 0) return;
    keys=[data.mode === 'activity' ? 'ride' : $('a').value,$('b').value];
    maps=keys.map(key=>new Map(data.series[key].points.map(p=>[p.duration_seconds,p])));
    durations=[...new Set(maps.flatMap(map=>[...map.keys()]))].sort((a,b)=>a-b);
    keys.forEach((key,i)=> {
      const s=data.series[key];
      $(i?'b-bounds':'a-bounds').textContent=s.count+' qualifying '+(s.count===1?'ride':'rides')+(key==='ride' ? '' : ' · '+date(s.start)+' → '+date(s.end_exclusive)+' (end excluded)');
    });
    const reasons={outdoor_ride_excluded:'Outdoor Ride power is outside the trusted Virtual Ride cohort.',
      no_supported_native_window:'No qualifying native observed-power windows.',
      competing_native_sources:'Competing native power sources are ambiguous.',
      non_virtual_or_ambiguous_classification:'This activity has no unambiguous trusted Virtual Ride classification.',
      profile_update_required:'This activity needs a Power Curve update.',
      api_power_stream_unavailable:'No qualifying retained API watt/time streams.',
      api_device_watts_not_confirmed:'The API source does not confirm device watts.'};
    const messages=[];
    if (!maps[0].size) messages.push(data.mode === 'activity' ? (reasons[data.current_reason] || 'No qualifying power data for this ride.') : 'No qualifying rides in '+names[keys[0]]+'.');
    if (!maps[1].size) messages.push(data.baseline_reason ? 'Comparison unavailable: this activity has no supported absolute start.' : 'No qualifying rides in '+names[keys[1]]+'.');
    if (data.ambiguous_durations?.length) messages.push('Some durations have competing file sources and remain unavailable.');
    if (data.mode==='performance') messages.push('Periods may overlap; a period best can come from a different ride at each duration. Calendar bounds: '+data.calendar_timezone+'.');
    $('empty').textContent=messages.join(' ');
    svg.replaceChildren();
    if (data.mode === 'activity') {
      panel.dataset.curveEmpty=String(!durations.length);
      svg.setAttribute('tabindex',durations.length ? '0' : '-1');
      svg.setAttribute('aria-hidden',String(!durations.length));
    }
    if (!durations.length) {
      for (const key of ['a','b']) {$(key+'-label').textContent=names[keys[key==='a'?0:1]];$(key+'-watts').textContent='Unavailable';$(key+'-ride').textContent='';$(key+'-link').hidden=true;$(key+'-source').replaceChildren();}
      $('duration').textContent='No supported durations';$('difference').textContent='Comparison unavailable';return;
    }
    const width=Math.max(220,svg.clientWidth), height=width<500 ? 300 : 370;
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
    const left=48,right=width-16,top=22,bottom=height-46;
    const maxD=durations.at(-1), domain=Math.max(2,maxD);
    const maximum=Math.max(1,...maps.flatMap(map=>[...map.values()].map(p=>p.average_watts)));
    const step=Math.max(1,Math.ceil(maximum/5/25)*25), maxY=Math.ceil(maximum/step)*step;
    const x=d=>left+Math.log(d)/Math.log(domain)*(right-left), y=w=>bottom-w/maxY*(bottom-top);
    scale={x,y,top,bottom};
    for (let w=0;w<=maxY;w+=step) {
      node('path',{d:`M${left} ${y(w)}H${right}`,class:'curve-grid'});
      node('text',{x:left-7,y:y(w)+4,'text-anchor':'end'},w);
    }
    node('text',{x:8,y:13},'W');
    const ticks=[...new Set([1,5,15,30,60,180,300,1200,3600,7200,14400,28800,86400,maxD])].filter(d=>d<=maxD).sort((a,b)=>a-b);
    let last=-100;
    ticks.forEach(d=> {
      if (x(d)-last<47 || maxD!==d && x(maxD)-x(d)<40) return;
      last=x(d);node('path',{d:`M${x(d)} ${top}V${bottom}`,class:'curve-grid'});
      node('text',{x:x(d),y:bottom+22,'text-anchor':d===1?'start':d===maxD?'end':'middle'},fmt(d));
    });
    node('text',{x:(left+right)/2,y:height-4,'text-anchor':'middle'},'Duration · logarithmic scale');
    maps.forEach((map,i)=> {
      let path='',pen=false;
      for (const d of durations) {
        const p=map.get(d);if (!p) {pen=false;continue;}
        path+=(pen?'L':'M')+x(d)+' '+y(p.average_watts);pen=true;
      }
      node('path',{d:path,class:'curve-line curve-line-'+(i?'b':'a')});
      for (const [d,p] of map) node('circle',{cx:x(d),cy:y(p.average_watts),r:1.7,class:'curve-anchor curve-anchor-'+(i?'b':'a')});
    });
    inspect(durations.reduce((best,d)=>Math.abs(Math.log(d/selection))<Math.abs(Math.log(best/selection))?d:best,durations[0]));
  }
  const choose = event => {
    if (!durations.length) return;
    const rect=svg.getBoundingClientRect(), px=event.clientX-rect.left;
    inspect(durations.reduce((best,d)=>Math.abs(scale.x(d)-px)<Math.abs(scale.x(best)-px)?d:best,durations[0]));
  };
  svg.addEventListener('pointermove',e=>{if(e.pointerType!=='touch')choose(e);});
  svg.addEventListener('pointerdown',choose);
  svg.addEventListener('keydown',event=> {
    if (!durations.length) return;
    const index=durations.indexOf(selection);
    if (['ArrowLeft','ArrowRight','Home','End','ArrowUp','ArrowDown','Enter'].includes(event.key)) event.preventDefault();
    if (event.key==='ArrowLeft') inspect(durations[Math.max(0,index-1)]);
    if (event.key==='ArrowRight') inspect(durations[Math.min(durations.length-1,index+1)]);
    if (event.key==='Home') inspect(durations[0]);
    if (event.key==='End') inspect(durations.at(-1));
    if (event.key==='ArrowUp'||event.key==='ArrowDown') activeSeries=1-activeSeries;
    if (event.key==='Enter') {
      let link=$(activeSeries?'b-link':'a-link');
      if(link.hidden) link=$(activeSeries?'a-link':'b-link');
      if(!link.hidden)link.click();
    }
  });
  $('a')?.addEventListener('change',render);$('b').addEventListener('change',render);
  const caption=document.querySelector('.performance-count'), historyCaption=caption?.textContent;
  for (const button of document.querySelectorAll('[data-curve-mode]')) {
    button.addEventListener('click',()=> {
      panel.hidden=button.dataset.curveMode!=='curve';
      document.getElementById('performance-history-mode').hidden=!panel.hidden;
      if(caption)caption.textContent=panel.hidden?historyCaption:'Power-duration best efforts · Trusted Virtual Ride power evidence';
      document.querySelectorAll('[data-curve-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
      render();
    });
  }
  if (url.searchParams.get('curve')==='1') document.querySelector('[data-curve-mode="curve"]')?.click();
  new ResizeObserver(render).observe(svg);
  render();
})();
