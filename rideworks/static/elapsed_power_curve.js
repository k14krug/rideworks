'use strict';
(() => {
  const payload=document.getElementById('power-curve-data');
  if (!payload) return;
  const data=JSON.parse(payload.textContent), panel=document.getElementById('power-curve-panel');
  const svg=document.getElementById('power-curve-chart'), plot=document.getElementById('elapsed-plot');
  const box=document.getElementById('elapsed-inspector'), unpin=document.getElementById('elapsed-unpin');
  const details=document.getElementById('elapsed-recording-details'), detailContent=document.getElementById('elapsed-recording-content');
  const announce=document.getElementById('elapsed-announcement'), selector=document.getElementById('curve-b');
  const names={ride:'This ride',six:'Previous 6 weeks',year:'Prior 12 months',all:'All earlier history'};
  const ns='http://www.w3.org/2000/svg';
  const timezone=data.calendar_timezone || 'America/Los_Angeles';
  const date=value=>value ? new Date(value).toLocaleString(undefined,{year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short',timeZone:timezone}) : 'All earlier supported history';
  function duration(d) {
    if (d<60) return `${d} s`;
    const whole=Math.floor(d),hours=Math.floor(whole/3600),minutes=Math.floor((whole%3600)/60);
    const fraction=String(d).split('.')[1];
    const secondText=String(whole%60).padStart(2,'0')+(fraction?'.'+fraction:'');
    return hours ? `${hours}:${String(minutes).padStart(2,'0')}:${secondText}` : `${minutes}:${secondText}`;
  }
  function tick(d) {
    if (d<60) return `${d} s`;
    if (d<3600) return `${Number((d/60).toFixed(1))} min`;
    return `${Number((d/3600).toFixed(2))} h`;
  }
  function element(tag,attrs={},value) {
    const e=document.createElementNS(ns,tag);
    for (const [k,v] of Object.entries(attrs)) e.setAttribute(k,v);
    if (value!==undefined) e.textContent=value;
    svg.append(e);return e;
  }
  let keys=[], maps=[], durations=[], selection=null, pinned=false, scale=null, touchStart=null, lastTouch=0, pointer=null, detailsKey=null, detailsPinned=false;
  function reset() { pinned=false; box.hidden=true; unpin.hidden=true; details.hidden=true; details.open=false; detailsKey=null; detailsPinned=false; svg.querySelectorAll('.curve-selected').forEach(e=>e.remove()); }
  function announceState() {
    if (box.hidden) {announce.textContent='Power curve inspection dismissed.';return;}
    const delta=document.getElementById('elapsed-delta');
    announce.textContent=`${document.getElementById('elapsed-duration').textContent}. ${document.getElementById('elapsed-series-a').innerText}. ${document.getElementById('elapsed-series-b').innerText}. ${delta.hidden?'':delta.getAttribute('aria-label')}. ${pinned?'Pinned':'Preview'}.`;
  }
  function row(container,key,point) {
    container.replaceChildren();container.className='elapsed-inspector-row '+(key==='ride'?'elapsed-inspector-a':'elapsed-inspector-b');
    const heading=document.createElement('strong');
    heading.textContent=names[key]+': '+(point?`${point.rounded_watts} W`:'Unavailable at this duration');
    container.append(heading);
    if (!point) {
      const note=document.createElement('p');
      note.textContent=key!=='ride' && !data.series[key].points.length ? 'No qualifying comparison rides.' : 'No qualifying result at this duration.';
      container.append(note);return;
    }
    if (key!=='ride') {
      const info=document.createElement('p'),a=point.activity,link=document.createElement('a');
      link.href='/activities/'+encodeURIComponent(a.activity_id);link.textContent=a.title;
      info.append(link,document.createTextNode(` · ${a.absolute_time?date(a.start_time):(a.date_day || 'Date unavailable')}`));
      container.append(info);
    }
    const evidence=document.createElement('p');
      let parts=[];
      if (point.pause_seconds) parts.push(`Paused ${point.pause_seconds} s at zero`);
      if (point.estimated_seconds) parts.push(`${point.estimated_seconds} s estimated`);
      if (point.unknown_seconds) parts.push(`${point.unknown_seconds} s unknown, assumed zero work`);
      if (!parts.length) return;
      evidence.textContent=parts.join(' · ')+'.';
    container.append(evidence);
  }
  function position() {
    if (box.hidden || !scale) return;
    // Fit the box inside the plot, moving it away from the selection where possible.
    const width=plot.clientWidth, boxWidth=box.offsetWidth, x=pointer ? pointer.x : scale.x(selection);
    let left=x+18;
    if (left+boxWidth>width-5) left=x-boxWidth-18;
    box.style.left=Math.max(5,Math.min(left,width-boxWidth-5))+'px';
    const horizontalOverlap=pointer && pointer.x>=parseFloat(box.style.left) && pointer.x<=parseFloat(box.style.left)+boxWidth;
    box.style.top=(horizontalOverlap && pointer.y<plot.clientHeight/2 ? Math.max(8,plot.clientHeight-box.offsetHeight-8) : 8)+'px';
  }
  function inspect(d,keyboard=false) {
    if (!durations.length || !scale || !durations.includes(d)) return;
    selection=d;svg.dataset.duration=String(d);box.hidden=false;unpin.hidden=!pinned;
    svg.querySelectorAll('.curve-selected').forEach(e=>e.remove());
    element('path',{d:`M${scale.x(d)} ${scale.top}V${scale.bottom}`,class:'curve-selected curve-guide'});
    const current=maps[0].get(d), prior=maps[1].get(d);
    [current,prior].forEach((p,i)=>{
      if (!p) return;
      element(i?'rect':'circle',i?{x:scale.x(d)-4,y:scale.y(p.average_watts)-4,width:8,height:8,class:'curve-selected curve-marker curve-marker-b'}:{cx:scale.x(d),cy:scale.y(p.average_watts),r:4,class:'curve-selected curve-marker curve-marker-a'});
    });
    document.getElementById('elapsed-duration').textContent=duration(d);
    row(document.getElementById('elapsed-series-a'),'ride',current);
    row(document.getElementById('elapsed-series-b'),keys[1],prior);
    const diff=document.getElementById('elapsed-delta');
    if (current && prior) {
      const v=current.rounded_watts-prior.rounded_watts;
      const signed=v<0?`−${Math.abs(v)}`:v>0?`+${v}`:'0';
      diff.textContent=` · ${signed} W`;diff.setAttribute('aria-label',`This ride minus comparison: ${signed} watts`);diff.hidden=false;
    } else {diff.textContent='';diff.removeAttribute('aria-label');diff.hidden=true;}
    const currentKey=`${d}|${keys[1]}`;
    if (!pinned || !detailsPinned || detailsKey!==currentKey) details.open=false;
    detailsKey=currentKey;detailsPinned=pinned;
    detailContent.replaceChildren();
    [[names.ride,current],[names[keys[1]],prior]].forEach(([label,p])=>{
      if (!p) return;
      const item=document.createElement('p'), parts=[`${(p.coverage*100).toFixed(2)}% observed`,`${p.observed_seconds} s observed`];
      if(p.pause_seconds)parts.push(`paused ${p.pause_seconds} s at zero`);
      if(p.estimated_seconds)parts.push(`${p.estimated_seconds} s estimated`);
      if(p.unknown_seconds)parts.push(`${p.unknown_seconds} s unknown, assumed zero work`);
      item.textContent=`${label}: ${parts.join(' · ')}.`;detailContent.append(item);
    });
    details.hidden=!pinned || !detailContent.childElementCount;
    position();if (keyboard) announceState();
  }
  function nearest(clientX) {
    const px=clientX-svg.getBoundingClientRect().left;
    return durations.reduce((best,d)=>Math.abs(scale.x(d)-px)<Math.abs(scale.x(best)-px)?d:best,durations[0]);
  }
  function render() {
    if (panel.hidden || !svg.clientWidth) return;
    keys=['ride',selector.value]; maps=keys.map(k=>new Map(data.series[k].points.map(p=>[p.duration_seconds,p])));
    durations=[...new Set([...keys.flatMap(k=>data.series[k].anchors || []),...maps.flatMap(m=>[...m.keys()]),...(data.elapsed_duration>0?[data.elapsed_duration]:[])])].filter(d=>d>0).sort((a,b)=>a-b);
    keys.forEach((k,i)=>{const s=data.series[k];document.getElementById(i?'curve-b-bounds':'curve-a-bounds').textContent=`${s.count} qualifying ${s.count===1?'ride':'rides'}`+(i?` · ${date(s.start)} → ${date(s.end_exclusive)} (end excluded)`:'');});
    let messages=[];
    if (!maps[0].size) messages.push(data.current_reason==='profile_update_required'?'This activity needs a Power Curve update.':'No qualifying power data for this ride.');
    if (!maps[1].size) messages.push(data.baseline_reason?'Comparison unavailable: this activity has no supported absolute start.':`No qualifying rides in ${names[keys[1]]}.`);
    if (data.ambiguous_durations?.length) messages.push('Some durations have competing file sources and remain unavailable.');
    document.getElementById('curve-empty').textContent=messages.join(' ');
    const endpoint=document.getElementById('elapsed-endpoint-status');
    if (data.elapsed_duration && !maps[0].has(data.elapsed_duration)) {
      endpoint.textContent=`Full ride ${duration(data.elapsed_duration)}: unavailable${data.endpoint_coverage!=null?` (${(data.endpoint_coverage*100).toFixed(2)}% observed coverage)`:''}.`;
    } else endpoint.textContent='';
    svg.replaceChildren();panel.dataset.curveEmpty=String(!durations.length);
    svg.setAttribute('tabindex',durations.length?'0':'-1');svg.setAttribute('aria-hidden',String(!durations.length));
    if (!durations.length) { reset();scale=null;return; }
    if (!durations.includes(selection)) selection=durations.reduce((best,d)=>Math.abs(d-1200)<Math.abs(best-1200)?d:best,durations[0]);
    const width=Math.max(220,svg.clientWidth),height=svg.clientHeight;
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
    const left=48,right=width-16,top=22,bottom=height-52,maxD=durations.at(-1);
    const maximum=Math.max(1,...maps.flatMap(m=>[...m.values()].map(p=>p.average_watts)));
    const step=Math.max(1,Math.ceil(maximum/5/25)*25),maxY=Math.ceil(maximum/step)*step;
    const x=d=>left+Math.sqrt(d/maxD)*(right-left),y=w=>bottom-w/maxY*(bottom-top);
    scale={x,y,top,bottom};
    for (let w=0;w<=maxY;w+=step) {element('path',{d:`M${left} ${y(w)}H${right}`,class:'curve-grid'});element('text',{x:left-7,y:y(w)+4,'text-anchor':'end'},w);}
    element('text',{x:8,y:13},'W');
    const ticks=[...new Set([1,5,15,30,60,120,300,600,1200,1800,2700,3600,5400,7200,10800,14400,21600,43200,86400,maxD])].filter(d=>d<=maxD).sort((a,b)=>a-b);
    const edgeLabel=duration(maxD),probe=element('text',{x:right,y:bottom+22},edgeLabel);
    const edgeWidth=Math.min(probe.getComputedTextLength(),right-left);probe.remove();
    let last=left-50;
    ticks.forEach(d=>{
      const pos=x(d),edge=d===maxD;
      if (!edge && (pos-last<60 || right-pos<edgeWidth+30)) return;
      last=pos;element('path',{d:`M${pos} ${top}V${bottom}`,class:'curve-grid'});
      const label=element('text',{x:pos,y:bottom+22,'text-anchor':edge?'end':'middle'},edge?edgeLabel:tick(d));
      if(edge && label.getComputedTextLength()>right-left) {label.setAttribute('textLength',right-left);label.setAttribute('lengthAdjust','spacingAndGlyphs');}
    });
    element('text',{x:(left+right)/2,y:height-5,'text-anchor':'middle'},'Elapsed duration · square-root scale');
    maps.forEach((map,i)=>{
      let path='',pen=false; const evaluated=new Set(data.series[keys[i]].anchors || [...map.keys()]);
      for (const d of durations) {if (!evaluated.has(d)) continue;const p=map.get(d);if(!p){pen=false;continue;}path+=(pen?'L':'M')+x(d)+' '+y(p.average_watts);pen=true;}
      element('path',{d:path,class:`curve-line curve-line-${i?'b':'a'}`});
      for (const [d,p] of map) element('circle',{cx:x(d),cy:y(p.average_watts),r:1.4,class:`curve-anchor curve-anchor-${i?'b':'a'}`});
    });
    if (!box.hidden) inspect(selection);
  }
  svg.addEventListener('pointermove',e=>{
    if(e.pointerType!=='mouse'||pinned||!durations.length)return;
    if(!box.hidden){
      const b=box.getBoundingClientRect(),margin=22;
      if(e.clientX>=b.left-margin && e.clientX<=b.right+margin && e.clientY>=b.top-margin && e.clientY<=b.bottom+margin)return;
    }
    const r=plot.getBoundingClientRect();pointer={x:e.clientX-r.left,y:e.clientY-r.top};inspect(nearest(e.clientX));
  });
  svg.addEventListener('pointerdown',e=>{if(e.pointerType==='touch')touchStart={x:e.clientX,y:e.clientY};});
  svg.addEventListener('pointerup',e=>{
    if (e.pointerType!=='touch'||!touchStart) return;
    const moved=Math.hypot(e.clientX-touchStart.x,e.clientY-touchStart.y);touchStart=null;
    lastTouch=Date.now();
    if(moved>10||!durations.length)return;
    if(pinned){reset();announceState();}else{pinned=true;inspect(nearest(e.clientX),true);}
  });
  svg.addEventListener('pointercancel',()=>{touchStart=null;});
  svg.addEventListener('click',e=>{
    if(e.pointerType==='touch'||Date.now()-lastTouch<700||e.detail===0||!durations.length)return;
    if(pinned){pinned=false;inspect(nearest(e.clientX),true);}else{pinned=true;inspect(nearest(e.clientX),true);}
  });
  plot.addEventListener('pointerleave',e=>{if(!pinned&&!plot.contains(e.relatedTarget))reset();});
  svg.addEventListener('keydown',e=>{
    if(!durations.length)return;
    if(e.key==='Escape'){reset();announceState();e.preventDefault();return;}
    if(['Enter',' '].includes(e.key)){e.preventDefault();pinned=!pinned;inspect(selection??durations[0],true);return;}
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
    e.preventDefault();if(pinned)return;
    const i=Math.max(0,durations.indexOf(selection));
    const target=e.key==='Home'?0:e.key==='End'?durations.length-1:e.key==='ArrowLeft'?Math.max(0,i-1):Math.min(durations.length-1,i+1);
    inspect(durations[target],true);
  });
  box.addEventListener('keydown',e=>{if(e.key==='Escape'){reset();svg.focus();announceState();e.preventDefault();}});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!box.hidden){reset();announceState();e.preventDefault();}});
  unpin.addEventListener('click',()=>{reset();svg.focus();announceState();});
  details.addEventListener('toggle',position);
  selector.addEventListener('change',()=>{reset();render();});
  new ResizeObserver(render).observe(svg);
  render();
})();
